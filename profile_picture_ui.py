"""Circular pictures from authorized bytes, with initials as the fallback."""
import base64
from functools import lru_cache
from io import BytesIO
from html import escape
import streamlit as st
from action_feedback import service_error
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException
from PIL import Image
import data.db as db
from core.profile_photo import initials, prepare_profile_photo

PICTURE_ERRORS = (APIError, StorageException, RequestError, RuntimeError, OSError)
_NOT_LOADED = object()
_UNAVAILABLE = object()


def picture_identity(username: str, photo: bytes | None = None, *, size=64):
    if photo:
        source = base64.b64encode(photo).decode('ascii')
        picture = f'<img src="data:image/jpeg;base64,{source}" alt="Profile picture" style="width:100%;height:100%;object-fit:cover;">'
    else:
        picture = escape(initials(username))
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin:8px 0 20px">'
        f'<span style="display:flex;align-items:center;justify-content:center;flex-shrink:0;'
        f'width:{size}px;height:{size}px;border-radius:50%;overflow:hidden;background:var(--surface-raised);'
        f'color:var(--text);font-weight:700;font-size:{size // 3}px">{picture}</span>'
        f'<span style="font-weight:600;overflow-wrap:anywhere">{escape(username)}</span></div>',
        unsafe_allow_html=True,
    )


def load_picture(viewer_id, owner_id):
    # Never cache across requests: removing a friend/request must end access.
    return db.download_profile_picture(viewer_id, st.session_state['credential_version'], owner_id)


def load_pictures(viewer_id, owner_ids, access=None):
    """Pictures the viewer may see, by player id (batches of 32 per request)."""
    owners = sorted(set(owner_ids))
    pictures = {}
    for start in range(0, len(owners), 32):
        pictures.update(db.download_profile_pictures(viewer_id, st.session_state['credential_version'],
                                                     owners[start:start + 32], access=access))
    return pictures


def member_pictures(viewer_id, memberships, member_ids, access=None) -> dict:
    """Avatar sources (data URLs) by membership id for the given members.

    Every page that shows players uses this, so pictures appear wherever the
    initials did before. Any failure keeps the initials (empty result)."""
    by_member = {m.id: m.player_id for m in memberships if m.id in set(member_ids)}
    if not by_member or not st.session_state.get('credential_version'):
        return {}
    try:
        photos = load_pictures(viewer_id, by_member.values(), access=access)
    except (*PICTURE_ERRORS, PermissionError, ValueError, KeyError):
        return {}
    return {member: avatar_src(photos[player]) for member, player in by_member.items() if player in photos}


def team_pictures(teams) -> dict:
    """Avatar sources by team id from the teams' own pictures."""
    sources = {}
    for team in teams:
        if team.photo_base64:
            try:
                sources[team.id] = avatar_src(base64.b64decode(team.photo_base64, validate=True))
            except ValueError:
                pass
    return {team: source for team, source in sources.items() if source}


@lru_cache(maxsize=128)
def avatar_src(photo: bytes | None, size: int = 128) -> str | None:
    """A small square JPEG data URL for avatars, so a list of rows stays light
    (a stored picture is 512 px). None when the bytes cannot be read."""
    if not photo:
        return None
    try:
        with Image.open(BytesIO(photo)) as image:
            image = image.convert('RGB')
            image.thumbnail((size, size))
            output = BytesIO()
            image.save(output, 'JPEG', quality=82)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    return 'data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def avatar_html(name: str, source: str | None, *, cls: str, style: str = '') -> str:
    """The round avatar used in lists: the picture when there is one, else initials."""
    if source and source.startswith('data:image/jpeg;base64,'):
        return (f'<span class="{cls}" style="{style}" aria-hidden="true">'
                f'<img src="{source}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%;">'
                '</span>')
    return f'<span class="{cls}" style="{style}" aria-hidden="true">{escape(initials(name))}</span>'


def picture_access(viewer_id):
    """Start the picture permission check early (with a page's first reads).

    Returns None when there is no signed-in credential or the check failed;
    load_pictures then runs its own check as before.
    """
    credential = st.session_state.get('credential_version')
    if not credential:
        return None
    try:
        return db.profile_picture_access(viewer_id, credential)
    except (*PICTURE_ERRORS, PermissionError, ValueError):
        return None


def show_picture_identity(viewer_id, owner_id, username, *, size=64):
    loaded = _UNAVAILABLE
    try:
        photo = load_picture(viewer_id, owner_id)
        loaded = photo
    except PICTURE_ERRORS:
        photo = None
    picture_identity(username, photo, size=size)
    return loaded


def show_picture_editor(player, *, saved_photo=_NOT_LOADED):
    st.subheader('Profile picture')
    st.caption('Visible to you, your friends and players with a pending friend request. JPEG, PNG or WebP; up to 10 MB and 20 megapixels. Pictures are centre-cropped automatically.')
    if st.session_state.pop('_picture_saved', False):
        st.success('Profile picture saved.')
    if st.session_state.pop('_picture_removed', False):
        st.success('Profile picture removed.')
    version = st.session_state.get('_picture_input_version', 0)
    source = st.radio('Picture source', ['Upload photo', 'Take photo'], horizontal=True, key='pill_radio_picture_source')
    if source == 'Take photo':
        selected = st.camera_input('Take a profile picture', key=f'profile_camera_{version}')
    else:
        selected = st.file_uploader('Choose a picture from your library', type=['jpg', 'jpeg', 'png', 'webp'],
                                    key=f'profile_upload_{version}', max_upload_size=10)
    if selected is not None:
        try:
            prepared = prepare_profile_photo(selected.getvalue())
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.caption('Preview — press Save picture to use this photo.')
            picture_identity(player.display_name, prepared, size=96)
            if st.button('Save picture', type='primary'):
                try:
                    db.save_profile_picture(player.id, st.session_state['credential_version'], selected.getvalue())
                except ValueError as exc:
                    service_error(exc, "Your picture could not be saved. Reopen Edit profile to check its saved state before retrying.", popup=True)
                except PICTURE_ERRORS as error:
                    service_error(error, "Your picture couldn't be saved. Reopen Edit profile to check the saved picture, then select your image again and retry.", popup=True)
                else:
                    st.session_state['_picture_input_version'] = version + 1
                    st.session_state['_picture_saved'] = True
                    st.rerun()
    if saved_photo is _UNAVAILABLE:
        st.info('Saved pictures are unavailable. Please try again later.')
        return
    try:
        saved = load_picture(player.id, player.id) if saved_photo is _NOT_LOADED else saved_photo
    except PICTURE_ERRORS:
        st.info('Saved pictures are unavailable. Please try again later.')
        return
    if saved and st.button('Remove picture'):
        try:
            db.remove_profile_picture(player.id, st.session_state['credential_version'])
        except PICTURE_ERRORS as error:
            service_error(error, "Your picture couldn't be removed. Reopen Edit profile to check whether it remains, then try Remove picture again if needed.", popup=True)
        else:
            st.session_state['_picture_input_version'] = version + 1
            st.session_state['_picture_removed'] = True
            st.rerun()

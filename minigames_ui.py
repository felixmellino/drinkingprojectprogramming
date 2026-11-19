"""Minigames catalogue, lobby invitations and the Chug Duel board."""
from base64 import b64encode
from pathlib import Path
from uuid import uuid4

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
from storage3.utils import StorageException

import data.db as db
from camera_capture import CameraCancelled, camera_photo
from chug_duel_component import duel_board
from core.chug_duel import allowances, component_action, night_id, next_reset, unlimited_plays, validate_pair, ERRORS
from core.checkin_photo import InvalidCheckinPhoto
from core.checkins import CheckinRejected
from core.scoring_v1 import DRINK_LABELS, SIZE_LABELS, base_points, current_time, rules_for, scoring_open, size_label
from drink_entry_ui import page_header, context_line
from phone_location import current_location, track_location

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError, StorageException)


def _error(error):
    if isinstance(error, CheckinRejected):
        st.error(ERRORS.get(error.reason, "The shared check-in could not be accepted. Please retry."))
    elif isinstance(error, (ValueError, PermissionError, RuntimeError)):
        st.error(str(error))
    else:
        st.error("The duel service is unavailable. Refresh to recover any saved action before retrying.")


def _act(player, duel, action, winner=None):
    try:
        db.chug_duel_action(player, duel["id"], action, winner)
        st.rerun()
    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
        _error(error)


def _game_cards(member, duels, *, service_available=True):
    """Show every game together; proposed games cannot start or award rewards."""
    active = [d for d in duels if d['status'] in {'invited', 'accepted', 'started'}]
    invitations = sum(d['opponent_id'] == member and d['status'] == 'invited' for d in active)
    columns = st.columns(2, gap='medium')
    with columns[0], st.container(key='minigame_card_chug', border=True):
        st.markdown(':material/sports_bar: **HEAD TO HEAD · 2 PLAYERS**')
        st.subheader('Chug Duel')
        st.write('Challenge a lobby member. Share a photo, then play together on one phone.')
        if not service_available:
            st.caption('Temporarily unavailable · Refresh to retry')
        elif invitations:
            st.caption(f'{invitations} incoming invitation' + ('s' if invitations != 1 else '') + ' · Open to respond')
        elif active:
            st.caption('Invitation or duel open · Open to continue')
        else:
            st.caption('View invitations and availability · Existing nightly rules apply')
        if st.button('Open Chug Duel', key='open_game_chug', type='primary',
                     width='stretch', disabled=not service_available):
            st.session_state['minigame_selected'] = 'chug_duel'
            st.rerun()
    with columns[1], st.container(key='minigame_card_focus', border=True):
        st.markdown(':material/psychology: **SOLO · IN DESIGN**')
        st.subheader('Focus Challenge')
        st.write('A proposed three-part challenge for reaction, memory and precision.')
        st.caption('Rules and reward under discussion · No points effect yet')
        st.button('Coming soon', key='open_game_focus', width='stretch', disabled=True)


def _focused_duel(player, duel, labels):
    """Keep one keyed board in the same screen position through all play phases."""
    with st.container(key="chug_duel_stage"):
        value = duel_board(duel, labels.get(duel["challenger_id"], "Challenger"),
                           labels.get(duel["opponent_id"], "Opponent"))
        with st.container(key="chug_duel_controls"):
            if duel["status"] == "started":
                # A compact exit is separate from both large finish targets.
                if st.button("End without winner", icon=":material/close:",
                             key=f"abort_{duel['id']}", help="End the duel. Both keep their normal drink points."):
                    _act(player, duel, "abort")
            elif st.button("Back to Minigames", key=f"chug_done_{duel['id']}"):
                st.session_state.pop("chug_focused_duel", None)
                st.rerun()
        if duel["status"] == "started":
            action = component_action(value, duel)
            if action:
                _act(player, duel, *action)


def _capture_and_start(player, lobby, season, duel):
    key = f"chug_photo_{duel['id']}"
    capture = st.session_state.get(key)
    st.caption("One shared photo of both drinks. The host's current location applies to both entries.")
    if not capture:
        stage = st.empty()
        try:
            with stage.container(key="chug_camera_stage"):
                photo = camera_photo(key=f"{key}_{st.session_state.get(key + '_number', 0)}")
        except CameraCancelled:
            stage.empty()
            st.info("Camera closed. Cancel the accepted invitation below, or reopen the camera.")
            if st.button("Reopen shared camera", key=key + "_reopen"):
                st.session_state[key + "_number"] = st.session_state.get(key + "_number", 0) + 1
                st.rerun()
            return
        except InvalidCheckinPhoto as error:
            stage.empty()
            st.error(str(error))
            if st.button("Retake shared photo", key=key + "_invalid"):
                st.session_state[key + "_number"] = st.session_state.get(key + "_number", 0) + 1
                st.rerun()
            return
        if photo:
            capture = (photo.getvalue(), current_time())
            st.session_state[key] = capture
            st.rerun()
        return
    encoded = b64encode(capture[0]).decode("ascii")
    st.html(f'<img class="chug-photo" src="data:image/jpeg;base64,{encoded}" alt="Shared duel photo">')
    if st.button("Retake shared photo", key=key + "_retake"):
        st.session_state.pop(key, None)
        st.session_state[key + "_number"] = st.session_state.get(key + "_number", 0) + 1
        st.rerun()
    gps, accuracy, problem = current_location()
    if problem:
        st.info("Waiting for a current phone location accurate to 50 m. Allow location access and keep this page open.")
    else:
        st.caption("Location ready · Exact GPS is discarded after verification.")
    st.info("Starting saves both normal drink entries and uses your challenge and their acceptance. An unfinished duel keeps those drink points.")
    if st.button("Save shared check-in & open duel", type="primary", key=key + "_start", disabled=bool(problem)):
        try:
            # Read the newest reading again at submission; do not use a preview.
            gps, accuracy, problem = current_location()
            if problem:
                raise ValueError(ERRORS["location_unavailable"])
            saved = db.start_chug_duel(player, lobby.id, season.id, duel["id"], capture[0], capture[1], gps, accuracy)
            if saved["status"] in {"started", "completed", "aborted"}:
                st.session_state.pop(key, None)
                st.rerun()
            st.warning("The invitation is no longer available. Refresh the list.")
        except (ValueError, PermissionError, CheckinRejected) + SERVICE_ERRORS as error:
            _error(error)


def render_minigames(player, member, lobby, season):
    rules = rules_for(season)
    unlimited = unlimited_plays(season)
    css = (Path(__file__).parent / "assets" / "minigames.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    page_header("Minigames", "Pick a game. Play with your lobby.", compact=True)
    context_line(lobby.name, "Test season · Unlimited minigame plays" if unlimited
                 else f"Evening resets at 06:00 · {season.timezone_name}")
    context = (member, lobby.id, season.id)
    if st.session_state.get('minigames_context', context) != context:
        st.session_state.pop('minigame_selected', None)
        st.session_state.pop('chug_focused_duel', None)
    st.session_state['minigames_context'] = context
    try:
        members = db.list_memberships_for_lobby(lobby.id)
        own = next((m for m in members if m.id == member and m.player_id == player), None)
        if own is None:
            raise PermissionError("Your membership is no longer available.")
        names = {p["id"]: p["display_name"] for p in db.list_public_usernames()}
    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
        _error(error)
        return
    labels = {m.id: names.get(m.player_id, "Lobby member") for m in members}

    @st.fragment(run_every="3s")
    def live_duels():
        now = current_time()
        try:
            duels = db.list_chug_duels(player, season.id)
        except (ValueError, PermissionError) + SERVICE_ERRORS as error:
            _game_cards(member, [], service_available=False)
            _error(error)
            return
        running = next((d for d in duels if d["status"] == "started" and d["challenger_id"] == member), None)
        if running:
            st.session_state["chug_focused_duel"] = running["id"]
        focused = running or next((d for d in duels if d["id"] == st.session_state.get("chug_focused_duel")
            and d["challenger_id"] == member and d["status"] in {"completed", "aborted"}), None)
        if focused:
            track_location()
            _focused_duel(player, focused, labels)
            return
        st.session_state.pop("chug_focused_duel", None)
        _game_cards(member, duels)
        if st.session_state.get('minigame_selected') != 'chug_duel':
            st.caption('Choose a game above. Invitations update automatically.')
            return
        if st.button('All games', icon=':material/arrow_back:', key='minigames_home'):
            st.session_state.pop('minigame_selected', None)
            st.rerun()
        st.subheader('Chug Duel', anchor=False)
        track_location()
        outgoing, incoming = allowances(member, night_id(now, season.timezone_name), duels, season=season)
        columns = st.columns(2)
        columns[0].metric("Challenge", "Unlimited" if unlimited else "Available" if outgoing else "Used / reserved")
        columns[1].metric("Accept", "Unlimited" if unlimited else "Available" if incoming else "Used / reserved")
        if unlimited:
            st.caption("TEST SEASON · Play minigames as often as you like. Finish or end the current duel first. The normal check-in cooldown still applies.")
        else:
            st.caption(f"One challenge + one acceptance per lobby and evening. Next reset: {next_reset(now, season.timezone_name):%a %H:%M %Z}.")
        if st.button("Refresh duels", key="chug_refresh"):
            st.rerun()

        active = [d for d in duels if d["status"] in {"invited", "accepted", "started"}]
        for duel in active:
            cid, oid = duel["challenger_id"], duel["opponent_id"]
            host = cid == member
            with st.container(border=True, key=f"chug_card_{duel['id']}"):
                st.text(f"{labels.get(cid, 'Lobby member')} vs {labels.get(oid, 'Lobby member')}")
                points = base_points(duel["drink_type"], duel.get("size"), rules)
                selection = DRINK_LABELS[duel["drink_type"]]
                if duel.get("size"):
                    selection += " · " + size_label(duel["drink_type"], duel["size"], rules)
                st.text(f"{selection} each · Winner {points * 2} / loser 0 base season points")
                st.caption("Territory points and owner income follow the normal check-in rules.")
                status = duel["status"]
                if status == "invited":
                    if host:
                        st.info("Waiting for the other player to accept on their own device. Invitation expires after ten minutes.")
                        if st.button("Cancel invitation", key=f"cancel_{duel['id']}"):
                            _act(player, duel, "cancel")
                    else:
                        st.info("Accept the selected drink, size and point transfer to join this duel.")
                        a, b = st.columns(2)
                        if a.button("Accept duel", key=f"accept_{duel['id']}", disabled=not incoming):
                            _act(player, duel, "accept")
                        if b.button("Decline", key=f"decline_{duel['id']}"):
                            _act(player, duel, "decline")
                elif status == "accepted":
                    if host:
                        _capture_and_start(player, lobby, season, duel)
                    else:
                        st.info("Accepted. Meet the challenger and use their phone for the shared photo and split screen.")
                    if st.button("Cancel before start", key=f"abort_{duel['id']}"):
                        _act(player, duel, "cancel" if host else "abort")
                else:
                    st.info("Duel running on the challenger's phone. Your result appears here automatically.")
                    if st.button("End without winner", key=f"abort_{duel['id']}"):
                        _act(player, duel, "abort")

        if not scoring_open(now, season):
            st.info("New duels are available during this season's open scoring window.")
        elif outgoing and not any(d["challenger_id"] == member or d["status"] != "invited" for d in active):
            st.subheader("Challenge a player")
            opponents = []
            for candidate in members:
                try:
                    validate_pair(own, candidate, lobby)
                    opponents.append(candidate.id)
                except ValueError:
                    pass
            if not opponents:
                st.info("Another eligible lobby member is needed. In team mode, choose a rival team.")
            else:
                opponent = st.selectbox("Opponent", opponents, format_func=lambda mid: labels[mid], key="chug_opponent")
                drink = st.radio("Duel drink", list(DRINK_LABELS), format_func=DRINK_LABELS.get, horizontal=True, key="chug_drink")
                size = None if drink == "shot" else st.radio("Duel size", list(SIZE_LABELS),
                    format_func=lambda s: size_label(drink, s, rules), horizontal=True, key=f"chug_size_{drink}")
                points = base_points(drink, size, rules)
                st.info(f"Both agree to the same drink and size. Winner: {points * 2} · loser: 0 base season points. A shared photo and location are required after acceptance.")
                request = (player, season.id, opponent, drink, size)
                if st.session_state.get("chug_request") != request:
                    st.session_state["chug_request"] = request
                    st.session_state["chug_invitation_id"] = str(uuid4())
                if st.button("Send challenge", type="primary", key="chug_invite"):
                    try:
                        db.invite_chug_duel(player, season.id, st.session_state["chug_invitation_id"], opponent, drink, size)
                        st.session_state.pop("chug_request", None)
                        st.rerun()
                    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
                        _error(error)

        history = [d for d in duels if d["status"] not in {"invited", "accepted", "started"}]
        if history:
            st.subheader("Recent duels")
        for duel in history[:10]:
            if duel["status"] == "completed":
                points = base_points(duel["drink_type"], duel.get("size"), rules)
                st.success(f"{labels.get(duel['winner_id'], 'Lobby member')} won · {points * 2} base season points. Other player: 0.")
            else:
                st.text(f"{labels.get(duel['challenger_id'], 'Lobby member')} vs {labels.get(duel['opponent_id'], 'Lobby member')} · {duel['status'].capitalize()}")
                if duel["status"] == "aborted":
                    st.caption("No point transfer. Both keep their normal drink points. You can play again in this test season." if unlimited
                               else "No point transfer. Both keep their normal drink points; the started allowances stay used.")
    live_duels()

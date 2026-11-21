"""Account-wide lobby context, separate from the Lobby page's open dialog."""
from datetime import datetime, timezone

import streamlit as st

import data.db as db
from core.lobby_overview import latest_season, lobby_status
from core.scoring_v1 import utc
from leaderboard_context import newest_active
from parallel import run_parallel

SELECTION_KEYS = ('current_membership_id', 'current_lobby_id', 'current_lobby_name',
                  'current_season_id', 'current_lobby_mode', 'current_team_id',
                  '_current_lobby_ends_at')


def clear_selection():
    for key in SELECTION_KEYS:
        st.session_state.pop(key, None)


def select_lobby(lobby, membership, season):
    st.session_state.update(current_membership_id=membership.id,
                            current_lobby_id=lobby.id, current_lobby_name=lobby.name,
                            current_lobby_mode=lobby.game_mode,
                            current_team_id=getattr(membership, 'team_id', None),
                            current_season_id=season.id if season else None,
                            _current_lobby_ends_at=utc(season.ends_at) if season else None)


def remember_choice(player_id, lobby_id):
    """Only explicit choices write the preference; refreshes never overwrite it."""
    db.save_lobby_choice(player_id, lobby_id)
    st.session_state['_saved_lobby_choice'] = lobby_id


def restore_selection(player_id):
    """Resolve after login and when the selected season reaches its end.

    An unavailable saved membership needs an explicit choice. An expired lobby
    falls back to the newest running competition, without changing the saved
    explicit preference. With no running alternative, leave the picker available.
    """
    now = datetime.now(timezone.utc)
    ends_at = st.session_state.get('_current_lobby_ends_at')
    restored = st.session_state.get('_lobby_restored_for') == player_id
    if restored:
        if ends_at is None or now < ends_at:
            return
        saved = None
        memberships = db.list_memberships_for_player(player_id)
    else:
        saved, memberships = run_parallel(lambda: db.get_lobby_choice(player_id),
                                         lambda: db.list_memberships_for_player(player_id))
    if saved and not any(m.lobby_id == saved for m in memberships):
        clear_selection()
        st.session_state['_lobby_choice_required'] = True
        st.session_state['_lobby_restored_for'] = player_id
        return
    lobbies = {l.id: l for l in db.list_lobbies()} if memberships else {}
    joined = [m for m in memberships if m.lobby_id in lobbies]
    seasons = run_parallel(*[lambda m=m: latest_season(db.list_seasons_for_lobby(m.lobby_id))
                             for m in joined])
    rows = [(lobbies[m.lobby_id], m, season) for m, season in zip(joined, seasons)]
    chosen = next((row for row in rows if row[0].id == saved
                   and lobby_status(row[2], now) != 'past'), None)
    if chosen is None:
        chosen = newest_active(rows, now)
    clear_selection()
    if chosen:
        select_lobby(*chosen)
    if not restored:
        st.session_state['_saved_lobby_choice'] = saved
    st.session_state['_lobby_restored_for'] = player_id

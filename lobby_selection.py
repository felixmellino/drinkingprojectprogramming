"""Account-wide lobby context, separate from the Lobby page's open dialog."""
from datetime import datetime, timezone

import streamlit as st

import data.db as db
from core.lobby_overview import latest_season
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
    # The end is kept only while the season runs: restore_selection rechecks the
    # choice once it passes. A finished lobby the player chose stays (no recheck).
    ends_at = utc(season.ends_at) if season else None
    if ends_at is not None and ends_at <= datetime.now(timezone.utc):
        ends_at = None
    st.session_state.update(current_membership_id=membership.id,
                            current_lobby_id=lobby.id, current_lobby_name=lobby.name,
                            current_lobby_mode=lobby.game_mode,
                            current_team_id=getattr(membership, 'team_id', None),
                            current_season_id=season.id if season else None,
                            _current_lobby_ends_at=ends_at)


def remember_choice(player_id, lobby_id):
    """Only explicit choices write the preference; refreshes never overwrite it."""
    db.save_lobby_choice(player_id, lobby_id)
    st.session_state['_saved_lobby_choice'] = lobby_id


def restore_selection(player_id):
    """Resolve after login and when the selected season reaches its end.

    An unavailable saved membership needs an explicit choice. The saved choice
    stays selected even after its season ends, so a player can keep viewing its
    final map, ranks and activity. Without a saved choice, the newest running
    competition is selected; with none, the picker stays available.
    """
    now = datetime.now(timezone.utc)
    ends_at = st.session_state.get('_current_lobby_ends_at')
    restored = st.session_state.get('_lobby_restored_for') == player_id
    if restored:
        if ends_at is None or now < ends_at:
            return
        saved = st.session_state.get('_saved_lobby_choice')  # an automatic pick moves on
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
    chosen = next((row for row in rows if row[0].id == saved), None)
    if chosen is None:
        chosen = newest_active(rows, now)
    clear_selection()
    if chosen:
        select_lobby(*chosen)
    if not restored:
        st.session_state['_saved_lobby_choice'] = saved
    st.session_state['_lobby_restored_for'] = player_id

"""Read-only season lookup for Leaderboard, independent of lobby selection.

Keep this import separate: a running Streamlit process may still have the
older lobby_selection module loaded when a new page version is deployed.
"""
from datetime import datetime, timezone

import streamlit as st

import data.db as db
from core.lobby_overview import latest_season, lobby_status
from core.scoring_v1 import utc
from parallel import run_parallel


def newest_active(rows, now):
    return max((row for row in rows if lobby_status(row[2], now) == 'active'),
               key=lambda row: (utc(row[2].starts_at), row[0].id), default=None)


def leaderboard_fallback(player_id):
    """Find a joined season to display without setting the gameplay lobby."""
    memberships = db.list_memberships_for_player(player_id)
    if not memberships:
        return None
    lobbies = {lobby.id: lobby for lobby in db.list_lobbies()}
    joined = [member for member in memberships if member.lobby_id in lobbies]
    seasons = run_parallel(*[lambda m=m: latest_season(db.list_seasons_for_lobby(m.lobby_id))
                             for m in joined])
    rows = [(lobbies[m.lobby_id], m, season) for m, season in zip(joined, seasons) if season is not None]

    active = newest_active(rows, datetime.now(timezone.utc))
    if active:
        return active
    saved = st.session_state.get('_saved_lobby_choice')
    return max(rows, key=lambda row: (row[0].id == saved, utc(row[1].joined_at), row[0].id),
               default=None)



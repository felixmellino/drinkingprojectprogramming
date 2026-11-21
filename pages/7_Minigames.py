"""Minigames in the selected lobby; server RPCs recheck every action."""
import streamlit as st
import data.db as db
from minigames_ui import render_minigames, _error, SERVICE_ERRORS
from shared import lobby_button, require_login, require_active_membership, selected_season

player = require_login()
member, lobby_id, season_id = require_active_membership()
try:
    season = selected_season(lobby_id, season_id)
    lobby = next((l for l in db.list_lobbies() if l.id == lobby_id), None)
    if not season or not lobby:
        st.info("Choose a lobby and season on the Lobby page.")
        lobby_button()
    elif season.scoring_version != "v1":
        st.info("Minigames are unavailable in this historical season. Create or join a new lobby on the Lobby page to play with the current rules. Your old scores are kept.")
        lobby_button()
    else:
        render_minigames(player, member, lobby, season)
except (ValueError, PermissionError) + SERVICE_ERRORS as error:
    _error(error)

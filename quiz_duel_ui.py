"""Quiz lobby and invitations. Only sanitized state crosses the component bridge."""
from uuid import uuid4
import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError
import data.db as db
from core.quiz_duel import ACTIVE, FINAL, component_action, validate_pair
from core.scoring_v1 import format_points
from quiz_duel_component import quiz_board

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError, ValueError, PermissionError)


def _action(player, duel, action, round_no=None, choice=None):
    try:
        db.quiz_action(player, duel["id"], action, round_no, choice)
        st.rerun(scope="fragment")
    except SERVICE_ERRORS as error:
        st.error(str(error) if isinstance(error, (ValueError, PermissionError, RuntimeError))
                 else "The quiz service is unavailable. Refresh to recover your saved game.")


def _stage(player, member, duel, labels):
    with st.container(key="quiz_stage"):
        ack_key = "quiz_ack_" + duel["id"]
        value = quiz_board(duel, member, labels, st.session_state.get(ack_key))
        parsed = component_action(value, duel)
        if not parsed or value["event_id"] == st.session_state.get(ack_key):
            return
        action, round_no, choice = parsed
        if action == "back":
            if duel["status"] not in FINAL:
                return
            st.session_state[ack_key] = value["event_id"]
            st.session_state.pop("quiz_focused_id", None)
            st.session_state["quiz_dismissed"] = duel["id"]
            st.rerun(scope="fragment")
        try:
            db.quiz_action(player, duel["id"], action, round_no, choice)
            st.session_state[ack_key] = value["event_id"]
            st.rerun(scope="fragment")
        except SERVICE_ERRORS as error:
            st.error(str(error) if isinstance(error, (ValueError, PermissionError, RuntimeError))
                     else "Connection interrupted. Your first answer will retry automatically.")


def render_quiz(player, member, lobby, season, members, labels):
    try:
        state = db.quiz_status(player, season.id)
    except SERVICE_ERRORS as error:
        st.error(str(error) if isinstance(error, (ValueError, RuntimeError, PermissionError))
                 else "Quiz Duel is temporarily unavailable. Refresh to retry.")
        if st.button("All games", key="quiz_error_back"):
            st.session_state.pop("minigame_selected", None)
            st.rerun()
        return
    duels = state["duels"]
    running = next((d for d in duels if d["status"] in ACTIVE), None)
    focused = running or next((d for d in duels if d["id"] == st.session_state.get("quiz_focused_id")), None)
    if focused:
        st.session_state["quiz_focused_id"] = focused["id"]
        _stage(player, member, focused, labels)
        return
    if st.button("All games", key="quiz_back"):
        st.session_state.pop("minigame_selected", None)
        st.rerun()
    st.subheader("Quiz Duel", anchor=False)
    st.write("General knowledge → multiplication → logic. First to two, or the higher score after three rounds.")
    st.caption("20 seconds · One locked answer · Faster correct answer earns one round point. "
               "Ties: up to three deciding questions. Server receipt time includes network latency.")
    st.metric("Available team points" if lobby.game_mode == "team" else "Available season points",
              format_points(state["available_points"]))
    st.caption("Stake 3–10 points. Both stakes are reserved on acceptance. Winner takes the loser's stake; "
               "a draw returns both stakes. Territory points stay unchanged.")
    st.caption("Test season · Unlimited sequential quizzes" if state["test_mode"] else
               "One challenge + one acceptance per evening · Resets at 06:00 in " + season.timezone_name)
    columns = st.columns(2)
    columns[0].caption("Challenge: " + ("Available" if state["outgoing"] else "Used / reserved"))
    columns[1].caption("Accept: " + ("Available" if state["incoming"] else "Used / reserved"))
    pending = [d for d in duels if d["status"] == "invited"]
    for duel in pending:
        with st.container(border=True):
            st.write(f"{labels.get(duel['challenger_id'], 'Player')} vs {labels.get(duel['opponent_id'], 'Player')}")
            st.write(f"Stake: {duel['stake']} points each")
            if member == duel["opponent_id"]:
                if st.button("Accept quiz", key="quiz_accept_" + duel["id"], type="primary"):
                    _action(player, duel, "accept")
                if st.button("Decline", key="quiz_decline_" + duel["id"]):
                    _action(player, duel, "decline")
            elif st.button("Cancel invitation", key="quiz_cancel_" + duel["id"]):
                _action(player, duel, "cancel")
    own = next(m for m in members if m.id == member)
    opponents = []
    for other in members:
        try:
            validate_pair(own, other, lobby)
            opponents.append(other.id)
        except ValueError:
            continue
    if not state["open"]:
        st.info("Quizzes open during this season's scoring window. Test seasons can play while active.")
    elif opponents:
        with st.form("quiz_invitation"):
            opponent = st.selectbox("Challenge player", opponents, format_func=lambda m: labels.get(m, "Lobby member"))
            stake = st.number_input("Stake (points)", min_value=3, max_value=10, value=3, step=1)
            sent = st.form_submit_button("Send quiz challenge", type="primary",
                disabled=not state["outgoing"] or state["available_points"] < stake
                or any(d["challenger_id"] == member for d in pending))
        if sent:
            request = st.session_state.setdefault("quiz_invitation_id", str(uuid4()))
            try:
                db.invite_quiz_duel(player, season.id, request, opponent, stake)
                st.session_state.pop("quiz_invitation_id", None)
                st.rerun(scope="fragment")
            except SERVICE_ERRORS as error:
                st.error(str(error) if isinstance(error, (ValueError, RuntimeError, PermissionError))
                         else "The invitation could not be confirmed. Retry to recover the same invitation.")
    else:
        st.info("Another eligible lobby member is needed. In team lobbies, choose an opposing team.")
    recent = [d for d in duels if d["status"] in FINAL]
    if recent:
        with st.expander("Recent quizzes"):
            for duel in recent[:10]:
                result = labels.get(duel.get("winner_id"), "Draw") if duel.get("winner_id") else duel["status"].title()
                st.write(f"{duel['challenger_score']} : {duel['opponent_score']} · {result} · Stake {duel['stake']}")
                if st.button("View result", key="quiz_result_" + duel["id"]):
                    st.session_state["quiz_focused_id"] = duel["id"]
                    st.rerun(scope="fragment")

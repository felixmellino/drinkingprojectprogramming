"""Reaction Duel screen: challenge, invitations, the tap board and the round-by-round result.
PostgreSQL decides every result and moves the stake (migration 025)."""
from html import escape
from uuid import uuid4

import streamlit as st
from httpx import RequestError
from postgrest.exceptions import APIError

import data.db as db
from core.reaction_duel import FINAL, STAKES, component_action, time_label, validate_pair
from core.scoring_v1 import format_points
from reaction_duel_component import reaction_board

SERVICE_ERRORS = (APIError, RequestError, RuntimeError, OSError)


def _error(error):
    st.error(str(error) if isinstance(error, (ValueError, PermissionError, RuntimeError))
             else "Reaction Duel is unavailable right now. It reloads by itself.")


def _act(player, duel, action, revision=None, elapsed_ms=None, *, rerun=True):
    try:
        db.reaction_action(player, duel["id"], action, revision, elapsed_ms)
        if rerun:
            st.rerun()
    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
        _error(error)


def _play(player, duel):
    """Full-screen tap board for the viewer's own three tries."""
    run = duel["run"]
    with st.container(key="reaction_stage"):
        value = reaction_board(run)
        with st.container(key="reaction_exit"):
            if st.button("Back to games", icon=":material/close:", key="reaction_leave",
                         help="Leave the screen. Your tries stay saved; unplayed tries count as missed when time runs out."):
                st.session_state["reaction_hidden"] = duel["id"]
                st.session_state.pop("minigame_selected", None)
                st.rerun()
        parsed = component_action(value, run)
        if parsed and run["status"] == "running":
            # The fragment poll shows the next try without remounting the board.
            _act(player, duel, parsed[0], run["revision"], parsed[1], rerun=False)


def _result(duel, member, labels):
    from minigames_ui import game_header, game_note
    game_header("Reaction Duel", "", "reaction_result_back")
    me_first = duel["challenger_id"] == member
    other = duel["opponent_id"] if me_first else duel["challenger_id"]
    if duel["status"] == "completed":
        won = duel["winner_id"] == member
        verdict = f"You won +{duel['stake']}" if won else f"You lost −{duel['stake']}"
    else:
        verdict = "Draw · stake back"
    rows = ""
    for r in duel["round_results"]:
        mine, theirs = (r["challenger_ms"], r["opponent_ms"]) if me_first else (r["opponent_ms"], r["challenger_ms"])
        rows += (f'<tr><td>{r["round_no"]}</td>'
                 f'<td class="{"win" if r["winner_id"] == member else ""}">{time_label(mine)}</td>'
                 f'<td class="{"win" if r["winner_id"] == other else ""}">{time_label(theirs)}</td></tr>')
    st.markdown(f'<p class="reaction-verdict">{escape(verdict)}</p>'
                f'<table class="reaction-rounds"><tr><th>Round</th><th>You</th>'
                f'<th>{escape(labels.get(other, "Opponent"))}</th></tr>{rows}</table>', unsafe_allow_html=True)
    if duel["status"] == "draw":
        game_note("Same rounds and same total time." if duel["reason"] == "rounds" else "Time ran out before anyone played.")
    if st.button("Done", key="reaction_done", type="primary", width="stretch"):
        st.session_state.pop("reaction_focused_id", None)
        st.rerun()


def _home(player, member, lobby, season, members, labels, state):
    from minigames_ui import game_header, game_note
    game_header("Reaction Duel", "1 vs 1 · 3 tries · best of 3", "reaction_back")
    game_note(f"{format_points(state['available_points'])} points available")
    duels = state["duels"]
    pending = [d for d in duels if d["status"] == "invited"]
    for duel in pending:
        with st.container(border=True):
            st.markdown(f'<p class="duel-vs">{escape(labels.get(duel["challenger_id"], "Player"))} <span>vs</span> '
                        f'{escape(labels.get(duel["opponent_id"], "Player"))}</p>'
                        f'<p class="duel-what">Stake {duel["stake"]} points</p>', unsafe_allow_html=True)
            if member == duel["opponent_id"]:
                accept, decline = st.columns(2)
                with accept:
                    if st.button("Accept", key="reaction_accept_" + duel["id"], type="primary", width="stretch"):
                        st.session_state.pop("reaction_hidden", None)
                        _act(player, duel, "accept")
                with decline:
                    if st.button("Decline", key="reaction_decline_" + duel["id"], width="stretch"):
                        _act(player, duel, "decline")
            else:
                game_note("Waiting for an answer.")
                if st.button("Cancel", key="reaction_cancel_" + duel["id"], width="stretch"):
                    _act(player, duel, "cancel")
    hidden = next((d for d in duels if d["status"] == "accepted"), None)
    if hidden:  # the player left a running duel: one tap brings the board back
        if st.button("Continue your duel", key="reaction_resume", type="primary", width="stretch"):
            st.session_state.pop("reaction_hidden", None)
            st.rerun()
        return
    own = next(m for m in members if m.id == member)
    opponents = []
    for other in members:
        try:
            validate_pair(own, other, lobby)
            opponents.append(other.id)
        except ValueError:
            continue
    if not state["open"]:
        game_note("Opens with the scoring window.")
    elif not opponents:
        game_note("Needs another player." if lobby.game_mode != "team" else "Needs a rival team.")
    elif not state["outgoing"]:
        game_note("You already challenged tonight. Resets at 06:00.")
    elif not any(d["challenger_id"] == member for d in pending):
        opponent = st.radio("Who", opponents, index=0 if len(opponents) == 1 else None,
                            format_func=lambda m: labels.get(m, "Lobby member"), horizontal=True,
                            key="pill_radio_reaction_opponent")
        stake = st.radio("Stake (points)", STAKES, horizontal=True, key="pill_radio_reaction_stake")
        if st.button("Challenge", type="primary", key="reaction_challenge", width="stretch",
                     disabled=opponent is None or state["available_points"] < stake):
            request = st.session_state.setdefault("reaction_invitation_id", str(uuid4()))
            try:
                db.invite_reaction_duel(player, season.id, request, opponent, stake)
                st.session_state.pop("reaction_invitation_id", None)
                st.rerun()
            except (ValueError, PermissionError) + SERVICE_ERRORS as error:
                _error(error)
    recent = [d for d in duels if d["status"] in {"completed", "draw"}]
    if recent:
        with st.expander("Recent"):
            for duel in recent[:10]:
                other = duel["opponent_id"] if duel["challenger_id"] == member else duel["challenger_id"]
                result = ("Won" if duel.get("winner_id") == member else "Lost") if duel.get("winner_id") else "Draw"
                if st.button(f"{result} vs {labels.get(other, 'Player')} · {duel['stake']} points",
                             key="reaction_result_" + duel["id"], type="tertiary"):
                    st.session_state["reaction_focused_id"] = duel["id"]
                    st.rerun()


def render_reaction(player, member, lobby, season, members, labels):
    try:
        state = db.reaction_status(player, season.id)
    except (ValueError, PermissionError) + SERVICE_ERRORS as error:
        from minigames_ui import game_header
        game_header("Reaction Duel", "", "reaction_error_back")
        _error(error)
        return
    duels = state["duels"]
    running = next((d for d in duels if d["status"] == "accepted"
                    and d["id"] != st.session_state.get("reaction_hidden")), None)
    if running:
        # Remember it, so the result opens by itself once both finished.
        st.session_state["reaction_focused_id"] = running["id"]
        if running["run"]["status"] == "running":
            _play(player, running)
        else:
            from minigames_ui import game_header, game_note
            game_header("Reaction Duel", "", "reaction_wait_back")
            other = running["opponent_id"] if running["challenger_id"] == member else running["challenger_id"]
            game_note(f"Your tries: {', '.join(time_label(t) for t in running['run']['reaction_ms'])}")
            game_note(f"Waiting for {labels.get(other, 'your opponent')} · try {min(running['other_step'] + 1, 3)} of 3")
        return
    focused = next((d for d in duels if d["id"] == st.session_state.get("reaction_focused_id")
                    and d["status"] in FINAL), None)
    if focused and focused["status"] in {"completed", "draw"}:
        _result(focused, member, labels)
        return
    _home(player, member, lobby, season, members, labels, state)

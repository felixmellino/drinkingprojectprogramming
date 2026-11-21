"""Explain rejected actions on tap; the caller must still enforce server rules.

Use inline=True inside an existing dialog: Streamlit cannot nest dialogs.
Background loading failures should keep their existing inline error instead.
"""
import streamlit as st

_SETUP_PREFIXES = (
    "Scoring setup is required", "Chug Duel setup is not complete",
    "Quiz Duel needs database migration", "Time Duel needs database migration",
    "Reaction Duel needs database migration", "Profile pictures require a private storage bucket",
    "Check-in photos require a private storage bucket",
    "Lobby invitations need database migration",
)


def service_error(error, fallback, *, popup=False):
    """Domain errors have safe messages; setup details are for the organizer.

    Unexpected service/transport exceptions never display raw server details.
    """
    details = None
    if isinstance(error, (ValueError, PermissionError)):
        message = str(error)
    elif isinstance(error, RuntimeError) and str(error).startswith(_SETUP_PREFIXES):
        message = "This feature's setup is incomplete. Ask the app organizer to finish setup, then reopen this page."
        details = str(error)
    else:
        message = fallback
    if popup:
        explain(message, details=details)
    else:
        st.error(message)
        if details:
            with st.expander("Details for the app organizer"):
                st.write(details)


@st.dialog("Action unavailable")
def _problem_dialog(messages, details):
    for message in messages:
        st.error(message)
    if details:
        with st.expander("Details"):
            st.write(details)
    if st.button("OK", key="action_feedback_ok", width="stretch"):
        st.rerun()


def explain(messages, *, details=None, inline=False):
    """Show actionable, user-safe text, without exposing raw service errors."""
    if isinstance(messages, str):
        messages = [messages]
    messages = [message for message in messages if message]
    if inline:
        for message in messages:
            st.warning(message)
        if details:
            with st.expander("Details"):
                st.write(details)
    else:
        _problem_dialog(messages, details)


def action_button(label, *, problems=(), details=None, inline=False, **kwargs):
    """Return True only for an allowed tap. Put mutations in the caller's if.

    Streamlit runs on_click callbacks before this guard, so callbacks must not
    perform guarded mutations (a clamped gallery page selection is harmless).
    """
    if not st.button(label, **kwargs):
        return False
    problems = [problem for problem in problems if problem]
    if problems:
        explain(problems, details=details, inline=inline)
        return False
    return True

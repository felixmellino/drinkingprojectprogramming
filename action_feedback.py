"""Explain rejected actions on tap; the caller must still enforce server rules.

Use inline=True inside an existing dialog: Streamlit cannot nest dialogs.
Background loading failures should keep their existing inline error instead.
"""
import streamlit as st


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

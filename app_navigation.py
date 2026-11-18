"""Bottom navigation using native Streamlit page switching, preserving login."""
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st


DESTINATIONS = [
    ("profile", "Profile", "pages/1_Profile.py", ":material/person:"),
    ("lobby", "Lobby", "pages/2_Lobby.py", ":material/group:"),
    ("checkin", "Check in", "pages/3_Check_in.py", ":material/add:"),
    ("leaderboard", "Leaderboard", "pages/4_Standings.py", ":material/leaderboard:"),
    ("history", "Photo history", "pages/6_Check_in_photos.py", ":material/photo_library:"),
]


def bottom_navigation(active: str | None = None, *, navigate=None) -> None:
    if active is None:
        path = urlsplit(st.context.url or "").path.rstrip("/").rsplit("/", 1)[-1].lower()
        active = {"profile": "profile", "lobby": "lobby", "check_in": "checkin",
                  "standings": "leaderboard", "leaderboard": "leaderboard",
                  "check_in_photos": "history", "photo_history": "history"}.get(path)
    css = (Path(__file__).parent / "assets" / "navigation.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    navigate = navigate or st.switch_page
    with st.container(key="wego_bottom_nav"):
        for column, (name, label, page, icon) in zip(st.columns(5, gap="small"), DESTINATIONS):
            with column, st.container(key=f"wego_nav_{name}"):
                if st.button(label, key=f"bottom_nav_{name}", icon=icon, width="stretch",
                             type="primary" if name == "checkin" else "tertiary"):
                    navigate(str(Path(__file__).parent / page))
                if name == "checkin":
                    st.caption("Check in")
    if active and active != "checkin":
        # Only trusted route names from DESTINATIONS enter the selector.
        if active in {item[0] for item in DESTINATIONS}:
            st.markdown(f'<style>.st-key-wego_nav_{active} button {{background:#e8f2e2;color:#176c50;}}</style>',
                        unsafe_allow_html=True)

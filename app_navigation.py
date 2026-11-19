"""Bottom tab bar using native Streamlit page switching, preserving login.

Five tabs like an iPhone app, with the check-in plus in the middle. Lobby
and Photo history open from the Profile tab. Icons are Phosphor SVGs
(assets/icons, MIT licence), drawn with a CSS mask so they take the text
colour: outline normally, filled for the active tab.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from theme import icon_css, icon_url  # noqa: F401  (icon_url is used by the tests)

ASSETS = Path(__file__).parent / "assets"

# (route, label, page, Phosphor icon name). The plus stays in the middle.
DESTINATIONS = [
    ("map", "Map", "pages/5_Map.py", "map-trifold"),
    ("leaderboard", "Ranks", "pages/4_Standings.py", "trophy"),
    ("checkin", "Check in", "pages/3_Check_in.py", "plus-bold"),
    ("minigames", "Games", "pages/7_Minigames.py", "game-controller"),
    ("profile", "Profile", "pages/1_Profile.py", "user-circle"),
]
# Pages without their own tab light up the tab they are reached from.
ROUTES = {"profile": "profile", "lobby": "profile", "check_in": "checkin",
          "standings": "leaderboard", "leaderboard": "leaderboard", "map": "map",
          "check_in_photos": "profile", "photo_history": "profile", "minigames": "minigames"}


def _styles(active: str | None) -> str:
    css = (ASSETS / "navigation.css").read_text(encoding="utf-8")
    for route, _label, _page, icon in DESTINATIONS:
        filled = route == active and route != "checkin"
        css += icon_css(f".st-key-wego_nav_{route} button::before", f"{icon}-fill" if filled else icon)
    if active in {item[0] for item in DESTINATIONS} and active != "checkin":
        css += f".st-key-wego_nav_{active} button{{color:var(--accent-ink);}}"
    return css


def bottom_navigation(active: str | None = None, *, navigate=None) -> None:
    if active is None:
        path = urlsplit(st.context.url or "").path.rstrip("/").rsplit("/", 1)[-1].lower()
        active = ROUTES.get(path)
    # Only trusted route names from DESTINATIONS reach the CSS selectors.
    st.markdown(f"<style>{_styles(active if active in ROUTES.values() else None)}</style>",
                unsafe_allow_html=True)
    navigate = navigate or st.switch_page
    with st.container(key="wego_bottom_nav"):
        for column, (name, label, page, _icon) in zip(st.columns(len(DESTINATIONS), gap=None, wrap=False), DESTINATIONS):
            with column, st.container(key=f"wego_nav_{name}"):
                if st.button(label, key=f"bottom_nav_{name}", width="stretch",
                             type="primary" if name == "checkin" else "tertiary"):
                    if name == "checkin":
                        st.session_state['checkin_open_camera'] = True
                    navigate(str(Path(__file__).parent / page))

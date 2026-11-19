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

from theme import button_icons, icon_css, icon_url  # noqa: F401  (icon_url is used by the tests)

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


# URL name of each page (lower case) -> its file.
PAGE_FILES = {"profile": "pages/1_Profile.py", "lobby": "pages/2_Lobby.py", "check_in": "pages/3_Check_in.py",
              "standings": "pages/4_Standings.py", "map": "pages/5_Map.py",
              "check_in_photos": "pages/6_Check_in_photos.py", "minigames": "pages/7_Minigames.py"}
HISTORY_LIMIT = 20


def current_page() -> str | None:
    path = urlsplit(st.context.url or "").path.rstrip("/").rsplit("/", 1)[-1].lower()
    return path if path in PAGE_FILES else None


def track_history(page: str | None) -> list[str]:
    """Remember the pages visited in this session, so Back can return to the last one."""
    history = st.session_state.setdefault("_nav_history", [])
    last = st.session_state.get("_nav_current")
    if page is None or page == last:
        return history
    going_back = st.session_state.pop("_nav_going_back", False)
    if last is not None and not going_back:
        history.append(last)
        del history[:-HISTORY_LIMIT]
    st.session_state["_nav_current"] = page
    return history


def back_button(page: str | None, history: list[str], navigate) -> None:
    """A Back button on every page: the previous page, or the Map when there is none."""
    if page == "minigames" and st.session_state.get("minigame_selected"):
        return  # a game screen has its own "All games" link
    target = history[-1] if history else ("map" if page not in (None, "map") else None)
    if target is None:
        return
    button_icons({"wego_back_btn": "caret-left"})
    with st.container(key="wego_back"):
        if st.button("Back", key="wego_back_btn", type="tertiary"):
            if history:
                history.pop()
            st.session_state["_nav_going_back"] = True
            navigate(str(Path(__file__).parent / PAGE_FILES[target]))


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
    page = current_page()
    back_button(page, track_history(page), navigate)
    with st.container(key="wego_bottom_nav"):
        for column, (name, label, target, _icon) in zip(st.columns(len(DESTINATIONS), gap=None, wrap=False), DESTINATIONS):
            with column, st.container(key=f"wego_nav_{name}"):
                if st.button(label, key=f"bottom_nav_{name}", width="stretch",
                             type="primary" if name == "checkin" else "tertiary"):
                    if name == "checkin":
                        st.session_state['checkin_open_camera'] = True
                    navigate(str(Path(__file__).parent / target))

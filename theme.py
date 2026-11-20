"""Loads the WeGoPub design system (direction "Tennis") on every page.

assets/theme.css holds the colour, type and shape tokens plus the base
styling of Streamlit's own widgets. Page styles in assets/*.css only use
those tokens, so changing the look of the whole app means editing one file.
"""

from base64 import b64encode
from functools import cache
from html import escape
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import declare_component

_ASSETS = Path(__file__).parent / "assets"
_CSS = _ASSETS / "theme.css"
_DARK_CSS = _ASSETS / "theme_dark.css"
_DARK_KEY = "wego_dark_mode"
_theme_switch = declare_component("theme_switch", path=str(Path(__file__).parent / "components" / "theme_switch"))


@cache
def icon_url(name: str) -> str:
    """A Phosphor icon from assets/icons (MIT licence) as a data URL for CSS."""
    svg = (_ASSETS / "icons" / f"{name}.svg").read_bytes()
    return "data:image/svg+xml;base64," + b64encode(svg).decode()


def icon_css(selector: str, name: str) -> str:
    """CSS that draws the icon as a mask, so it takes the element's colour."""
    url = icon_url(name)
    return f'{selector}{{-webkit-mask-image:url("{url}");mask-image:url("{url}");}}'


def menu_icons(icons: dict[str, str]) -> None:
    """Icons for rows of a menu list: {button key: icon name}. See .st-key-menu_list_* in theme.css."""
    css = "".join(icon_css(f".stApp .st-key-{key} button::before", icon) for key, icon in icons.items())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_subtitle(*parts: str) -> None:
    """One quiet line under a page title, e.g. lobby · status."""
    st.markdown(f'<p class="page-subtitle">{escape(" · ".join(p for p in parts if p))}</p>', unsafe_allow_html=True)


def button_icons(icons: dict[str, str]) -> None:
    """A Phosphor icon in front of a normal button's label: {button key: icon name}."""
    base = ('content:"";display:inline-block;flex:0 0 20px;width:20px;height:20px;margin-right:6px;background-color:currentColor;'
            '-webkit-mask:none center/contain no-repeat;mask:none center/contain no-repeat;')
    css = "".join(f".stApp .st-key-{key} button::before{{{base}}}" + icon_css(f".stApp .st-key-{key} button::before", icon)
                  for key, icon in icons.items())
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def dark_mode() -> bool:
    """Whether this player turned on dark mode (remembered in their browser)."""
    return bool(st.session_state.get(_DARK_KEY))


def component_tokens() -> str:
    """The colour/type tokens for components drawn in their own frame (switches,
    duel boards): the light set, plus the dark one when dark mode is on."""
    css = _CSS.read_text(encoding="utf-8")
    tokens = css[css.index(":root {"):css.index("/* Base */")]
    if dark_mode():
        dark = _DARK_CSS.read_text(encoding="utf-8")
        tokens += dark[dark.index(":root {"):dark.index("}", dark.index(":root {")) + 1]
    return tokens


def _sync_dark_mode() -> None:
    """An invisible reader tells this session what the browser remembers.
    It is applied once per visit only: the reader keeps reporting the value it
    read at page load, which must not undo a later tap on the switch."""
    if st.session_state.get("_wego_dark_synced"):
        return
    with st.container(key="theme_reader"):
        saved = _theme_switch(mode="reader", key="theme_reader_frame", default=None)
    if saved not in ("dark", "light"):
        return
    st.session_state["_wego_dark_synced"] = True
    if (saved == "dark") != dark_mode():
        st.session_state[_DARK_KEY] = saved == "dark"
        st.rerun()


def dark_mode_switch() -> None:
    """The visible Dark mode switch (Profile, under Location)."""
    value = _theme_switch(mode="switch", current=dark_mode(), tokens=component_tokens(),
                          key="theme_switch", default=None)
    if value in ("dark", "light") and (value == "dark") != dark_mode():
        st.session_state[_DARK_KEY] = value == "dark"
        st.rerun()


def apply_theme() -> None:
    css = _CSS.read_text(encoding="utf-8")
    css += f':root{{--icon-caret-right:url("{icon_url("caret-right")}");}}'
    if dark_mode():
        css += _DARK_CSS.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    _sync_dark_mode()


def wordmark(name: str = "WeGoPub") -> None:
    """The app name in the display face, in the brand red."""
    st.markdown(f'<p class="wego-wordmark">{escape(name)}</p>', unsafe_allow_html=True)


def empty_state_html(icon: str, title: str, line: str, *, key: str = "") -> str:
    """Icon, title and one line for an empty screen. Every value is escaped;
    the icon is a Phosphor name from assets/icons drawn as a CSS mask, scoped
    to this card so two cards on one page keep their own icons."""
    scope = f".st-key-empty_state_{key} " if key else ""
    mask = icon_css(f"{scope}.empty-state-icon i", icon)
    return (f'<style>{mask}</style>'
            f'<div class="empty-state-icon" aria-hidden="true"><i></i></div>'
            f'<p class="empty-state-title">{escape(title)}</p>'
            f'<p class="empty-state-line">{escape(line)}</p>')


def empty_state(key: str, icon: str, title: str, line: str, *, check_in: bool = False) -> None:
    """One calm card instead of an info box when a screen has nothing yet:
    icon, title, one line, and (optionally) a Check in button that opens the
    camera like the + tab. Scarlet stripe on top (theme.css)."""
    with st.container(key=f"empty_state_{key}"):
        st.markdown(empty_state_html(icon, title, line, key=key), unsafe_allow_html=True)
        if check_in and st.button("Check in", key=f"checkin_from_empty_{key}", type="primary", width="stretch"):
            st.session_state["checkin_open_camera"] = True
            st.switch_page("pages/3_Check_in.py")

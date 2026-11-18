"""Loads the WeGoPub design system (direction "Tennis") on every page.

assets/theme.css holds the colour, type and shape tokens plus the base
styling of Streamlit's own widgets. Page styles in assets/*.css only use
those tokens, so changing the look of the whole app means editing one file.
"""

from html import escape
from pathlib import Path

import streamlit as st

_CSS = Path(__file__).parent / "assets" / "theme.css"


def apply_theme() -> None:
    st.markdown(f"<style>{_CSS.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def wordmark(name: str = "WeGoPub") -> None:
    """The app name in the display face, in the brand red."""
    st.markdown(f'<p class="wego-wordmark">{escape(name)}</p>', unsafe_allow_html=True)

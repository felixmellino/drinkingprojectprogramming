"""Presentation helpers for the Drink Entries block; no game or data rules."""

from html import escape
from pathlib import Path

import streamlit as st


def page_header(title: str, description: str, *, compact: bool = False) -> None:
    """Load page-scoped styles and an accessible heading."""
    css = (Path(__file__).parent / "assets" / "drink_entries.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.markdown(
        f'<header class="drink-page-hero{" drink-camera-hero" if compact else ""}">'
        f'<h1>{escape(title)}</h1><p class="drink-intro">{escape(description)}</p></header>',
        unsafe_allow_html=True,
    )


def section_heading(number: str, title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="drink-section-heading"><h2>{escape(title)}</h2><p>{escape(description)}</p></div>',
        unsafe_allow_html=True,
    )


def context_line(label: str, detail: str) -> None:
    """Escape lobby/user values before inserting them into presentation HTML."""
    st.markdown(
        f'<div class="drink-context"><span>{escape(label)}</span><span>{escape(detail)}</span></div>',
        unsafe_allow_html=True,
    )

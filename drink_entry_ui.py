"""Presentation helpers for the Drink Entries block; no game or data rules."""

from html import escape
from pathlib import Path

import streamlit as st


def page_header(title: str, description: str, *, photos: bool = False, standings: bool = False) -> None:
    """Load page-scoped styles and an accessible heading with decorative art."""
    css = (Path(__file__).parent / "assets" / "drink_entries.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    if standings:
        drawing = '<path d="M38 19h44v25a22 22 0 0 1-44 0ZM38 27H23v11a18 18 0 0 0 18 18m41-29h15v11a18 18 0 0 1-18 18M60 66v24m-19 11h38M47 90h26v11"/><path d="m60 29 3 7 8 1-6 5 2 8-7-4-7 4 2-8-6-5 8-1Z"/>'
    elif photos:
        drawing = '<rect x="20" y="34" width="80" height="60" rx="14"/><path d="m36 34 7-12h34l7 12"/><circle cx="60" cy="64" r="18"/><path d="m92 17 2-7m8 17 7-2"/>'
    else:
        drawing = '<path d="M32 40h49v51a12 12 0 0 1-12 12H44a12 12 0 0 1-12-12Z"/><path d="M81 49h8a13 13 0 0 1 0 26h-8M46 55v31m20-31v31"/><path d="M32 40a11 11 0 0 1 4-21 13 13 0 0 1 23-3 12 12 0 0 1 22 7 9 9 0 0 1 0 17M95 20l3-8m5 18 8-3"/>'
    label = "SEASON STANDINGS" if standings else "LOBBY MOMENTS" if photos else "DRINK ENTRIES"
    st.markdown(
        f'<header class="drink-page-hero"><div><p class="drink-eyebrow">WeGoPub / {label}</p>'
        f'<h1>{escape(title)}</h1><p class="drink-intro">{escape(description)}</p></div>'
        f'<div class="drink-hero-art" aria-hidden="true"><svg viewBox="0 0 120 120" '
        f'fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" '
        f'stroke-linejoin="round" focusable="false">{drawing}</svg></div></header>',
        unsafe_allow_html=True,
    )


def section_heading(number: str, title: str, description: str = "") -> None:
    st.markdown(
        f'<div class="drink-section-heading"><span class="drink-step" aria-hidden="true">{escape(number)}</span>'
        f'<div><h2>{escape(title)}</h2><p>{escape(description)}</p></div></div>',
        unsafe_allow_html=True,
    )


def context_line(label: str, detail: str) -> None:
    """Escape lobby/user values before inserting them into presentation HTML."""
    st.markdown(
        f'<div class="drink-context"><span>{escape(label)}</span><span>{escape(detail)}</span></div>',
        unsafe_allow_html=True,
    )

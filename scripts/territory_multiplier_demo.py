"""Local visual demo of the proposed territory boost, using synthetic scores."""

from datetime import datetime, timezone
from html import escape
from math import ceil
from random import choice
from time import monotonic

import streamlit as st

import map_ui
from core.models import DrinkEntry
from core.scoring_v1 import TERRITORY_MULTIPLIER as BOOST
from core.territory_geometry import boost_candidates
from data.territory_file import load_territories


TRIGGER_ID = "shortys"
DURATION = 15 * 60


@st.cache_data
def demo_map():
    territories = load_territories()
    fixtures = [(TRIGGER_ID, "ana", 8), (TRIGGER_ID, "me", 5),
                ("le-pub", "me", 7), ("party-street", "leo", 6), ("rua-da-rosa", "ana", 4)]
    entries = [
        DrinkEntry(id=str(index), membership_id=player, season_id="demo", drink_type="beer",
                   amount=None, photo_ref="", device_gps=None, photo_gps=None,
                   territory_id=area, location_check_result="matched", points_awarded=points,
                   submitted_at=datetime(2026, 11, 21, 20, index, tzinfo=timezone.utc))
        for index, (area, player, points) in enumerate(fixtures)
    ]
    rows = map_ui.territory_rows(territories, entries, "me", {"me": "You", "ana": "Ana", "leo": "Leo"})
    return rows, boost_candidates(territories, TRIGGER_ID)


def reset_draw(candidates):
    st.session_state.boost_demo_territory = choice(candidates)
    st.session_state.boost_demo_ends_at = monotonic() + DURATION


def preview_expiry():
    st.session_state.boost_demo_ends_at = monotonic() + 10


st.set_page_config(page_title="WeGoPub · Territories", layout="wide")
st.session_state["wego_dark_mode"] = True
st.markdown("""
<style>
.stApp { background:#111718; }
[data-testid="stHeader"] { visibility:hidden; }
[data-testid="stMainBlockContainer"] { max-width:1020px; padding:1.2rem 1.2rem 1.6rem; }
[data-testid="stMainBlockContainer"] > div { gap:.75rem; }
.demo-header { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
.demo-header > div { display:flex; align-items:baseline; gap:.8rem; flex-wrap:wrap; }
.demo-header h1 { padding:0; color:#fafaf4; font-size:clamp(1.65rem,5vw,2.2rem); line-height:1.15; letter-spacing:-.045em; }
.demo-brand { color:#ffce76; font-size:.9rem; font-weight:750; }
.demo-lobby { color:#b8c3c2; font-size:.85rem; white-space:nowrap; }
.st-key-boost_demo_map { position:relative; overflow:hidden; border:1px solid #374140; border-radius:20px; background:#1a2223; }
.map-legend { display:flex; flex-wrap:wrap; gap:.9rem; color:#aebcbb; padding:0 .3rem; font-size:.8rem; }
.map-legend span { display:inline-flex; align-items:center; gap:.36rem; }
.map-legend i { width:8px; height:8px; border-radius:2px; }
.score-card { background:#1b2425; border:1px solid #374140; border-radius:16px; padding:14px 16px; color:#f4f3ea; }
.score-header { display:flex; align-items:start; gap:.5rem; justify-content:space-between; margin-bottom:.65rem; }
.score-header h2 { padding:0; color:#f4f3ea; font-size:1.14rem; line-height:1.2; font-weight:750; }
.score-card p { margin:0; color:#b8c3c2; font-size:.88rem; }
.score-owner { text-align:right; }
.sample-award { color:#f4f3ea; font-weight:650; }
.sample-award strong { color:#ffce76; }
.demo-sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
.stApp button[data-testid^="stBaseButton-secondary"] { background:#1b2425; border:1px solid #495654; color:#e3eae8; }
.stApp button[data-testid^="stBaseButton-secondary"]:hover { background:#283534; border-color:#ffce76; color:#ffce76; }
@media (max-width:480px) {
  [data-testid="stMainBlockContainer"] { padding-left:.8rem; padding-right:.8rem; }
  .demo-header > div { gap:.25rem .55rem; }
  .score-owner { max-width:50%; }
}
</style>
<header class="demo-header"><div><span class="demo-brand">WeGoPub</span><h1>Territories</h1></div>
<span class="demo-lobby">Sample lobby</span></header>
""", unsafe_allow_html=True)

rows, candidates = demo_map()
st.session_state.setdefault("boost_demo_territory", TRIGGER_ID)
st.session_state.setdefault("boost_demo_ends_at", monotonic() + DURATION)
territory_id = st.session_state.boost_demo_territory
territory = next(row for row in rows if row["id"] == territory_id)
ends_at = st.session_state.boost_demo_ends_at
active = ends_at > monotonic()


@st.fragment(run_every=1 if active else None)
def map_and_score():
    seconds = max(0, ceil(ends_at - monotonic()))
    if active and seconds == 0:
        st.rerun()
    minutes, remainder = divmod(seconds, 60)
    label = f"{BOOST:g}x\n{minutes:02d}:{remainder:02d}"
    with st.container(key="boost_demo_map"):
        focus = "Bairro Alto" if territory_id in map_ui.AREAS["Bairro Alto"] else territory_id
        tapped = map_ui.render_map(rows, None, None, focus=focus, context="boost-demo", height=420,
                                   boost=(territory_id, label) if active else None)
    st.markdown(
        '<div class="map-legend"><span><i style="background:#2c99d6"></i>Yours</span>'
        '<span><i style="background:#eb2f33"></i>Rival</span>'
        '<span><i style="background:#8a97a6"></i>Unclaimed</span>'
        '<span><i style="background:#ffce76"></i>Territory boost</span></div>',
        unsafe_allow_html=True,
    )

    selected = next((row for row in rows if row["id"] == tapped), territory)
    boosted = active and selected["id"] == territory_id
    award = 4 * BOOST if boosted else 4
    if selected["status"] == "theirs":
        owner = f'Owner earns {award * 0.25:g} season points.'
    else:
        owner = ""
    accessible_timer = (f'<span class="demo-sr-only" role="timer">{escape(territory["name"])} '
                        f'boost ends in {minutes:02d}:{remainder:02d}</span>') if active else ""
    st.markdown(
        f'<section class="score-card"><div class="score-header"><div><h2>{escape(selected["name"])}</h2>'
        f'<p>{escape(selected["detail"])}</p></div><p class="score-owner">{owner}</p></div>'
        f'<p>Sample check-in · 4 base points <span class="sample-award">→ <strong>{award:g} season points'
        f' and {award:g} territory points</strong></span></p>{accessible_timer}</section>',
        unsafe_allow_html=True,
    )
    if not active:
        st.info("Territory boost expired. Ordinary scoring has resumed.")


map_and_score()
replay, expiry = st.columns(2)
replay.button("Replay random draw", on_click=reset_draw, args=(candidates,), width="stretch")
expiry.button("Preview last 10 seconds", on_click=preview_expiry, width="stretch")

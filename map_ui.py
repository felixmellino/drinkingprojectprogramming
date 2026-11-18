"""Map page presentation: territories coloured by owner, your position.

Ownership and the capture gap come from core/territories.py; this file only
turns them into map shapes, colours and text. No game rules live here.
"""

from __future__ import annotations

import math
import re
import unicodedata
from html import escape
from pathlib import Path

import pydeck as pdk
import streamlit as st

from core.territories import capture_status, territory_owner, territory_standings

# Colour = what the territory means for you (RGB). Same values as the
# --territory-* tokens in assets/theme.css (design system "Rush").
COLOURS = {
    "yours": [76, 195, 138],    # #4CC38A green
    "theirs": [255, 93, 82],    # #FF5D52 red
    "free": [126, 136, 156],    # #7E889C grey
}
FILL_ALPHA = {"yours": 125, "theirs": 120, "free": 55}
LEGEND = {"yours": "Yours", "theirs": "Someone else's", "free": "Unclaimed"}
HOVER_COLOUR = [255, 255, 255, 70]  # lightens the area under the pointer

# Quick-zoom buttons: which territory ids belong to which part of the city.
# Ids that aren't in the territory file are simply skipped.
_BAIRRO_ALTO = ["rua-dos-mouros", "cheers-irish-pub", "le-pub", "shortys",
                "party-street", "outer-bairro", "rua-da-rosa", "autschan"]
AREAS = {
    "Bairro Alto": _BAIRRO_ALTO,
    "Lisbon": _BAIRRO_ALTO + [
        "santa-catarina", "tower-bar", "santos-kiosk", "after8", "principe-real",
        "praca-das-flores", "sao-bento", "madragoa", "calcada-do-combro", "bica",
        "sao-paulo", "time-out-market", "pink-street", "chiado", "sao-pedro-de-alcantara"],
    "Nova SBE": ["nova-sbe"],
}
ME = ":material/my_location: Me"
ALL = "All"


def load_styles() -> None:
    """Game-style page: dark background, floating HUD and card (assets/game_map.css)."""
    css = (Path(__file__).parent / "assets" / "game_map.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def hud(lobby_name: str, rows: list[dict]) -> None:
    """Top bar floating over the map: lobby and how many territories you hold."""
    numbers = summary(rows)
    st.markdown(
        f'<div class="game-hud"><div><small>Lobby</small><strong>{escape(lobby_name)}</strong></div>'
        f'<div class="game-score"><small>Yours</small><strong>{numbers["yours"]}</strong>'
        f' / {numbers["total"]} · {numbers["free"]} free</div></div>',
        unsafe_allow_html=True,
    )


def location_card(here: dict | None, status: str, accuracy_m: float | None = None) -> None:
    """Bottom card floating over the map: where you are and what it means.
    status: "matched", "outside", "inaccurate", "denied" or "waiting"."""
    if status == "matched" and here:
        tone = {"yours": "game-yours", "theirs": "game-theirs"}.get(here["status"], "")
        body = (f'<small>You are in</small><h3>{escape(here["name"])}</h3>'
                f'<p class="{tone}">{escape(here["detail"])}</p>')
    elif status == "outside":
        body = "<small>You are</small><h3>Outside the map</h3><p>Drinks here count for season points only.</p>"
    elif status == "inaccurate":
        body = (f"<small>Location</small><h3>Not precise enough</h3>"
                f"<p>Accurate to about {accuracy_m:.0f} m, we need 50 m. Step outside for a moment.</p>")
    elif status == "denied":
        body = "<small>Location</small><h3>Location is blocked</h3><p>Allow location for this site in your browser settings.</p>"
    else:
        body = "<small>Location</small><h3>Finding you…</h3><p>Allow location access if your browser asks.</p>"
    st.markdown(f'<div class="game-card">{body}</div>', unsafe_allow_html=True)


def legend() -> None:
    st.markdown(
        '<div class="game-legend">'
        f'<span><i style="background:rgb{tuple(COLOURS["yours"])}"></i>Yours</span>'
        f'<span><i style="background:rgb{tuple(COLOURS["theirs"])}"></i>Someone else\'s</span>'
        f'<span><i style="background:rgb{tuple(COLOURS["free"])}"></i>Unclaimed</span></div>',
        unsafe_allow_html=True,
    )


def _label(text: str) -> str:
    # The map's label font only has plain letters, so drop accents on the map.
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def markdown_safe(text: str) -> str:
    """Usernames are free text: stop them from being read as Markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", text)


def territory_rows(territories, entries, me: str, names: dict) -> list[dict]:
    """One row per territory with everything the map and list show."""
    rows = []
    for territory in territories:
        owner = territory_owner(entries, territory.id)
        standings = territory_standings(entries, territory.id)
        status, number = capture_status(standings, owner, me)
        needed = number if status == "theirs" else None
        my_points = dict(standings).get(me, 0)
        owner_name = names.get(owner, "Unknown player") if owner else "Nobody"
        if status == "free":
            detail = "Unclaimed: your next drink here claims it."
        elif status == "yours":
            detail = f"Yours: you lead by {number} point{'s' if number != 1 else ''}."
        else:
            detail = f"Owned by {owner_name}: you need {number} more point{'s' if number != 1 else ''} to take it."
        rows.append({
            "id": territory.id,
            "name": territory.name,
            "status": status,
            "owner": owner_name,
            "my_points": my_points,
            "needed": needed,
            "detail": detail,
            "boundary": territory.boundary,
        })
    return rows


def summary(rows: list[dict]) -> dict:
    """Numbers for the cards above the map. 'easiest' is the territory someone
    else owns that needs the fewest points to take (None if there's none)."""
    yours = sum(1 for row in rows if row["status"] == "yours")
    free = sum(1 for row in rows if row["status"] == "free")
    theirs = [row for row in rows if row["status"] == "theirs"]
    easiest = None
    if theirs:
        best = min(theirs, key=lambda row: (row["needed"], row["name"]))
        easiest = (best["name"], best["needed"])
    return {"yours": yours, "total": len(rows), "free": free, "easiest": easiest}


def view_for(rows: list[dict], focus: str, location: tuple[float, float] | None) -> pdk.ViewState:
    """Where the map starts: on you, or zoomed to fit one part of the city."""
    if focus == ME and location is not None:
        return pdk.ViewState(latitude=location[0], longitude=location[1], zoom=15.5)
    ids = set(AREAS.get(focus, []))
    points = [p for row in rows if row["id"] in ids for p in row["boundary"]["coordinates"][0]]
    if not points:  # "All" (or an unknown area): fit every territory
        points = [p for row in rows for p in row["boundary"]["coordinates"][0]]
    lngs, lats = [p[0] for p in points], [p[1] for p in points]
    # Zoom so the area's width and height fit the map (~420 x 480 px; a bit
    # of it may run off a narrow phone screen, which is fine).
    # The map library draws the whole world 512 px wide at zoom 0.
    span_lng = max(max(lngs) - min(lngs), 1e-4)
    span_lat = max(max(lats) - min(lats), 1e-4) / math.cos(math.radians(sum(lats) / len(lats)))
    zoom = min(math.log2(420 * 360 / (512 * span_lng)), math.log2(480 * 360 / (512 * span_lat))) - 0.2
    return pdk.ViewState(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lngs) + max(lngs)) / 2,
                         zoom=max(9.0, min(zoom, 17.0)))


def render_map(rows: list[dict], location: tuple[float, float] | None, accuracy_m: float | None,
               focus: str = "Bairro Alto") -> None:
    features = [
        {
            "type": "Feature",
            "geometry": row["boundary"],
            "properties": {
                # The tooltip is HTML, and usernames are free text: escape them.
                "name": escape(row["name"]),
                "detail": escape(row["detail"]),
                "points": f"Your points here: {row['my_points']}",
                "fill": COLOURS[row["status"]] + [FILL_ALPHA[row["status"]]],
                "line": COLOURS[row["status"]] + [235 if row["status"] != "free" else 120],
            },
        }
        for row in rows
    ]
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            {"type": "FeatureCollection", "features": features},
            pickable=True,
            auto_highlight=True,
            highlight_color=HOVER_COLOUR,
            stroked=True,
            filled=True,
            get_fill_color="properties.fill",
            get_line_color="properties.line",
            line_width_min_pixels=2.5,
        )
    ]
    # Territory names written on the map, like place names in a game.
    labels = [{"position": _centre(row["boundary"]), "name": _label(row["name"])} for row in rows]
    layers.append(pdk.Layer(
        "TextLayer", labels, get_position="position", get_text="name", get_size=11,
        get_color=[240, 225, 206, 240], get_text_anchor="'middle'", get_alignment_baseline="'center'",
        font_weight=700, font_settings={"sdf": True}, outline_width=3, outline_color=[26, 40, 65, 235],
    ))
    if location is not None:
        here = [{"lng": location[1], "lat": location[0], "radius": accuracy_m or 0}]
        layers += [
            pdk.Layer("ScatterplotLayer", here, get_position="[lng, lat]", get_radius="radius",
                      get_fill_color=[90, 168, 255, 45], stroked=False),
            pdk.Layer("ScatterplotLayer", here, get_position="[lng, lat]", get_radius=1,
                      radius_min_pixels=8, get_fill_color=[90, 168, 255, 255],
                      get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=3),
        ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_for(rows, focus, location),
            map_provider="carto",
            map_style="dark",  # Carto "Dark Matter": game-like night map
            tooltip={"html": "<b>{name}</b><br/>{detail}<br/>{points}"},
        ),
        height=600,
    )


def _centre(boundary: dict) -> list[float]:
    ring = boundary["coordinates"][0][:-1]
    return [sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)]


def territory_list(rows: list[dict]) -> None:
    """The same information as the map, as a table (SCREENS.md: map alternative)."""
    order = {"yours": 0, "theirs": 1, "free": 2}
    st.dataframe(
        [
            {"Territory": row["name"], "Status": LEGEND[row["status"]], "Owner": row["owner"],
             "Your points": row["my_points"], "What it means": row["detail"]}
            for row in sorted(rows, key=lambda r: (order[r["status"]], r["name"]))
        ],
        hide_index=True,
        width="stretch",
    )

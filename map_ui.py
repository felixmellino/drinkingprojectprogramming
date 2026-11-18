"""Map page presentation: territories coloured by owner, your position.

Ownership and the capture gap come from core/territories.py; this file only
turns them into map shapes, colours and text. No game rules live here.
"""

from __future__ import annotations

import math
import re
from html import escape

import pydeck as pdk
import streamlit as st

from core.territories import capture_status, territory_owner, territory_standings

# Colour = what the territory means for you (RGBA).
COLOURS = {
    "yours": [29, 158, 117, 150],   # green
    "theirs": [226, 75, 74, 140],   # red
    "free": [180, 178, 169, 110],   # grey
}
LEGEND = {"yours": "🟢 Yours", "theirs": "🔴 Someone else's", "free": "⚪ Unclaimed"}
HOVER_COLOUR = [255, 196, 0, 170]  # amber, on the area under the pointer

# Quick-zoom buttons: which territory ids belong to which part of the city.
# Ids that aren't in the territory file are simply skipped.
AREAS = {
    "Bairro Alto": ["rua-dos-mouros", "cheers-irish-pub", "le-pub", "shortys",
                    "party-street", "outer-bairro", "rua-da-rosa", "autschan"],
    "Santos": ["santa-catarina", "tower-bar", "santos-kiosk", "after8"],
    "Nova SBE": ["nova-sbe"],
}
ME = "📍 Me"


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


def render_summary(rows: list[dict]) -> None:
    numbers = summary(rows)
    owned, free, easiest = st.columns(3)
    owned.metric("Yours", f"{numbers['yours']} of {numbers['total']}")
    free.metric("Unclaimed", numbers["free"], help="Your next drink in one of these claims it.")
    if numbers["easiest"]:
        name, needed = numbers["easiest"]
        easiest.metric("Easiest to take", name, f"{needed} point{'s' if needed != 1 else ''} needed",
                       delta_color="off")
    else:
        easiest.metric("Easiest to take", "—")


def view_for(rows: list[dict], focus: str, location: tuple[float, float] | None) -> pdk.ViewState:
    """Where the map starts: on you, or zoomed to fit one part of the city."""
    if focus == ME and location is not None:
        return pdk.ViewState(latitude=location[0], longitude=location[1], zoom=15.5)
    ids = set(AREAS.get(focus, []))
    points = [p for row in rows if row["id"] in ids for p in row["boundary"]["coordinates"][0]]
    if not points:  # unknown area: show everything
        points = [p for row in rows for p in row["boundary"]["coordinates"][0]]
    lngs, lats = [p[0] for p in points], [p[1] for p in points]
    # Zoom so the area's width and height fit a phone-sized map (~340 x 400 px).
    # The map library draws the whole world 512 px wide at zoom 0.
    span_lng = max(max(lngs) - min(lngs), 1e-4)
    span_lat = max(max(lats) - min(lats), 1e-4) / math.cos(math.radians(sum(lats) / len(lats)))
    zoom = min(math.log2(340 * 360 / (512 * span_lng)), math.log2(400 * 360 / (512 * span_lat))) - 0.2
    return pdk.ViewState(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lngs) + max(lngs)) / 2,
                         zoom=max(11.0, min(zoom, 17.0)))


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
                "fill": COLOURS[row["status"]],
                "line": COLOURS[row["status"]][:3] + [255],
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
            line_width_min_pixels=1.5,
        )
    ]
    if location is not None:
        here = [{"lng": location[1], "lat": location[0], "radius": accuracy_m or 0}]
        layers += [
            pdk.Layer("ScatterplotLayer", here, get_position="[lng, lat]", get_radius="radius",
                      get_fill_color=[24, 95, 165, 40], stroked=False),
            pdk.Layer("ScatterplotLayer", here, get_position="[lng, lat]", get_radius=1,
                      radius_min_pixels=7, get_fill_color=[24, 95, 165, 255],
                      get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=2),
        ]
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_for(rows, focus, location),
            map_provider="carto",
            map_style="light",
            tooltip={"html": "<b>{name}</b><br/>{detail}<br/>{points}"},
        ),
        height=460,
    )
    st.caption(" · ".join(LEGEND.values()) + (" · 🔵 You" if location is not None else ""))


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

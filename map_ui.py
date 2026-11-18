"""Map page presentation: territories coloured by owner, your position.

Ownership and the capture gap come from core/territories.py; this file only
turns them into map shapes, colours and text. No game rules live here.
"""

from __future__ import annotations

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
            "detail": detail,
            "boundary": territory.boundary,
        })
    return rows


def render_map(rows: list[dict], location: tuple[float, float] | None, accuracy_m: float | None) -> None:
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
    # Centre of all 12 territories (Santos to Bairro Alto), wide enough for phones.
    view = pdk.ViewState(latitude=38.7094, longitude=-9.1500, zoom=13.7)
    if location is not None:
        view = pdk.ViewState(latitude=location[0], longitude=location[1], zoom=15)
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view,
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

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
from core.scoring_v1 import replay_season, format_points
from map_markers import owner_markers

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
    snapshot = replay_season(entries) if any(e.rule_version == "v1" for e in entries) else None
    point_step = .5 if any(e.focus_attempt_id for e in entries) else 1
    for territory in territories:
        owner = snapshot.owners.get(territory.id) if snapshot else territory_owner(entries, territory.id)
        standings = snapshot.territory_rows(territory.id) if snapshot else territory_standings(entries, territory.id)
        status, number = capture_status(standings, owner, me, point_step=point_step)
        needed = number if status == "theirs" else None
        my_points = dict(standings).get(me, 0)
        owner_name = names.get(owner, "Unknown player") if owner else "Nobody"
        if status == "free":
            detail = "Unclaimed: your next drink here claims it."
        elif status == "yours":
            detail = f"Yours: you lead by {format_points(number)} point{'s' if number != 1 else ''}."
        else:
            detail = f"Owned by {owner_name}: you need {format_points(number)} more point{'s' if number != 1 else ''} to take it."
        rows.append({
            "id": territory.id,
            "name": territory.name,
            "status": status,
            "owner": owner_name,
            "owner_id": owner,
            "owner_points": dict(standings).get(owner, 0),
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


def _map_selection_changed():
    st.session_state["_map_open_popup"] = True


def selected_territories(selection, rows, markers):
    """Resolve browser selection by index against fresh server-side data only."""
    indices = selection.get("indices", {})
    ids = set()
    for layer, data in (("owner-badges", markers), ("territories", rows)):
        for index in indices.get(layer, []):
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(data):
                ids.update(data[index]["territory_ids"] if layer == "owner-badges" else [data[index]["id"]])
    return [row for row in rows if row["id"] in ids]


def _clear_map_selection():
    # Streamlit selections are read-only. A fresh widget key clears the old
    # selection so the same badge can be opened again after closing its dialog.
    st.session_state["_map_selection_version"] = st.session_state.get("_map_selection_version", 0) + 1


@st.dialog("Territory points", on_dismiss=_clear_map_selection)
def territory_popup(rows, team_mode=False):
    st.markdown(f'<p>Current owner: <strong>{escape(rows[0]["owner"])}</strong></p>', unsafe_allow_html=True)
    body = "".join(f'<tr><th scope="row">{escape(row["name"])}</th>'
                   f'<td>{row["owner_points"]}</td><td>{row["my_points"]}</td></tr>' for row in rows)
    st.markdown('<div class="map-points-scroll"><table class="map-points-table">'
                '<thead><tr><th scope="col">Territory</th><th scope="col">Owner points</th>'
                f'<th scope="col">{"Your team’s points" if team_mode else "Your points"}</th></tr></thead>'
                f'<tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
    if len(rows) == 1:
        st.caption(rows[0]["detail"])
    st.caption("Only territory points count here; season owner income is excluded.")


def render_map(rows: list[dict], location: tuple[float, float] | None, accuracy_m: float | None,
               focus: str = "Bairro Alto", *, pictures=None, team_mode=False, context="map") -> None:
    features = [
        {
            "type": "Feature",
            "geometry": row["boundary"],
            "properties": {
                # The tooltip is HTML, and usernames are free text: escape them.
                "name": escape(row["name"]),
                "detail": escape(row["detail"]),
                "points": f"Owner: {escape(row['owner'])} · {row['owner_points']} points · "
                          f"{'Your team’s' if team_mode else 'Your'} points here: {row['my_points']}",
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
            id="territories",
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
    markers = owner_markers(rows, pictures or {}, COLOURS)
    # Marker tooltip strings are HTML too; the unescaped owner name stays server-side.
    for marker in markers:
        marker["name"] = escape(marker["name"])
    layers += [
        pdk.Layer("IconLayer", markers, id="owner-badges", get_position="position", get_icon="icon",
                  get_size="size", size_units="meters", size_min_pixels=12, size_max_pixels=52,
                  pickable=True, billboard=True),
        pdk.Layer("TextLayer", markers, id="owner-initials", get_position="position", get_text="initials",
                  get_size="text_size", size_units="meters", size_min_pixels=6, size_max_pixels=16,
                  get_color=[255, 255, 255, 255], font_weight=800, billboard=True,
                  get_text_anchor="'middle'", get_alignment_baseline="'center'", pickable=False),
    ]
    # Territory names written on the map, like place names in a game.
    labels = [{"position": _centre(row["boundary"]), "name": _label(row["name"]),
               "offset": [0, 34] if row.get("owner_id") else [0, 0]} for row in rows]
    layers.append(pdk.Layer(
        "TextLayer", labels, id="territory-labels", get_position="position", get_text="name", get_size=11,
        get_pixel_offset="offset",
        get_color=[240, 225, 206, 240], get_text_anchor="'middle'", get_alignment_baseline="'center'",
        font_weight=700, font_settings={"sdf": True}, outline_width=3, outline_color=[26, 40, 65, 235],
    ))
    if location is not None:
        here = [{"lng": location[1], "lat": location[0], "radius": accuracy_m or 0}]
        layers += [
            pdk.Layer("ScatterplotLayer", here, id="gps-accuracy", get_position="[lng, lat]", get_radius="radius",
                      get_fill_color=[90, 168, 255, 45], stroked=False),
            pdk.Layer("ScatterplotLayer", here, id="gps-position", get_position="[lng, lat]", get_radius=1,
                      radius_min_pixels=8, get_fill_color=[90, 168, 255, 255],
                      get_line_color=[255, 255, 255, 255], stroked=True, line_width_min_pixels=3),
        ]
    event = st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_for(rows, focus, location),
            map_provider="carto",
            map_style="dark",  # Carto "Dark Matter": game-like night map
            tooltip={"html": "<b>{name}</b><br/>{detail}<br/>{points}"},
        ),
        height=600,
        key=f"territory_map:{context}:{st.session_state.get('_map_selection_version', 0)}",
        on_select=_map_selection_changed,
        selection_mode="single-object",
    )
    if st.session_state.pop("_map_open_popup", False):
        selected = selected_territories(event.selection, rows, markers)
        if selected:
            territory_popup(selected, team_mode)


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

"""Map page presentation: territories coloured by owner, your position.

Ownership and the capture gap come from core/territories.py; this file only
turns them into map shapes, colours and text. No game rules live here.
"""

from __future__ import annotations

import math
import re
from html import escape
from pathlib import Path

import pydeck as pdk
import streamlit as st
from streamlit.components.v1 import declare_component
from streamlit.errors import StreamlitInvalidLayoutContextError

from theme import component_tokens, dark_mode

from core.territories import capture_status, territory_owner, territory_standings
from core.scoring_v1 import replay_season, format_points
from core.profile_photo import initials
from map_markers import boost_badge, interior_anchor, owner_markers

# Colour = what the territory means for you (RGB). Same values as the
# --territory-* tokens in assets/theme.css (design system "Tennis").
COLOURS = {
    "yours": [44, 153, 214],    # #2C99D6 Sky Blue
    "theirs": [235, 47, 51],    # #EB2F33 Scarlet Red
    "free": [138, 151, 166],    # #8A97A6 grey
}
# Soft translucent fills with a thin outline in the same colour (light basemap,
# like Citymapper / Strava): the colour says who owns it, the map stays readable.
FILL_ALPHA = {"yours": 80, "theirs": 80, "free": 22}
LINE_ALPHA = {"yours": 235, "theirs": 235, "free": 150}
LEGEND = {"yours": "Yours", "theirs": "Someone else's", "free": "Unclaimed"}
HOVER_COLOUR = [20, 43, 61, 28]      # darkens the area under the pointer (light map)
HOVER_COLOUR_DARK = [255, 255, 255, 60]

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
    "Nova SBE": ["nova-sbe", "carcavelos-centro", "rebelva"],
    "Jamor Golf": ["jamor-golf"],
}
ME = ":material/my_location: Me"
ALL = "All"


def load_styles() -> None:
    """Game-style page: dark background, floating HUD and card (assets/game_map.css)."""
    css = (Path(__file__).parent / "assets" / "game_map.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def hud(lobby_name: str, rows: list[dict]) -> None:
    """Slim bar floating over the map: the lobby, and how many territories
    are yours, a rival's and free. The coloured numbers double as the legend."""
    numbers = summary(rows)
    rivals = numbers["total"] - numbers["yours"] - numbers["free"]
    st.markdown(
        f'<div class="game-hud"><strong class="game-hud-lobby">{escape(lobby_name)}</strong>'
        f'<span class="game-hud-counts"><b class="game-yours">{numbers["yours"]}</b> yours'
        f'<b class="game-theirs">{rivals}</b> rivals'
        f'<b class="game-free">{numbers["free"]}</b> free</span></div>',
        unsafe_allow_html=True,
    )


def map_style() -> str:
    return "dark_no_labels" if dark_mode() else "light_no_labels"


def selection_card(selected: dict | None, here: dict | None = None) -> bool:
    """The bottom card: the selected territory's tug-of-war, or nothing at all
    (nothing is selected by default). The grey handle on top closes it; returns
    True when it was tapped. "You are here" only when you stand in that area."""
    if selected is None:
        return False
    closed = st.button("Close", key="map_card_close", help="Close", width="stretch")
    standing_in = here is not None and here["id"] == selected["id"]
    st.markdown(f'<div class="game-card">{territory_card(selected, standing_in=standing_in)}</div>',
                unsafe_allow_html=True)
    return closed


def _title(name: str, sub: str) -> str:
    """Territory name in plain bold with one small line under it (layout A)."""
    return (f'<div class="tug-title"><h3>{escape(name)}</h3>'
            f'<p class="tug-sub">{escape(sub)}</p></div>')


def territory_card(row: dict, *, standing_in: bool = False) -> str:
    """Card body for one territory: the tug-of-war when someone owns it, one
    line when it's unclaimed. standing_in adds "You are here" to the sub line."""
    if row["status"] in ("yours", "theirs"):
        return tug_of_war(row, standing_in=standing_in)
    sub = "Unclaimed. You are here" if standing_in else "Unclaimed"
    return _title(row["name"], f"{sub}. Your next drink here claims it.")


def tug_of_war(here: dict, *, standing_in: bool = True) -> str:
    """Compact card for an owned territory (layout A): name with "Owned by X"
    under it, a small pill on the right (points to take it, or your lead) and
    a thin bar of you against the owner / your closest rival with the two
    scores under it. The full sentence stays as screen-reader text."""
    me = here["my_points"]
    if here["status"] == "theirs":
        rival_name, rival = here["owner"], here["owner_points"]
        sub = f"Owned by {rival_name}"
        pill, tone = f"+{format_points(here['needed'])} to take it", "tug-pill-theirs"
    else:
        rivals = [r for r in here["ranking"] if not r["you"]]
        rival_name, rival = (rivals[0]["name"], rivals[0]["points"]) if rivals else ("No rival yet", 0)
        sub = "Yours"
        pill, tone = f"+{format_points(me - rival)} lead", "tug-pill-yours"
    if standing_in:
        sub += ". You are here"
    total = me + rival
    share = 50 if total <= 0 else round(100 * float(me) / float(total))
    return (
        f'<div class="tug-head">{_title(here["name"], sub)}'
        f'<span class="tug-pill {tone}">{escape(pill)}</span></div>'
        f'<div class="tug-bar" aria-hidden="true"><i class="tug-you" style="width:{share}%"></i>'
        f'<i class="tug-rival" style="width:{100 - share}%"></i></div>'
        f'<div class="tug-labels" aria-hidden="true"><span class="game-yours">You {escape(format_points(me))}</span>'
        f'<span class="game-theirs">{escape(rival_name)} {escape(format_points(rival))}</span></div>'
        f'<p class="sr-only">{escape(here["detail"])}</p>'
    )


def markdown_safe(text: str) -> str:
    """Usernames are free text: stop them from being read as Markdown."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|<>~$])", r"\\\1", text)


def territory_rows(territories, entries, me: str, names: dict) -> list[dict]:
    """One row per territory with everything the map and list show."""
    rows = []
    snapshot = replay_season(entries) if any(e.rule_version == "v1" for e in entries) else None
    if any(e.territory_boost_id or e.focus_multiplier == 1.25 for e in entries):
        point_step = .25
    else:
        point_step = .5 if any(e.focus_attempt_id for e in entries) else 1
    for territory in territories:
        owner = snapshot.owners.get(territory.id) if snapshot else territory_owner(entries, territory.id)
        standings = snapshot.territory_rows(territory.id) if snapshot else territory_standings(entries, territory.id)
        status, number = capture_status(standings, owner, me, point_step=point_step)
        needed = number if status == "theirs" else None
        my_points = dict(standings).get(me, 0)
        owner_name = names.get(owner, "Unknown player") if owner else "Nobody"
        # The standings are already in ranking order (ties: who reached the score first).
        ranking = [{"id": who, "name": names.get(who, "Unknown player"), "points": points, "you": who == me}
                   for who, points in standings]
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
            "ranking": ranking,
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
    ids = set(AREAS.get(focus, [])) or ({focus} if any(row["id"] == focus for row in rows) else set())
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
    single = len(ids) == 1   # one territory picked from the list: a little room around it
    return pdk.ViewState(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lngs) + max(lngs)) / 2,
                         zoom=max(9.0, min(zoom - (0.6 if single else 0), 16.5 if single else 17.0)))


def render_map(rows: list[dict], location: tuple[float, float] | None, accuracy_m: float | None,
               focus: str = "Bairro Alto", *, pictures=None, context="map", selected: str | None = None,
               boost: tuple[str, str] | None = None, height: int = 600) -> str | None:
    """Draw the map and return the id of the territory the player tapped
    (None when nothing is selected; tapping empty map space clears it)."""
    features = [
        {
            "type": "Feature",
            "geometry": row["boundary"],
            "properties": {
                # Only the id goes to the browser: the card is built server-side.
                "id": row["id"],
                "fill": COLOURS[row["status"]] + [FILL_ALPHA[row["status"]]],
                "line": COLOURS[row["status"]] + [LINE_ALPHA[row["status"]]],
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
            highlight_color=HOVER_COLOUR_DARK if dark_mode() else HOVER_COLOUR,
            stroked=True,
            filled=True,
            get_fill_color="properties.fill",
            get_line_color="properties.line",
            line_width_min_pixels=1.5,
        )
    ]
    picked = [f for f in features if f["properties"]["id"] == selected]
    if picked:   # the selected area gets a thicker outline in its own colour, drawn on top
        layers.append(pdk.Layer(
            "GeoJsonLayer", {"type": "FeatureCollection", "features": picked}, id="selected-outline",
            pickable=False, stroked=True, filled=False,
            get_line_color=COLOURS[next(r["status"] for r in rows if r["id"] == selected)] + [255],
            line_width_min_pixels=3.5))
    markers = owner_markers(rows, pictures or {}, COLOURS)
    for marker in markers:
        marker["name"] = escape(marker["name"])  # never rendered as HTML, escaped anyway
    layers += [
        pdk.Layer("IconLayer", markers, id="owner-badges", get_position="position", get_icon="icon",
                  get_size="size", size_units="meters", size_min_pixels=12, size_max_pixels=52,
                  pickable=False, billboard=True),
        pdk.Layer("TextLayer", markers, id="owner-initials", get_position="position", get_text="initials",
                  get_size="text_size", size_units="meters", size_min_pixels=6, size_max_pixels=16,
                  get_color=[255, 255, 255, 255], font_weight=800, billboard=True,
                  get_text_anchor="'middle'", get_alignment_baseline="'center'", pickable=False),
    ]
    if boost is not None:
        territory_id, label = boost
        boosted = next((feature for feature in features if feature["properties"]["id"] == territory_id), None)
        if boosted is not None:
            position, _ = interior_anchor(boosted["geometry"])
            layers += [
                pdk.Layer("GeoJsonLayer", [boosted], id="boost-outline", pickable=False,
                          filled=True, stroked=True, get_fill_color=[255, 194, 91, 65],
                          get_line_color=[255, 198, 98, 255], line_width_min_pixels=2.5),
                pdk.Layer("IconLayer", [{"position": position, "label": label, "icon": boost_badge(label)}],
                          id="boost-label", get_position="position", get_icon="icon", get_size=49,
                          size_units="'pixels'", size_min_pixels=49, size_max_pixels=49,
                          billboard=True, pickable=False),
            ]
    # No territory names on the map (too crowded with 48 areas): tap one for its card.
    if location is not None:
        here = [{"lng": location[1], "lat": location[0], "radius": accuracy_m or 0}]
        layers += [
            pdk.Layer("ScatterplotLayer", here, id="gps-accuracy", get_position="[lng, lat]", get_radius="radius",
                      get_fill_color=[255, 255, 255, 40], stroked=False),
            pdk.Layer("ScatterplotLayer", here, id="gps-position", get_position="[lng, lat]", get_radius=1,
                      radius_min_pixels=8, get_fill_color=[255, 255, 255, 255],  # --you-dot
                      get_line_color=[20, 43, 61, 255], stroked=True, line_width_min_pixels=3),
        ]
    event = st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_for(rows, focus, location),
            map_provider="carto",
            # Carto without place names (they clashed with ours): quiet light
            # "Positron" normally, "Dark Matter" when the player turned on dark mode.
            map_style=map_style(),
        ),
        height=height,
        # A tap selects one territory and reruns the page, so the bottom card
        # can show its tug-of-war (replaces the old hover tooltip).
        on_select="rerun",
        selection_mode="single-object",
        key=f"territory_map:{context}",
    )
    return selected_territory(event, {row["id"] for row in rows})


def selected_territory(event, known_ids: set) -> str | None:
    """The tapped territory's id from the map's selection state, if any.
    Only ids we drew are accepted."""
    try:
        objects = (event.selection or {}).get("objects", {}).get("territories", [])
    except AttributeError:
        return None
    for picked in objects:
        territory_id = (picked.get("properties") or {}).get("id") if isinstance(picked, dict) else None
        if territory_id in known_ids:
            return territory_id
    return None


def _sheet_row(row: dict) -> dict:
    """One territory in the list sheet as plain data (the sheet draws it as text,
    so names can never become HTML)."""
    me = row["my_points"]
    rivals = [r for r in row["ranking"] if not r["you"]]
    if row["status"] == "theirs":
        badge, sub = row["owner"], f'Owned by {row["owner"]}, you {format_points(me)} vs {format_points(row["owner_points"])}'
        pill = f'+{format_points(row["needed"])} to take'
    elif row["status"] == "yours":
        rival = rivals[0] if rivals else None
        badge = "You"
        sub = (f'Yours, {format_points(me)} vs {format_points(rival["points"])} for {rival["name"]}' if rival
               else f"Yours with {format_points(me)}, no rival yet")
        pill = f'+{format_points(me - (rival["points"] if rival else 0))} lead'
    else:
        badge, sub, pill = "", "Unclaimed", "Claim it"
    return {"id": row["id"], "name": row["name"], "status": row["status"], "sub": sub, "pill": pill,
            "avatar": initials(badge) if badge else "–", "detail": row["detail"]}


def territory_sheet_rows(rows: list[dict]) -> list[dict]:
    """All territories, easiest to take first: rivals' (fewest points needed),
    then unclaimed, then yours (smallest lead first, the ones to defend)."""
    def order(row):
        if row["status"] == "theirs":
            return (0, row["needed"], row["name"])
        if row["status"] == "free":
            return (1, 0, row["name"])
        rivals = [r["points"] for r in row["ranking"] if not r["you"]]
        return (2, row["my_points"] - (max(rivals) if rivals else 0), row["name"])
    return [_sheet_row(row) for row in sorted(rows, key=order)]


_territory_sheet = declare_component(
    "territory_sheet", path=str(Path(__file__).parent / "components" / "territory_sheet"))


def all_territories_button(rows: list[dict]) -> None:
    """The "All territories  N" row in the bottom card: opens the sheet."""
    if st.button(f"All territories\u2003{len(rows)}", key="map_all_territories", width="stretch"):
        st.session_state["map_sheet_open"] = st.session_state.get("map_sheet_open_count", 0) + 1
        st.session_state["map_sheet_open_count"] = st.session_state["map_sheet_open"]


def territory_list(rows: list[dict], *, lobby_name: str = "", team_mode: bool = False) -> str | None:
    """The territory sheet over the map (its own component, so it can be swiped
    down like an iPhone sheet). Call it outside the blurred bottom card: a blurred
    parent would trap the full-screen frame inside it. Returns the territory id
    the player tapped in the list, else None."""
    opened = st.session_state.get("map_sheet_open")
    if not opened:
        return None
    summary = summary_line(rows)
    note = "Team territories: points and gaps combine all team members’ drinks." if team_mode else ""
    with st.container(key="territory_sheet_stage"):
        value = _territory_sheet(rows=territory_sheet_rows(rows), title=lobby_name, summary=summary, note=note,
                                 tokens=component_tokens(), key=f"territory_sheet_{opened}", default=None)
    if not isinstance(value, dict) or value.get("action") not in ("close", "select"):
        return None
    st.session_state.pop("map_sheet_open", None)          # swiped down, backdrop or a name: the sheet goes
    picked = value.get("id") if value.get("action") == "select" else None
    if picked in {row["id"] for row in rows}:           # only ids we listed
        return picked
    try:                                                # closed without a pick: just hide the sheet
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()


def summary_line(rows: list[dict]) -> str:
    numbers = summary(rows)
    rivals = numbers["total"] - numbers["yours"] - numbers["free"]
    return f'{numbers["yours"]} yours\u2003{rivals} rivals\u2003{numbers["free"]} free'

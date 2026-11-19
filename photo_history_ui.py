"""Photo-card presentation using authorized image bytes and stored entry values."""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime
from decimal import Decimal
from html import escape
from hashlib import sha256
from zoneinfo import ZoneInfo

import streamlit as st

from core.scoring_v1 import DRINK_LABELS, format_points, size_label, utc
from drink_entry_ui import context_line


def photo_card(entry: dict, photo: bytes | None) -> None:
    location = "Outside game territories" if entry["location"] == "outside" else entry["territory"]
    context_line(entry["username"], location or "No territory assigned")
    framed_photo(entry, photo)
    photo_metadata(entry)


def identity_colour(entry: dict) -> str:
    """A stable identity colour across pagination, renames and app restarts."""
    identity = (f"team:{entry['team_id']}" if entry.get("team_id") else
                f"player:{entry.get('player_id') or entry.get('membership_id') or entry['username']}")
    hue = int.from_bytes(sha256(identity.encode()).digest()[:4], "big") / 2**32 * 360
    return f"hsl({hue:.3f} 60% 42%)"


def framed_photo(entry: dict, photo: bytes | None, *, detail: bool = False) -> None:
    name = entry["username"]
    if entry.get("team_id"):
        name = f"{entry.get('team_name') or 'Team'} · {name}"
    # Identity-derived colour only; all names are escaped and images stay inline.
    colour = identity_colour(entry)
    label = f'<figcaption class="history-photo-identity">{escape(name)}</figcaption>'
    if photo is not None:
        encoded = b64encode(photo).decode("ascii")
        image = (f'<img class="{"drink-photo" if detail else "history-photo"}" '
                 f'src="data:image/jpeg;base64,{encoded}" alt="Check-in photo by {escape(name, quote=True)}">')
        st.html(f'<figure class="history-photo-frame" style="--photo-identity:{colour}">{label}{image}</figure>')
    else:
        st.markdown(f'<figure class="history-photo-frame" style="--photo-identity:{colour}">{label}'
                    '<div class="history-photo-missing">Photo unavailable</div></figure>', unsafe_allow_html=True)


def photo_metadata(entry: dict) -> None:
    """Show stored selections/awards, including historical legacy entries."""
    model = entry.get("entry")
    kind = model.drink_type if model else entry.get("drink_type")
    selection = DRINK_LABELS.get(kind, "Long drink" if kind == "longdrink" else kind or "Drink details unavailable")
    if model and model.size:
        selection += f" · {size_label(kind, model.size, entry['season'].scoring_rules)}"
    points = model.points_awarded if model else entry.get("base_points")
    if points is None:
        award = "Points unavailable"
    else:
        territory_points = points if entry["location"] == "matched" else 0
        season_points = entry.get("duel_season_points", points) if entry.get("duel_id") else points
        award = f"+{format_points(season_points)} season pts · +{format_points(territory_points)} territory pts"
    timestamp = entry.get("captured_at") or entry["submitted_at"]
    zone = ZoneInfo(entry.get("timezone_name", "UTC"))
    time = utc(datetime.fromisoformat(timestamp)).astimezone(zone)
    time_label = "Photo received" if entry.get("captured_at") else "Submitted"
    st.markdown(f'<div class="history-card-details"><h3>{escape(selection)}</h3>'
                f'<p class="history-award">{escape(award)}</p>'
                f'<p class="history-time">{time_label} · {time:%d %b %Y · %H:%M %Z}</p></div>',
                unsafe_allow_html=True)
    if entry.get("duel_id"):
        st.caption("Chug Duel · Shared capture · Drink selection agreed by both players.")
    bonus = model.owner_bonus_quarters if model else entry.get("owner_bonus_quarters", 0)
    if bonus:
        income = format_points(Decimal(bonus) / 4)
        st.markdown(f'<p class="history-owner-income">Owner income: +{income} pts to '
                    f'{escape(entry.get("income_recipient") or "Lobby member")}</p>', unsafe_allow_html=True)

"""Photo-card presentation using authorized image bytes and stored entry values."""
from base64 import b64encode
from datetime import datetime
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from core.scoring_v1 import DRINK_LABELS, format_points, size_label, utc
from drink_entry_ui import context_line


def photo_card(entry: dict, photo: bytes | None) -> None:
    location = "Outside game territories" if entry["location"] == "outside" else entry["territory"]
    context_line(entry["username"], location or "No territory assigned")
    if photo is not None:
        encoded = b64encode(photo).decode("ascii")
        st.html(f'<img class="history-photo" src="data:image/jpeg;base64,{encoded}" alt="Drink check-in photo">')
    else:
        st.markdown('<div class="history-photo-missing">Photo unavailable</div>', unsafe_allow_html=True)
    photo_metadata(entry)


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
        award = f"+{format_points(points)} season pts · +{format_points(territory_points)} territory pts"
    timestamp = entry.get("captured_at") or entry["submitted_at"]
    zone = ZoneInfo(entry.get("timezone_name", "UTC"))
    time = utc(datetime.fromisoformat(timestamp)).astimezone(zone)
    time_label = "Photo received" if entry.get("captured_at") else "Submitted"
    st.markdown(f'<div class="history-card-details"><h3>{escape(selection)}</h3>'
                f'<p class="history-award">{escape(award)}</p>'
                f'<p class="history-time">{time_label} · {time:%d %b %Y · %H:%M %Z}</p></div>',
                unsafe_allow_html=True)
    bonus = model.owner_bonus_quarters if model else entry.get("owner_bonus_quarters", 0)
    if bonus:
        income = format_points(Decimal(bonus) / 4)
        st.markdown(f'<p class="history-owner-income">Owner income: +{income} pts to '
                    f'{escape(entry.get("income_recipient") or "Lobby member")}</p>', unsafe_allow_html=True)

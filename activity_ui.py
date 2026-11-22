"""Activity feed presentation. Which events exist comes from core/activity.py.

Every name and territory is escaped here; the page only passes ids and the
lookup tables it loaded.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from zlib import crc32
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from core.activity import CAPTURE, CHUG_DUEL, DUEL, MEDAL, ActivityEvent
from core.scoring_v1 import DRINK_LABELS, SIZE_LABELS, format_points, utc, window_bounds
from photo_history_ui import game_night_label, identity_colour
from profile_picture_ui import avatar_html
from standings_ui import ago
from theme import icon_css

VIEWS = ["Feed", "Photos"]
VIEW_PAGES = {"Feed": "pages/8_Activity.py", "Photos": "pages/6_Check_in_photos.py"}

# Ways to say "drank". Each check-in keeps the same one on every reload.
VERBS = ["drank", "downed", "sank", "knocked back", "polished off", "put away", "chugged",
         "inhaled", "demolished", "sipped", "threw back", "made short work of", "said cheers to",
         "disposed of", "got through"]


def load_styles() -> None:
    css = (Path(__file__).parent / "assets" / "activity.css").read_text(encoding="utf-8")
    css += icon_css(".activity-duel-icon", "trophy-fill")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def view_switch(current: str) -> None:
    """Feed | Photos at the top of both screens; the bottom tab opens Feed."""
    choice = st.radio("Activity view", VIEWS, index=VIEWS.index(current), horizontal=True,
                      key=f"pill_radio_activity_view_{current.lower()}", label_visibility="collapsed")
    if choice != current:
        st.switch_page(VIEW_PAGES[choice])


def medal_list(medals) -> str:
    """'A', 'A and B', 'A, B and C': no middle dots, like the rest of the app."""
    medals = list(medals)
    return " and ".join([", ".join(medals[:-1]), medals[-1]]) if len(medals) > 1 else "".join(medals)


def drink_label(event: ActivityEvent) -> str:
    """'large beer', 'shot': size first, all lower case, to follow the bold name."""
    drink = DRINK_LABELS.get(event.drink_type, "Drink").lower()
    size = SIZE_LABELS.get(event.size)
    return f"{size.lower()} {drink}" if size else drink


def drink_verb(entry_id: str) -> str:
    """Picked from the entry id, so the same check-in reads the same every time
    (Python's own hash() changes between restarts; crc32 does not)."""
    return VERBS[crc32(entry_id.encode()) % len(VERBS)]


def _name(competitor: str | None, names: dict, me: str) -> str:
    if competitor == me:
        return "you"
    return names.get(competitor, "Unknown player")


def capture_html(event: ActivityEvent, names: dict, territory_names: dict, me: str) -> str:
    """'Ben took Shortys from you', 'You claimed Nova SBE', ... as a tinted banner.

    Green when you gain a territory, red when one is taken from you, violet
    when other players take one (assets/activity.css)."""
    winner = _name(event.competitor, names, me)
    place = escape(territory_names.get(event.territory_id, "a territory"))
    if event.previous_owner is None:
        text = f"{escape(winner)} claimed <strong>{place}</strong>"
    else:
        text = (f"{escape(winner)} took <strong>{place}</strong> "
                f"from {escape(_name(event.previous_owner, names, me))}")
    text = text[0].upper() + text[1:]
    tone = ("yours" if event.competitor == me else
            "lost" if event.previous_owner == me else "rival")
    return (f'<div class="activity-capture activity-capture-{tone}">'
            f'<span class="activity-capture-dot" aria-hidden="true"></span>'
            f'<span>{text}</span></div>')


def duel_html(event: ActivityEvent, member_names: dict, team_names: dict, territory_names: dict,
              me_member: str, me_competitor: str, now: datetime) -> str:
    """'You won the Chug Duel against Ben', +2, 'Ben −1': one row per finished duel.

    Green when you won, red when you lost, violet between other players, like
    captures. The right-hand column shows what the winner got (or the Time Duel
    boost) and the second line what the loser gave up; when you lost, the
    right-hand column is your loss and the second line the winner's gain."""
    def who(member, account, *, start):
        if member == me_member:
            return "You" if start else "you"
        name = member_names.get(member, "Unknown player")
        team = team_names.get(account) if team_names else None
        return f"{name} ({team})" if team else name

    you_won = event.member == me_member or (team_names and event.competitor == me_competitor)
    you_lost = event.loser_member == me_member or (team_names and event.loser == me_competitor)
    tone = "yours" if you_won else "lost" if you_lost else "rival"
    game = "a duel" if event.game == "Duel" else f"the {event.game}"
    title = (f"<strong>{escape(who(event.member, event.competitor, start=True))}</strong> won {escape(game)} "
             f"against <strong>{escape(who(event.loser_member, event.loser, start=False))}</strong>")
    details = []
    if event.game == CHUG_DUEL and event.territory_id:
        details.append(territory_names.get(event.territory_id, "Unknown territory"))
    winner_gets = event.prize or f"+{format_points(event.points)}"
    loser_gives = f"\u2212{format_points(event.lost_points)}" if event.lost_points else None
    # The right-hand number is the viewer's own result when they lost.
    if tone == "lost" and loser_gives:
        reward = loser_gives
        details.append(f"{who(event.member, event.competitor, start=True)} {winner_gets}")
    else:
        reward = winner_gets
        if event.prize:
            details.append("1 hour boost")
        elif loser_gives:
            details.append(f"{who(event.loser_member, event.loser, start=True)} {loser_gives}")
    details.append(ago(event.at, now))
    return (
        f'<div class="activity-duel activity-duel-{tone}">'
        f'<span class="activity-duel-icon" aria-hidden="true"></span>'
        f'<span class="activity-main"><span class="activity-title">{title}</span>'
        f'<span class="activity-meta">{escape(", ".join(details))}</span></span>'
        f'<span class="activity-points">{escape(reward)}</span></div>'
    )


def checkin_html(event: ActivityEvent, member_names: dict, team_names: dict, territory_names: dict,
                 me_member: str, now: datetime, picture: str | None = None) -> str:
    you = event.member == me_member
    name = "You" if you else member_names.get(event.member, "Unknown player")
    if team_names and event.competitor in team_names:
        name = f"{name} ({team_names[event.competitor]})"
    where = (territory_names.get(event.territory_id, "Unknown territory") if event.territory_id
             else "Outside territories")
    avatar = f"background:{identity_colour({'membership_id': event.member})};color:#fff;"
    return (
        f'<div class="activity-row{" activity-row-you" if you else ""}">'
        + avatar_html(member_names.get(event.member, "?"), picture, cls="activity-avatar", style=avatar) +
        f'<span class="activity-main"><span class="activity-title"><strong>{escape(name)}</strong> '
        f'{escape(drink_verb(event.entry_id))} a {escape(drink_label(event))}</span>'
        f'<span class="activity-meta">{escape(where)}, {escape(ago(event.at, now))}</span></span>'
        f'<span class="activity-points">+{escape(format_points(event.points))}</span></div>'
    )


def feed_html(events: list[ActivityEvent], *, member_names: dict, team_names: dict, territory_names: dict,
              me_member: str, me_competitor: str, season, now: datetime, pictures: dict | None = None) -> str:
    """Rows newest first, with a heading whenever a new game night starts."""
    names = team_names or member_names
    parts, night = [], None
    for event in events:
        if season is not None:
            bounds = window_bounds(event.at, season)
            if event.kind == MEDAL and not (utc(season.starts_at) <= utc(event.at) < utc(season.ends_at)
                                            and utc(bounds[0]) <= utc(event.at) < utc(bounds[1])):
                date = utc(event.at).astimezone(ZoneInfo(season.timezone_name)).date()
                group, label = date, f"{date:%d %b %Y}"
            else:
                group, label = bounds, game_night_label(*bounds)
            if group != night:
                night = group
                parts.append(f'<p class="activity-night">{escape(label)}</p>')
        if event.kind == CAPTURE:
            parts.append(capture_html(event, names, territory_names, me_competitor))
        elif event.kind == DUEL:
            parts.append(duel_html(event, member_names, team_names, territory_names, me_member, me_competitor, now))
        elif event.kind == MEDAL:
            name = "You" if event.member == me_member else member_names.get(event.member, "Unknown player")
            medals = medal_list(event.medals)
            parts.append(f'<div class="activity-medal"><span aria-hidden="true">★</span>'
                         f'<span>{escape(name)} earned <strong>{escape(medals)}</strong>'
                         f'<small>{escape(ago(event.at, now))}</small></span></div>')
        else:
            parts.append(checkin_html(event, member_names, team_names, territory_names, me_member, now,
                                      (pictures or {}).get(event.member)))
    return '<div class="activity-feed">' + "".join(parts) + "</div>"

"""Season awards for the end-of-season recap (R-S01 to R-S03 in docs/ontology/RULES.md).

Pure: no Streamlit, no database. Everything is derived from the saved entries
and transfers with the same replay as Ranks and the Map, so the recap always
matches the final standings. Nothing here changes points.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from core.activity import accepted
from core.leaderboard import season_leaderboard
from core.models import DrinkEntry
from core.scoring_v1 import format_points, replay_season
from core.teams import competitor

MVP = "mvp"
TERRITORIES = "territories"
TAKEOVER = "takeover"
CAPTURES = "captures"
DRINKS = "drinks"
ORDER = (MVP, TERRITORIES, TAKEOVER, CAPTURES, DRINKS)  # slide order in the recap


@dataclass(frozen=True)
class Award:
    key: str
    winner: str          # competitor id: membership id, or team id in team lobbies
    value: int | Decimal  # points, territories, captures or drinks; beaten points for a takeover
    territory_id: str | None = None  # biggest takeover only
    loser: str | None = None         # biggest takeover only


@dataclass(frozen=True)
class Standing:
    competitor: str
    rank: int
    points: int | Decimal
    drinks: int
    territories: int
    captures: int


@dataclass(frozen=True)
class Recap:
    standings: list[Standing]   # final order, same as Ranks
    awards: list[Award]         # only awards that have a winner
    you: Standing | None        # None when the viewer never scored

    @property
    def podium(self) -> list[Standing]:
        return self.standings[:3]


def _most(counts: Counter, rank: dict[str, int]) -> tuple[str, int] | None:
    """Highest count; a tie goes to the better final rank (R-S02)."""
    if not counts:
        return None
    winner = min(counts, key=lambda c: (-counts[c], rank.get(c, len(rank)), c))
    return winner, counts[winner]


def build_recap(entries: list[DrinkEntry], transfers=(), *, me: str | None = None) -> Recap:
    legacy = not transfers and not any(entry.rule_version == "v1" for entry in entries)
    rows = season_leaderboard(entries, transfers)
    rank = {c: index for index, (c, _) in enumerate(rows)}
    counted = (lambda e: e.points_awarded > 0) if legacy else accepted
    drinks = Counter(competitor(e) for e in entries if counted(e))
    held: Counter = Counter()
    gains: Counter = Counter()
    takeover = None
    if not legacy:
        replay = replay_season(entries, transfers)
        held = Counter(replay.owners.values())
        for _entry, territory, new_owner, previous, beaten in replay.captures:
            gains[new_owner] += 1
            # Only real takeovers; the earliest one wins a tie, so strictly greater.
            if previous is not None and (takeover is None or beaten > takeover.value):
                takeover = Award(TAKEOVER, new_owner, beaten, territory, previous)

    standings = [Standing(c, index + 1, points, drinks[c], held[c], gains[c])
                 for index, (c, points) in enumerate(rows)]
    found = {TAKEOVER: takeover}
    if rows and rows[0][1] > 0:
        found[MVP] = Award(MVP, rows[0][0], rows[0][1])
    for key, counts in ((TERRITORIES, held), (CAPTURES, gains), (DRINKS, drinks)):
        if (best := _most(counts, rank)):
            found[key] = Award(key, *best)
    awards = [found[key] for key in ORDER if found.get(key)]
    you = next((s for s in standings if s.competitor == me), None)
    return Recap(standings, awards, you)


def safe_cell(value) -> str:
    """Stop a name like '=HYPERLINK(...)' running as a formula in Excel or Sheets."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_rows(recap: Recap, names: dict[str, str]) -> list[list[str]]:
    header = ["Rank", "Player", "Points", "Drinks", "Territories held", "Captures"]
    return [header] + [[str(s.rank), safe_cell(names.get(s.competitor, "Unknown player")), format_points(s.points),
                        str(s.drinks), str(s.territories), str(s.captures)] for s in recap.standings]

"""Read retained season records for profile stats and medal announcements."""
from functools import partial

import data.db as db
from parallel import run_parallel


def load_stat_history(lobby_ids, *, known_entries=None):
    known_entries = known_entries or {}
    groups = run_parallel(*(partial(db.list_seasons_for_lobby, lobby_id)
                            for lobby_id in dict.fromkeys(lobby_ids)))
    seasons = {season.id: season for group in groups for season in group}
    missing = [season_id for season_id in seasons if season_id not in known_entries]
    reads = run_parallel(*(partial(db.list_drink_entries, season_id) for season_id in missing),
                         *(partial(db.list_season_transfers, season_id) for season_id in seasons))
    entries_by_season = {**known_entries, **dict(zip(missing, reads[:len(missing)]))}
    return [(season, entries_by_season[season.id], transfers)
            for season, transfers in zip(seasons.values(), reads[len(missing):])]

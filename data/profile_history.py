"""Read retained season records for profile stats and medal announcements."""
from collections import defaultdict

import data.db as db
from parallel import run_parallel


def load_stat_history(lobby_ids, *, known_entries=None):
    known_entries = known_entries or {}
    seasons = db.list_seasons_for_lobbies(lobby_ids)
    if not seasons:
        return []
    season_ids = [season.id for season in seasons]
    missing = [season_id for season_id in season_ids if season_id not in known_entries]
    entries, transfers = run_parallel(
        lambda: db.list_drink_entries_for_seasons(missing),
        lambda: db.list_transfers_for_seasons(season_ids),
    )
    entries_by_season = defaultdict(list, known_entries)
    transfers_by_season = defaultdict(list)
    for entry in entries:
        entries_by_season[entry.season_id].append(entry)
    for transfer in transfers:
        transfers_by_season[transfer.season_id].append(transfer)
    return [(season, entries_by_season[season.id], transfers_by_season[season.id])
            for season in seasons]

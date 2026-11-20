"""Compare equivalent navigation/read schedules; never print account data.

Default: synthetic 80 ms network calls. --live: read-only shared Supabase
bootstrap timing using one current membership; no check-ins or scores are written.
Run from the repository root: python scripts/benchmark_navigation.py [--live]
"""
import argparse
from pathlib import Path
from statistics import median
import sys
from time import perf_counter, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parallel import run_parallel


def compare(label, before, after, samples=3):
    timings = [[], []]
    for _ in range(samples):
        for index, call in enumerate((before, after)):
            start = perf_counter()
            call()
            timings[index].append((perf_counter() - start) * 1000)
    old, new = (median(values) for values in timings)
    print(f'{label}: median {old:.0f} ms -> {new:.0f} ms ({100 * (old-new) / old:.0f}% less waiting)')


def navigation(account, context, badge):
    def before():
        run_parallel(account, context)
        badge()
    return before, lambda: run_parallel(account, context, badge)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    def read():
        sleep(0.08)
    compare('Synthetic navigation, 80 ms/read', *navigation(read, read, read))
    compare('Synthetic 12-photo gallery, 80 ms/download',
            lambda: [read() for _ in range(12)], lambda: run_parallel(*[read] * 12))
    if args.live:
        import data.db as db
        client = db.get_client()
        rows = (client.table('lobby_memberships').select('id,player_id,lobby_id,lobbies!inner(seasons(id))')
                .is_('left_at', 'null').limit(1).execute().data)
        if not rows or not rows[0]['lobbies']['seasons']:
            raise SystemExit('No current membership/season is available for the read-only benchmark.')
        row = rows[0]
        sid = row['lobbies']['seasons'][0]['id']
        account = lambda: db.get_player(row['player_id'])
        context = lambda: db.membership_context(row['player_id'], row['id'], row['lobby_id'], sid)
        badge = lambda: db.pending_minigame_invite_count(row['player_id'], sid)
        # Verify these three reads once before measuring; no identifiers are printed.
        account(); context(); badge()
        compare('Live Supabase navigation reads, warm connection', *navigation(account, context, badge))


if __name__ == '__main__':
    main()

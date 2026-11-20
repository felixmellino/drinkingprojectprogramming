# Navigation and loading performance — 19 November 2026

Merge reconciliation, 20 November 2026: retain main's Photos tab, All/Mine
filter, portrait grid and full-photo detail, Location switches and tapped-map
territory cards. The optimized bounded loading and destination callbacks apply
to that current interface. Main's Reaction Duel replacement remains in place;
the removed solo Focus screen is not restored.

This change reduces repeated reads and sequential network waits. It does not
change scores, game rules, location thresholds, membership or photo audiences.
Deploy it through the normal reviewed PR. No new database migration is needed
for these performance changes; existing feature migrations still apply.

## Changes

- Existing sessions opening the app entry point go straight to Map. The
  destination freshly validates login and membership, avoiding a duplicate
  entry-point bootstrap.
- The account, selected membership/season and invitation badge reads overlap.
  The badge consumes that result once for the matching player and season.
  Its ten-second fragment refresh still queries the server again. Failed badge
  requests are retried on the next refresh, not twice during one page load.
- Lobby restoration, leaderboard fallback, lobby card summaries and personal
  statistics overlap independent reads. Rendering remains on the page thread,
  and result order stays deterministic. Each parallel batch has at most eight
  workers instead of allocating one thread per record.
- Map and leaderboard load the public username projection rather than full
  account rows containing private fields.
- Map avatars authorize the current credential/friendship state once per
  bounded batch, fetch allowed references together and check the private bucket
  once before downloading. Unauthorized owners never reach Storage. No image
  bytes or authorization decisions are cached between requests.
- Profile Edit reuses the avatar just fetched for its identity header. Menu
  navigation is processed before downloading an avatar for the page being left.
  Storage failures still show the existing explanatory message and initials.
- Gallery pages contain at most twelve photos and two game-night groups.
  Larger nights continue on the next page. Only visible photos download, with
  bounded concurrency and the existing fresh per-photo membership, consent,
  reference, expiry and private-bucket checks. A denied access check stops the
  gallery before any tile is shown. Pagination/detail callbacks select the
  destination before loading, avoiding a second download of the departed page.

## Measurements and verification

Run `python scripts/benchmark_navigation.py` for a reproducible synthetic
comparison. Add `--live` for three warm, read-only Supabase samples. The live
mode prints timings only and writes no game data.

Measured locally on 19 November 2026:

| Comparison | Before | After | Scope |
| --- | ---: | ---: | --- |
| Live Supabase navigation reads | 175 ms | 102 ms | Median of three warm samples, 42% less waiting |
| Synthetic navigation, 80 ms per read | 163 ms | 85 ms | Controlled network-delay comparison |
| Synthetic twelve-photo gallery, 80 ms per download | 968 ms | 169 ms | Controlled network-delay comparison, 82% less waiting |

These measure the read schedules, not total deployed page-load time or a phone
benchmark. Real gains depend on network latency, lobby size, image sizes and
hosting. Streamlit Cloud cold starts, initial dependency imports and browser
map assets are outside these timings. No production speed guarantee is implied.

Regression checks cover credential revocation, membership loss, per-request
invitation updates, private-bucket/consent checks, old and new gallery pages,
ordering, profile save/remove/restart and a bounded worker pool. The local browser
fixture `streamlit run tests/fixtures/performance_app.py` exercises the actual
Profile, Map, Leaderboard, Lobbies and Photo history pages with synthetic data
and 50 ms simulated reads. A browser switched between them, opened photo
details and reached the last of 25 photos (12 + 12 + 1), without shared data.
The full local Python suite passed 961 tests; a subsequent Map error-path
check also covers a credential change during an avatar request.
Those counts describe the original performance branch. Verification of the
20 November merge is recorded in the PR. The merge also reconstructs the
accidentally overwritten rulebook from its last intact Git version, preserving
Reaction Duel/scoring/privacy rules and inserting the current Location rule
once. It removes the repeated Location-only text (about 70 MB) from the file.
Final merge verification: all 1,000 Python tests passed. Location and Reaction
Duel component checks and the documented 25-file SQL installation chain passed.
An isolated browser verified All/Mine filtering, the portrait grid and the
full-photo detail with the destination callback. No shared data was changed.

## Remaining limits

Scores and permissions intentionally remain fresh instead of using a global
TTL cache. Very large competitions still download/replay full season history;
server-side standings summaries and database-level gallery pagination would
be separate coordinated data-layer changes. This PR bounds photo downloads,
not the metadata history query. Deployment and a real-phone comparison on the
public URL remain to verify after merge.

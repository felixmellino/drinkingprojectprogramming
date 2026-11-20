# Full-app performance audit — 20 November 2026

This audit starts from main `ad4c9cf` on `codex/app-performance-audit` and
also integrates the team's newer main before final verification. It preserves
all current game rules, photo privacy, original images, scores and minigames.
No Supabase migration, credential change or shared-data mutation is required.

## What was measured

Live calls used the configured shared Supabase project, from this development
machine. Initial observations used five warm samples; photo comparisons used
three. The chosen season had 31 entries and the permitted gallery 11 photos.
Only counts, route categories, bytes, durations and error types are recorded.
No IDs, passwords, request headers, exact coordinates or photo contents are
saved in the measurement output. Writes and email delivery use isolated tests.

| Connected service / operation | Observed median | Interpretation |
| --- | ---: | --- |
| First Supabase REST call | 181–211 ms | One request, includes initial transport setup |
| Current account validation | 71–77 ms | Fresh credential check, deliberately not cached |
| Current membership and season | 73–89 ms | Fresh authorization, deliberately not cached |
| Public username directory | 75–98 ms | Public projection only |
| Lobby directory | 71–73 ms | One REST call; cards do additional scoped reads |
| Season entries | 72–91 ms | One call for the sampled 31-entry season |
| Season stake ledger | 66–74 ms | Separate from drink and territory points |
| Invitation badge | 70–83 ms | Scoped read-only counter |
| Gallery metadata, previous | 306–379 ms | Four sequential calls |
| Gallery metadata, updated | 261 ms | Three calls; one current roster reused within this invocation |
| Private bucket metadata | 116–177 ms | Per operation/batch; never cached globally |
| Original photo, individual authorized read | 538–623 ms | Six calls, including all permission checks |
| Own avatar when none is stored | 153–219 ms | Two authorization/reference reads; no object download |
| Public Streamlit HTML shell | 390–400 ms | Initial sample reached 2,236 ms; not full app or WebSocket loading |
| CARTO map style JSON | 33–108 ms | Public map configuration; tile loading is additional |
| Google Fonts stylesheet | 37–58 ms | CSS only; font files and browser rendering are additional |
| Brevo connectivity | 85–102 ms | Expected unauthenticated HTTP 401; does not prove mail delivery |

These are small diagnostic samples, not p95 latency estimates or a benchmark
of the hosting region. Variation is visible between runs. An original-path
repeat encountered one transient `RemoteProtocolError`; failed samples must
not be counted as successful timing results. The final batch comparison had
no operation-level exception. Missing objects are separately returned as
unavailable, with a readable placeholder instead of losing the whole gallery.

## Changes and measured benefit

### Gallery: fewer requests and smaller browser payloads

The previous gallery made six requests per photo, including repeated roster,
consent and bucket reads. Eleven visible photos therefore required 66 calls,
even with bounded parallel workers. The new `download_checkin_photos` checks
one fresh roster, one scoped entry set, one current consent set and the private
bucket, then downloads only the requested allowed paths. Eleven photos take
15 calls. The cap remains twelve; duplicate IDs are deduplicated.

| Same visible gallery, three warm samples | Previous path | Batched path |
| --- | ---: | ---: |
| Requests for 11 photos | 66 | 15 |
| Median live read time, first valid comparison | 1,915 ms | 820 ms |

That comparison saves 57% of waiting and 77% of requests. A later run's batch
median was 1,363 ms, demonstrating network variation; this is not a promise
that every phone will load in 820 ms. Metadata loading and browser rendering
are additional to this operation.

All batch permissions are checked before any image object is requested. An
outsider, withdrawn consent, changed team roster or unverified public bucket
still blocks access. Deleted, expired, wrong-lobby, missing or wrong-path
images never become authorized through an old gallery listing. Detail opening
retains its fresh single-image authorization and original image.

Grid cards now receive a display-only JPEG thumbnail up to 360×480 rather
than a base64 copy of the original. A measured example fell from 168,193 to
18,372 bytes (89% smaller). Stored originals and the full-photo detail are
unchanged. This reduces server-to-browser delivery; the server still downloads
the original from Storage. Thumbnails are decoded one at a time to bound
working memory, respect the existing pixel limit, and fall back gracefully
for unreadable bytes. No private image or audience is cached across requests.

### Lobby: overlap independent reads

After membership verification, public username and the viewer's friendship
reads overlap. A friendship-provider failure still leaves the member list
readable with its existing warning. Active individual lobby cards overlap the
leader-name and roster reads before fetching an allowed avatar. Rendering
remains on the main Streamlit thread; privacy checks stay fresh.

In the actual-page fixture with 50 ms per synthetic service read, a warm lobby
render changed from 460 to 387 ms. This is a controlled local result, not live
Supabase end-to-end time. Other fixture warm renders were approximately:
Profile 125 ms, Photos 242 ms, Ranks 184 ms, Map 258 ms. Each page uses the
actual application code with artificial records and a blocked live client.

### Profile and cold-client reliability

Completed modern seasons previously replayed ownership once to find the
winner and again for owner income. A single request-local replay now serves
both, including stake transfers and the established tie-break. On 5,000
artificial entries it took 14.84 instead of 33.46 ms with identical statistics.
Time Duel bonuses remain excluded from lifetime points as explicitly required
by `TIME_DUEL.md`; this audit changes no scoring rule.

Concurrent initial requests could also construct multiple Supabase clients
before the shared variable was assigned. Initialization now uses a lock and
a second check, preserving one pooled client and allowing retry after failed
initialization. This does not cache credentials' validity or permission data.

Historical Focus photos now label their saved ×1.25/×1.5 tier accurately;
older records with no tier keep the existing ×1.5 fallback.

## Whole-app verification and reproducible commands

`python -m pytest -q --durations=15` exercises account creation/login/logout,
remembered sessions and credential revocation, password reset with mocked
Brevo, lobby creation/join/leave/team access, inside/outside/uncertain GPS,
required camera images, duplicates, cooldown/window boundaries, corrections,
territory capture/ties, standings, photo privacy/deletion/retention, and all
minigame interfaces/rules. Live client creation was blocked in this test run.
Initial full audit suite: **1,024 passed**; subsequent affected lobby/profile
checks: **128 passed**. Final combined-main verification is recorded below.

Additional isolated PostgreSQL checks passed for:

- The documented 25-file migration installation order and anonymous-role denial.
- Scoring: atomic acceptance, boundary cutoffs, duplicates, corrections,
  owner-income replay, frozen rules and reopen after restart.
- Chug Duel: two-player acceptance, capture, transfers once, rollback, normal
  limits and unlimited QA repeats, expiry, permissions and restart.
- Quiz Duel: stake reservation, teams, rounds, retries, limits and restart.
- Reaction Duel: false starts, best of three, timeout, stakes and ledger once.
- Historical Focus: all eight task-result combinations, continuation, exact
  fractional awards, corrections, expiry and saved state.
- Time Duel: invitations/retries, outsider denial, all three rounds, the saved
  season-only boost, normal owner income, exact expiry and reopen after restart.

Run the portable database checks with PGlite 0.3.14 installed outside app
requirements. On PowerShell:

```powershell
$env:SCORING_PYTHON='.venv/Scripts/python.exe'
$env:PGLITE_MODULE='.venv/photo-sql-check/package/dist/index.cjs'
node tests/migration_chain.cjs $env:PGLITE_MODULE
node tests/scoring_postgres.cjs $env:PGLITE_MODULE
node tests/chug_duel_postgres.cjs $env:PGLITE_MODULE
node tests/quiz_postgres.cjs $env:PGLITE_MODULE
node tests/reaction_postgres.cjs $env:PGLITE_MODULE
node tests/focus_complete_postgres.cjs
node tests/time_postgres.cjs $env:PGLITE_MODULE
node tests/camera_component.cjs
node tests/location_component.cjs
node tests/reaction_component.cjs
```

Camera, location and reaction component checks passed. The separate existing
Playwright scripts require their browser harness and were not completed by
this audit; they are not included as passed. Browser interaction for this audit
uses the local actual-page fixture, not a shared player's account.

`python -m pip check` found no broken requirements. A separate pip-audit 2.10.1
environment checked **80 installed app/environment packages** against current
advisories on 20 November 2026: **no known vulnerabilities found**. The audit
tool was not added to the application's dependencies.

Reproduce the read-only timings and server-render measurements:

```powershell
python scripts/audit_app_performance.py --live --external --output .venv/audit.json
python scripts/benchmark_app_pages.py
streamlit run tests/fixtures/performance_app.py
```

The live script can read up to twelve existing permitted images into memory;
it never saves them, sends mail, uploads images or mutates game records.
Do not treat status RPCs as pure reads: some minigame status functions finalize
expired rounds while holding a lobby lock. They were exercised only against
isolated PostgreSQL during this audit. The badge counter is read-only.

## Remaining work and limits

- After teammate review and merge, compare the deployed app on a real phone:
  first open versus warm page switching, camera opening/flip/retake and actual
  permission prompts, GPS freshness, upload, reopen from another allowed
  account and privacy revocation. Synthetic GPS/camera evidence is not a
  physical-device test.
- Brevo's request format, timeout and safe failures are tested with mocked
  transport. An authorized test recipient must confirm real delivery.
- The latest visible scheduled cleanup run succeeded on 19 November 2026.
  That proves that run completed, not that a run happened every subsequent day
  or that a newly deleted object's backups/copies disappeared. Check Actions
  after deployment; no destructive cleanup was triggered by this audit.
- Very large lobbies still read full season history for standings/replay and
  full gallery metadata before applying the twelve-image display page. A
  coordinated server-side summary/keyset-pagination change is the next
  scalability step, with dedicated correctness/permission tests.
- On every acceptance, SQL replays prior entries; minigame refreshes also take
  lobby locks. Large-history/write-contention profiling needs an isolated
  concurrent load test before redesigning transactions. This audit did not
  reduce atomicity or remove server validation to make timings look better.
- Streamlit hosting startup, mobile radio/Wi-Fi, database region and browser
  map/font assets contribute latency beyond the measured reads. The initial
  HTTP shell sample above is not proof of a host cold start.
- Tests include upstream Streamlit/pandas deprecation warnings. They passed;
  dependency warnings are not suppressed as a performance fix.

---

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

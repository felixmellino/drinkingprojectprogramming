# WeGoPub performance audits

## Fewer waiting rounds on Lobby and Map — 21 November 2026

Live tab switches (deployed app, signed in): Lobby 3.0–3.5 s, Map 2.6–3.4 s,
Games 1.5–2.0 s, Activity 1.55 s, Ranks 0.95–1.7 s, Profile 1.1–1.35 s. Python
work is under 0.1 s per page; the time is database round trips that wait for
each other, each costing about 0.3 s from Streamlit Cloud. Every tab switch
also has about 1 s of fixed cost (switch round trip, login check, navigation).

Changes, measured locally against the live database with the real pages
(read-only, writes blocked; median of warm runs; same rendered output):

| Page | Requests | Time |
| --- | ---: | ---: |
| Lobby (9 lobbies) | 44 → 20 | 1,308 → 775 ms |
| Map | 9 → 8, 5 → 3 waiting rounds | 512 → 290 ms |

- Lobby cards load in three rounds for all cards together (`lobby_ui.load_summaries`):
  scores plus the picture permission check, then all leader names in one
  request (`db.list_membership_names`), then one picture batch. Before, each
  card ran its own chain of name, roster, credential, friendship, picture row,
  bucket and download reads.
- Map starts the picture permission check (`db.profile_picture_access`) in its
  first round of reads.
- The private-bucket check runs once per bucket every 10 minutes per server
  process instead of before every photo (see SECURITY.md).

Not changed yet: bottom navigation still uses a button plus `st.switch_page`
(an extra round trip per tab switch; `st.page_link` would avoid it), and the
Lobby page reads pending invitations after the memberships instead of together.

## Follow-up audit — 21 November 2026

The measurements below distinguish live service requests, synthetic Streamlit
rendering and the public browser. Live reads used the configured Supabase
project. The sampled gallery had 21 visible rows and the selected season had
37 check-ins. Reports contain counts, timings and response sizes.

### Where the time goes

| Live operation | Observed median | What it covers |
| --- | ---: | --- |
| First Supabase REST request | 136–315 ms | Separate runs, including client connection setup |
| Account, membership and season reads | 76–104 ms | One request per read, measured from this machine |
| Season entries | 86–102 ms | 37 entries, 35 kB |
| Lobby selected in Games | 193 B | Previously 3,683 B for the entire directory; network time varied |
| Recent Check-in query | 2 B | Previously 902 B for this member; no cooldown-window entries in this sample |
| Lifetime history, six lobbies/seasons | 321 → 200 ms | 18 → 3 requests, identical returned seasons, entries and transfers |
| Gallery listing | 243–323 ms | Three requests before the photos themselves |
| Twelve gallery previews, cold → reused | 644 → 278 ms | 16 → 3 requests and 1.97 MB → 5.4 kB from Supabase |
| Open original photo | 475 ms | Five requests, previously six; the original still comes from Storage |
| Profile photo metadata for a user without an avatar | 158–198 ms | Two requests; an avatar would add a Storage read |
| Public Streamlit HTML | 406 ms | HTTP only; up to 1.9 s in the runs |
| Public Streamlit screen / open login form | 8.6–9.3 s / 1.8–2.9 s | Three fresh Chrome sessions in the app's embedded frame on the deployed version |
| CARTO style and one Lisbon vector tile | 86 ms / 21 ms | The browser may request several tiles |
| Google Fonts CSS and one font file | 93 ms / 50 ms | Browser font loading is separate |
| Brevo endpoint | 74 ms | HTTP 401 from a request without credentials; delivery was exercised with test doubles |

The gallery comparison is for the same twelve previews with three samples.
The cache is local to each browser session and keeps at most 48 previews for
45 seconds. Membership, team, consent, expiry and stored photo reference are
read fresh before reusing a preview. The gallery discards cached previews when
access changes. Opening a photo still reads its original. A cold gallery still
downloads the originals from Storage. The database transfer for the cold
gallery and the Streamlit hosting path are the largest remaining gaps measured.

The app bundles historical reads across lobbies, players and seasons with
bounded filters and pagination. The Check-in page reads only the relevant
cooldown or duplicate window and explicitly includes an outstanding capture ID
to recover an older committed submission. Closed or already posted check-ins
skip the cooldown read when there is no capture to recover. Games overlaps its
Chug Duel and invitation reads. The Lobby overview loads the player's lobby
records and seasons together, and opening a lobby skips a redundant full rerun.
The remembered-device bridge reads saved sign-in once per session and still
handles explicit writes and clears. The theme reader avoids a round trip when
the browser has no saved preference.

Actual page code with synthetic 50 ms reads and three warm renders per page
measured Lobbies at 444 → 392 ms, Games at 322 → 285 ms, and Activity at
389 → 344 ms. Profile, Ranks, the sample Map, Check-in and Photos were within
7 ms of baseline in this fixture. Its photo and check-in rows have very little
data, so the script does not represent the live Storage bytes or long check-in
histories.

A separate CPU test gave all 48 real territory outlines the same synthetic
owner. Marker preparation took 603 → 302 ms on the first run and 566 → 31 ms
at the warm median with identical marker output. Geometry cache keys include
the actual coordinates. Badge layers send their own required fields, which
avoids duplicating photo data in the initials layer. The GPS component starts
while the other map work is pending. The GPS acceptance boundary comes from
the original territory data.

### Reproduce and verify

```sh
python scripts/audit_app_performance.py --live --external --output /tmp/wegopub-perf.json
python scripts/benchmark_app_pages.py
python scripts/benchmark_page_performance.py --map-markers
python -m pytest -q
python scripts/verify.py --group components database mutations
```

1,199 Python tests and 13 component, migration, SQL and mutation checks
passed. Eight concurrent transaction cases passed on disposable native
PostgreSQL plus a separate real server restart and state check. The native
test copy used PostgreSQL's built-in UUID generator because the local
distribution omits pgcrypto. The repository migration chain also passed
unchanged with the normal test harness. Chrome exercised navigation at 390
and 1,280 pixels, gallery paging, profile stats, a rejected check-in followed
by successful location recovery and scoring, and Chug, Quiz and Time Duel
browser cases. Live service checks were read-only. Production writes,
physical phone camera/GPS permissions and delivery to a real mailbox were
outside those checks.

The first public Chrome probe looked in Streamlit's wrapper page. A second
probe verified the signed-out screen and login form inside the app frame and
provided the timings above. The local app showed its signed-out home in
about 1.5 s before the bridge changes and 1.0 s after, in individual browser
samples. A phone run through
the deployed check-in flow is still part of release verification. The changes
on the efficiency branch need the usual review and deployment. They require
no migration.

The next storage improvement is to generate a private thumbnail on upload
and keep the original for the detail view. It would also need retry, deletion
and retention coverage for both objects and a fallback for existing photos.
For production start time, compare a cold and a warm browser session against
the Streamlit deployment logs. Record the time to the first interactive
screen, separately from the initial HTTP response.

## Original audit — 20 November 2026

This audit starts from main `ad4c9cf` on `codex/app-performance-audit` and
also integrates main `80b010a` (including login hardening and the latest layout)
before final verification. It preserves
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
- Installed SDK defaults allow 120 seconds for PostgREST and 20 for Storage;
  Brevo uses an explicit ten-second timeout. On an outage, these can dominate
  waiting. A separate read-only deadline/recovery design should be tested
  before shortening write deadlines or adding automatic mutation retries.
- Tests include upstream Streamlit/pandas deprecation warnings. They passed;
  dependency warnings are not suppressed as a performance fix.

## Final verification of the combined branch

After integrating main `80b010a`, the complete isolated Python suite passed
**1,034 tests in 158.02 seconds**. Camera, Location and Reaction component
checks also passed against the combined source. The read-only credential
pattern scan covered 299 tracked paths, found no supported secret patterns,
and confirmed the local secrets file is untracked/ignored.

The browser verified the current actual-page fixture: Profile → Photos,
25-photo pagination (12 + 12 + 1), an opened original with metadata, Ranks,
Map, Profile and Lobbies. The public deployment's registration and login
views loaded without submitting credentials or creating an account. This
does not deploy or authenticate the new performance branch on that URL.
Physical-phone verification and actual email delivery remain the explicit
checks listed above. No shared game data was written or cleaned up.

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

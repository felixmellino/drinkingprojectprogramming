# Focus Challenge — implementation handoff, 19 November 2026

The contributor confirmed teammate approval and requested the complete game.
R-M06–R-M09 in `docs/ontology/RULES.md` are the active implementation contract.
This branch includes the game, authoritative persistence and the scoring effect.
Shared Supabase migration/activation and human phone difficulty calibration are
still required. No shared-project records were changed during development.

## Activation

1. Review this branch and migrations 014/015 with a teammate.
2. The Data owner applies 014 after 010, 011, `012_qa_minigames.sql` and
   `013_checkin_photo_privacy.sql`. Migration 014 is repeatable. Do not rerun
   `schema.sql` on an existing database. Fresh databases also need these
   feature migrations. Then apply `015_focus_test_replays.sql`. Both scripts
   are repeatable in this order; when 014 is already installed, apply only 015.
3. Merge the reviewed PR and deploy/restart with the same pinned requirements.
4. Select an **existing explicitly marked QA season** or create one with the
   Wednesday 08:00 test-season option. The frozen `test_mode` flag must be JSON
   boolean true; names alone do not enable QA. No new season or uploads are
   needed. Older QA snapshots use the fixed v1 Focus configuration, without
   modifying their saved rules. Older normal snapshots remain disabled.
5. In QA, start with zero uploads, fail and retry, then win and replay while
   the boost is active. QA permits unlimited sequential plays throughout an
   active season, even outside the weekly drink window. Normal seasons retain
   five/seven/nine unlocks, one win per evening and the scoring window.

No new dependency, public database privilege or credential is needed. A missing
migration shows a setup message. Existing Check-in/Chug Duel scoring remains
usable; a failed boost preview never determines the authoritative award.

## Player workflow

Open Minigames → Focus Challenge. The page shows the three tasks, next count
threshold and any active boost. Retakes/retries/rejected posts do not count;
the player's shared duel entry does. Deleted photos leave accepted entries
and their count intact. After a failed attempt the normal-season threshold rises
by two. QA instead shows a test-mode label and immediate Start, without progress
or a nightly win block. Finish the result screen with Back to games, then reopen
Focus to replay. A missing migration 015 shows an explicit setup message.

Start opens a full-screen board. Each trial has a new private server-generated
challenge. Reaction uses five independent waits of 1.5–4.5 seconds and a median
of at most 350 ms, without early taps. Memory shows seven positions on a 3x3
grid, flashing 650 ms with 200 ms gaps, then allows fifteen seconds for input.
Precision requires twelve correct targets in twelve seconds. Targets move with
consistent margins/minimum distance; tapping the play area elsewhere fails.

Ready screens time out after thirty seconds; reaction responses after two.
The entire attempt lasts at most three minutes, and ends sooner at 06:00,
scoring closure (normal seasons) or season end. Closing/reloading does not reset it or generate
new content. Memory/reaction steps and precision checkpoints are persisted.
The browser caches pending evidence to recover a lost reply. Two seconds of
server delivery grace accommodates transport; task timers do not gain time.

On a saved win, an automatic x1.5 effect lasts up to sixty minutes, bounded by
scoring/season closure. It can cross 06:00 and never stacks. An old evening's
unexpired boost prevents starting another Focus attempt until expiry. There
is one successful reward per member/lobby evening, independently of Chug roles.
Active Focus and started Chug games cannot overlap for the same member.
The QA exception removes count/win/active-boost gates. Further QA wins refresh
expiry to sixty minutes from that win, capped at season end, never stack factors
or accumulate hours. QA still requires an active season, keeps the 06:00 attempt
cutoff and all task deadlines. Ordinary drink scoring keeps its weekly window.

Only ordinary Check-in awards are boosted, including matched territory points.
The previous owner's 25% uses that boosted award. A 1-point drink becomes 1.5;
its owner income is exactly 0.375. A corrected 3-point drink becomes 4.5 with
1.125 owner income. Self/team-self income remains zero. In teams, only the
successful player's entries receive the boost. Chug Duel sources/transfers do
not receive it, even when its winner currently has a Focus effect.

## Code and data

- `core/focus_challenge.py`: frozen per-season configuration, availability and
  bounded component-message validation. `new_rules()` copies the configuration
  into new seasons. SQL reads that saved snapshot for thresholds and timing.
- `components/focus_challenge/`: accessible touch/keyboard controls, monotonic
  timing, server-anchored deadlines, pending-event recovery and precision prefix
  checkpoints. `logic.js` has pure helpers exercised by the Node test.
- `focus_challenge_component.py`, `focus_challenge_ui.py`, `minigames_ui.py`:
  authenticated page integration, progress, start/recovery, board and results.
  Three-second polling preserves a keyed component; it does not restart clocks.
- `data/db.py`: thin RPC wrappers and numeric row conversion. Clients send
  action evidence and expected revision, never a trusted win or points factor.
- `014_focus_challenge.sql`: private attempts, server random material,
  membership checks, lobby transaction locks, idempotent start/results, stage
  validation, deadlines, one-running/one-win indexes and immutable boost source.
- `015_focus_test_replays.sql`: explicit-QA detection, effective configuration
  for existing QA snapshots, server-derived attempt flag and a normal-only
  one-win index. RPCs retain membership checks and a single running game. New
  QA wins refresh one boost; the immutable source still records the actual win.
- `DrinkEntry.focus_attempt_id`: the source grant at check-in receipt time.
  Corrections keep it; replay recomputes the corrected award with that original
  multiplier after expiry. Neither correction nor replay compounds multipliers.
- `points_awarded` and `owner_bonus_quarters` become exact SQL numeric values.
  Existing quarter-unit readers remain compatible; a half-quarter means 0.125
  points. Python uses only binary-exact integer/half-unit values here. The
  common formatter retains three decimals. No historical award is rescaled.
- Check-in previews, saved receipts, photo history, leaderboard and territory
  replay use those awards. Capture-gap hints accommodate half-point awards once
  Focus entries are present. Photo deletion/retention and Chug transfers remain
  unchanged.

## Security and limits

Public/anon/authenticated roles cannot read attempts or execute game RPCs.
Only the existing trusted server role can call them; every public game RPC
also verifies the supplied player's current membership. Private challenge
material is persisted once per attempt, using cryptographic UUID entropy with
bounded rejection sampling, never a calendar/player/attempt-number seed.
Only the current stage's required content is sent to the component. Memory
answers are omitted from later snapshots once its presentation ends.

Timers and taps still originate in a browser and remain tamperable. Server
validation prevents unauthorized awards, skipped phases, duplicate rewards
and refresh-based rerolls; it cannot prove that a human physically made each
tap. This is the class project's trust-based skill game, not a medical test,
automated cheating detector or assessment of fitness to ride/drive. No health
label, photo, microphone, motion-sensor data or exact GPS is collected by Focus.
Attempt records are part of competition history; the project's broader account
history/retention policy remains applicable.

## Verification

- Python: `python -m pytest -q`. Development runs additionally block live
  Supabase client creation. The latest full regression suite passed 652 tests. Focus tests cover configuration freezing, safe
  bridge messages, exact fractional replay/corrections, team scope, errors,
  unlock UI, restart recovery and keeping older seasons disabled.
- Browser state machine: `node tests/focus_component.cjs` checks reaction
  timing/early taps, unchanged clocks during polling/reload, memory playback,
  precision prefixes, misses/timeouts and terminal results without new rewards.
- Isolated PostgreSQL: `node tests/focus_postgres.cjs PATH_TO_PGLITE_INDEX_CJS`.
  Uses optional PGlite already used by the project; never shared Supabase.
  Covers migration repeat, real service-role grants and anonymous denial,
  separate identities, five/seven/nine gates, persisted random material,
  stale/invalid actions, all stages, one reward, corrections, exact owner
  income, Chug exclusion, expiry, midnight/06:00 carry-over, timeout, team scope,
  old snapshots and reopening a saved running attempt/database after restart.
  Controlled entropy is injected only in this isolated test to avoid random
  flaky assertions; production uses cryptographic entropy.
- QA replay update: full Python suite **652 passed** with live client creation
  blocked; Focus/Chug UI subset **56 passed**. The PostgreSQL checks also cover
  existing QA snapshots, zero-upload start, retry after failure, multiple wins,
  nonstacking 1.5 awards, restart, repeat migration and strict boolean QA flags.
  QA games outside the weekly window remain playable, while drink submissions
  and expired-season games are rejected. The component tests check QA result text.
  A browser opened an existing QA snapshot with zero entries, started the actual
  game and returned to an enabled Start after the attempt ended.
- Existing `tests/scoring_postgres.cjs` and `tests/chug_duel_postgres.cjs`
  regression suites passed after the shared rule/default changes.
- A 390x844 browser completed reaction, observed and repeated the actual
  randomized memory flashes, completed precision and saw the saved win through
  the real component and RPCs against isolated PostgreSQL with five synthetic
  accepted entries. The saved reaction times were 193/114/171/111/215 ms; the twelve precision taps finished at 3709 ms. This proves the automated software flow, not human difficulty balance.

Still check after deployment: installation of both 014 and 015, immediate QA
play with zero uploads and repeated wins, real iPhone/Android timing and target usability,
switch-away/reconnect on mobile networks, an actual boosted check-in and its
territory/leaderboard/history, teammate review and shared migration installation.

## Integration with photo sharing — 19 November 2026

The latest main adds default-OFF account photo sharing, team consent and
attributed photo frames. This branch keeps those access checks and frames,
while retaining Focus source labels and exact fractional award details.
R5 keeps Focus eighth-point income; R6/R-PH01 keep the stricter photo policy.
Privacy migration 013 is already applied to the shared project. Focus's new
migration is numbered 014 to avoid colliding with that deployed migration.
Its SQL behavior is unchanged; if an earlier Focus 013 script was already
applied, 014 can still be applied safely because it is repeatable.

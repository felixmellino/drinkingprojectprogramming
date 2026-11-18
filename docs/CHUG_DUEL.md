# Chug Duel implementation handoff

Contributor-authorised rules, 18 November 2026, recorded in RULES.md
R-M01–R-M05. Implemented locally; migration 011 and live database/phone
verification remain pending. The earlier minigame proposal is historical.

## Player workflow

Minigames sits immediately right of the plus in the seven-button bottom bar.
Select any eligible other member of the current lobby, choose the common
drink/size, and send an invitation. The other player accepts on their own
device. The host takes one fresh photo of both drinks; their current GPS is
used for both entries. The same normal scoring window, season dates, two-minute
cooldown for each member and location acceptance rules apply. No extra
time-since-first-post or post-count gate applies to this game.

The host saves the shared check-in, then both players use the split screen on
the host's device. Each half has a separate Ready action. The server arms a
three-second countdown after both are ready; the first subsequent browser
pointer/keyboard event locks the outcome before a network round trip. Only the
host can submit the winner. Participants trust each other about physical
completion; neither the camera nor the app proves a drink was emptied.

Example outside all territories: two 3-point drinks give 3/3 at start, then
6/0 on a recorded win. A started abort keeps 3/3. Territory-linked entries
still give each competitor 3 territory points. Owner income is calculated
normally in entry acceptance order and is never transferred by the duel.
Thus a loser can still have owner income in addition to the zero base award.

## Code and persistence

- `core/chug_duel.py`: 06:00 calendar-night identity (season timezone), separate
  role allowances, pair validation, component message validation and errors.
- `minigames_ui.py` / `pages/7_Minigames.py`: invite, accept/decline, capture,
  readiness, board, result, abort and three-second polling. Identity and lobby
  checks run before rendering; every mutation checks again on the server.
- `components/chug_duel/index.html` / `chug_duel_component.py`: browser timing,
  touch halves and keyboard access. Names use textContent; no public text is
  inserted as HTML. Countdown uses a server-time anchor and a monotonic
  browser clock, so phone wall-clock settings do not bypass it.
- `data/db.py`: membership-checked, metadata-stripped shared capture and RPCs.
  No exact GPS is stored or passed to SQL. One capture produces two private
  JPEG copies at the existing entry-owned paths. Each player can delete their
  own copy under existing R7; the other's copy has its own lifecycle. Both
  expire with the same season's normal photo-retention rules. Failed uploads
  create no scores; unreferenced files use the existing orphan cleanup.
- `migrations/011_chug_duel.sql`: authoritative server receipt clock, lobby
  transaction lock shared with scoring/team membership, role-specific unique
  indexes, participant authorization, phase expiry and atomic two-entry start.
  Public/anon/authenticated cannot access the table or call its RPCs.
- `DrinkEntry.duel_id`: links the two normal source entries. Their agreed
  drink/size cannot be corrected separately (both Python and SQL enforce this).
- On completion only the losing source stores `duel_transfer_to` (the saved
  winning member/team account) and `duel_transfer_order` (a new position in the
  existing scoring sequence). Replay credits/debits that base award at result
  time, preserving every original territory event and owner-income award.
  Terminal duel results are immutable and retries return the saved result.
  Same-result simultaneous ties preserve the previously higher-ranked account.
- `core/scoring_v1.py` replays base and transfer events together. Existing
  leaderboard/map/lobby callers receive the same DrinkEntry list interface.
  Normal corrections replay ownership/income without removing duel transfers.
  Photo history displays the resulting 6/0 season awards and normal territory
  awards. Legacy records and season snapshots are not rewritten.

The old `core/minigames.py` weekly placeholder and its tests remain for legacy
code; Chug Duel does not call it. This is the explicit exception to the earlier
one-game/items-only design. Other proposed minigames are not implemented.

## Boundary defaults

Invitations expire after ten minutes. Accepted setup has ten minutes to start,
and a started game has ten minutes to finish. A phase also ends at the 06:00
rollover, scoring-window close or season end, whichever comes first. Pending
expiry consumes nothing. Accepted cancellation/expiry frees both reserved
roles; started expiry/abort consumes the host's outgoing and guest's incoming
roles while retaining both normal drink awards. Reconnecting can resume a
started game until expiry. One pending outgoing invitation and one
accepted/started game per member avoid overlapping physical games. A player
can subsequently play their opposite role that evening. A different lobby
has independent allowances. Team membership is checked again on start;
scored entries then retain the existing immutable team identities.

## Verification

Verified locally on 18 November 2026: full Python suite **507 passed**;
isolated PGlite integration **passed**, including disk reopen; actual browser
board and two independent synthetic Streamlit sessions **passed**. The browser
workflow used the real camera component with a fake video device, synthetic
GPS/services, and 390 px mobile plus desktop screenshots. Real phone hardware
and the shared Supabase deployment were not used. `git diff --check` passed.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Targeted workflows: `tests/test_chug_duel.py`, `tests/test_chug_duel_db.py`,
`tests/test_chug_duel_ui.py`, `tests/test_app_navigation.py`, plus existing
scoring, team, photo and standings tests. UI tests use independent AppTest
sessions and isolated services; they do not connect to Supabase.

Optional database integration uses Node and `@electric-sql/pglite@0.3.14`
installed under ignored `.venv/chug-test`, without a new production dependency:

```powershell
$env:SCORING_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
node tests/chug_duel_postgres.cjs .venv/chug-test/node_modules/@electric-sql/pglite
```

It verifies migration repeatability, authorization, role limits, competing
accepts, atomic cooldown rollback, countdown enforcement, idempotent 6/0
transfer, team identities, expiry, aborts, midnight/06:00 and disk-backed
PostgreSQL reopen persistence. The clock substitution exists only in the
isolated test migration copy. PGlite queues queries in one engine; this is not
a multi-connection load test of hosted PostgreSQL.

Optional browser check with installed Playwright/Chromium or Edge:

```powershell
node tests/chug_duel_browser.cjs
```

This exercises the actual HTML board (readiness, early taps, countdown,
first-tap lock and escaped names). `CHUG_QA_URL` can target an explicitly
synthetic localhost Streamlit fixture for a two-browser workflow and mobile
screenshots. It refuses remote hosts. QA images stay under ignored `.venv`.

## Before live use

Apply `migrations/011_chug_duel.sql` after 010 through the team's normal
database migration process, then deploy the reviewed branch through a PR.
No shared/live migration is claimed applied by this change. With two real
accounts on phones, verify invitation updates, permissions for the common
camera/GPS, touch halves/countdown, both histories and the leaderboard. Repeat
after a Streamlit restart; check cancellation and a started abort, then
confirm the separate outgoing/incoming limits. For true concurrency, use two
database connections to race acceptance/start/result against the same lobby.

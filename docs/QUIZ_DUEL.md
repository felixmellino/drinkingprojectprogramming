# Quiz Duel implementation

19 November 2026. Local feature branch: `codex/quiz-duel`.
The code and disposable-database/browser tests work. The shared database and
deployed app have not been changed by this implementation.

## Flow and ownership

Minigames → Quiz Duel → select opponent and 3–10 point stake → recipient accepts
on their account → both ready → countdown → one question at a time. English
general knowledge, multiplication 1–10 and short logic templates form the three
normal rounds. A 2:0 ends early; ties get at most three general-knowledge deciders.

- `core/quiz_duel.py`: limits, stakes, round outcomes, component validation.
- `core/quiz_questions.py`, `data/quiz_questions.py`, `data/quiz/`: private shared
  question packs. The checked-in 100 questions need no manual import.
- `migrations/016_quiz_duel.sql`: transactional state machine, server-clock
  answers, stake reservations, team purses and exactly-once transfer ledger.
- `data/db.py`: service-only RPC wrappers; no answer keys go to the player board.
- `quiz_duel_ui.py`, `quiz_duel_component.py`, `components/quiz_duel/`: lobby,
  invitations and stable full-screen board with reload/retry support.
- `core/scoring_v1.py` replays the separate ledger in season event order.
  Standings, lobby summaries, team cards and profiles include the transfer.
  Territory ownership, drink counts and owner income remain unchanged.

The [rules](ontology/QUIZ_DUEL.md) contain all contributor decisions and operational
defaults. Server receipt time includes network latency; this is casual multiplayer,
not a latency-compensated competitive quiz service.

## Database and release

Apply the reviewed migration 016 after 014 to the shared Supabase project.
It is transactional and repeatable, leaves existing seasons/drinks intact and
does not require migration 015 (it is compatible with that QA Focus migration).
Deploy the reviewed branch via a PR and teammate review; do not push to main.
Quiz setup failures show a clear message until migration 016 is installed.

No new production dependencies, question uploads or browser credentials are
needed. Existing service-key/session architecture is retained: all tables and
RPCs are inaccessible to public/anon/authenticated Supabase clients.

## Verification

With the project's Python environment active:

```powershell
python -m pytest -q
python scripts/prepare_quiz_questions.py
```

Optional local SQL/browser integration tests use PGlite and Playwright installed
in a disposable development directory, not production requirements:

```powershell
$env:SCORING_PYTHON = (Get-Command python).Source
$env:PGLITE_MODULE = 'ABSOLUTE_PATH_TO_PGLITE_DIST_INDEX_CJS'
node tests/quiz_postgres.cjs
node tests/quiz_browser.cjs ABSOLUTE_PATH_TO_PLAYWRIGHT
```

The SQL suite applies the migration twice and covers authorization, invalid
stakes/decks, hidden answers, fixed deadlines, wrong answers, exact timing ties,
early 2:0, higher-score wins, deciders/draws, independent nightly roles, QA repeats,
team reservations, correction protection, forfeit, exactly-once retries and a
disk-backed database close/reopen. Browser integration uses two real Streamlit
sessions and PostgreSQL, verifies identical questions/order, countdown, locked
answer after reload, 2:0 and one transfer, at mobile/desktop sizes.

Local verification: 832 pytest tests passed (315 existing Streamlit/NumPy
deprecation warnings); PostgreSQL and the two-player browser suite passed.
Real phone/network calibration and shared-project/deployed verification remain.

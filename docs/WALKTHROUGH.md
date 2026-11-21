# Repository walkthrough (for the graded presentation)

Every team member should be able to answer each section below without
notes. Any of us can be asked about any part. For a longer plain-language tour
of every file, see [`WORKING_GUIDE.md`](WORKING_GUIDE.md).

## 1. What we built on

- **Solo project:** TODO (owner, link). It already had: TODO.
- **What the team added:** email accounts and remembered devices, lobbies
  (individual and team), scoring v1 with game-night windows, predefined
  territories with GPS verification and a map, photo check-ins with private
  storage, standings and profile stats, friends, and four duels (Chug, Quiz,
  Time, Reaction).

## 2. Architecture: where things live

| Part | Where | Rule |
| --- | --- | --- |
| Screens | `app.py`, `pages/*.py`, `*_ui.py` | Shows data and forms; calls `core/` and `data/`, no game rules here. |
| Game rules | `core/*.py` | Plain Python, no Streamlit and no database. Scoring, windows, location, duels, ranking, auth hashing. |
| Storage | `data/db.py` | The only file that talks to Supabase (Postgres + photo storage). |
| Database rules | `schema.sql`, `migrations/*.sql` | Tables, access restrictions and atomic RPCs; install order in [`MIGRATIONS.md`](MIGRATIONS.md). |
| Browser parts | `components/*/index.html` | Camera, phone GPS, remembered device, duel games. |
| Email | `password_email.py` | Only file that calls Brevo. |
| Drink suggestion | `drink_recognition.py`, `core/drink_recognition.py` | Only file that calls Claude (Anthropic API); the core file checks the answer. |
| Tests | `tests/` | `pytest` for Python, `*.cjs` for components and in-memory Postgres. |

One check-in, end to end: `pages/3_Check_in.py` collects drink, size, photo
and GPS -> `core/location.py` matches the GPS point to exactly one territory
(accuracy must be 50 m or better) -> `core/checkins.py` and the scoring rules
decide if it counts -> `data/db.py` stores it with one database RPC, so points,
territory totals and standings change together or not at all.

## 3. Data: where it is stored and why

- **Supabase (Postgres + Storage), shared team project.** Why: real
  multi-user data, survives app restarts, SQL constraints and RPCs enforce
  rules atomically, photos stay in a private bucket.
- **Limits:** free tier (small database and storage quota); the project
  pauses after a period of inactivity; Streamlit Community Cloud sleeps the app
  when nobody visits. Open both before the demo.
- Photos expire 30 days after a season ends (`data/cleanup_checkin_photos.py`,
  daily GitHub Action).

## 4. Access control and validation

- Every game page calls the shared page start in `shared.py`, which stops the
  page unless a valid signed-in player is in the session.
- The app uses a server-only key; public and anonymous Supabase keys are
  denied on account and game tables. Lobby actions pass the acting player to
  the database (`actor_player`), which checks membership/ownership again.
- Passwords: PBKDF2-SHA256 with 600,000 iterations (`core/auth.py`); remembered
  devices store only a hash of a random token. Login is throttled to ten tries
  per account per 15 minutes.
- Inputs are validated in `core/` (lengths, ranges, allowed values) and again
  by database constraints. The Supabase client sends parameters, never
  string-built SQL. User text shown as HTML is escaped with `html.escape`.
- Details: [`SECURITY.md`](SECURITY.md).

## 5. External services and what happens when they fail

| Service | Used for | If it is down |
| --- | --- | --- |
| Supabase | all data and photos | Page shows "Account service is unavailable. Please try again later." and stops; nothing is half-saved because writes are single RPCs. |
| Brevo | password reset emails | 10 s timeout; the player sees the same neutral message as for an unknown address; no crash. |
| Carto basemap (map tiles) | map background | Territories still draw; only the background is missing. |
| Phone GPS / camera (browser) | check-in | Check-in is refused with a message saying what to allow or retry. |
| Anthropic API (Claude) | suggesting drink and size from the photo | 12 s timeout, no retry; the normal form is shown and the player picks the drink. Points never depend on it. |

## 6. Tests: what they cover and what they do not

- `pytest` (about 1,230 tests, no live database): accepted, rejected and
  boundary cases for scoring, windows (Thursday 18:00 to Sunday 18:00), GPS
  accuracy and borders, duplicates and cooldowns, ties, duels, access checks,
  password reset and API failures (Brevo/Supabase errors are faked).
- `python scripts/verify.py`: also JavaScript components, rule mutations and
  migrations on an in-memory Postgres. CI runs everything on every PR.
- **Not covered automatically:** real phones (camera/GPS permission flows),
  the real Supabase project and its applied migrations, Brevo delivery, and
  Streamlit Cloud deployment. These are manual checks in
  [`VERIFICATION.md`](VERIFICATION.md).

## 7. Why we decided this way

- **Streamlit:** the course stack; fast to build forms and pages in Python.
  Trade-off: every click reruns the script, so we cache the database client
  and keep pages light (see [`PERFORMANCE.md`](PERFORMANCE.md)).
- **Rules in `core/`:** easy to test without a database and easy to explain.
- **Database RPCs for writes:** two players acting at once cannot corrupt
  points or territory ownership.
- **Automatic GPS instead of a buddy confirmation:** fewer steps for players.
- **Claude only suggests the drink:** a photo cannot reliably show the size
  (no scale, mixed drinks look alike), so the player confirms and the points
  stay rule-based and testable. Structured outputs force a fixed JSON answer.

## 8. Known limits and how it could change

- Streamlit polls for duel updates; a real-time service (websockets) would
  make two-phone duels smoother.
- GPS can be spoofed by a determined player; server-side plausibility checks
  (speed between check-ins) would help.
- Free hosting sleeps and pauses; a paid tier or another host removes that.
- Territories are a GeoJSON file; an admin screen could edit them.

# drinkingprojectprogramming (WeGoPub)

WeGoPub: a social drinking-game app where players log drinks with a photo
and GPS location, capture territories on a map, and compete on a season
leaderboard. Game design lives in [`docs/ontology/`](docs/ontology/) and
[`AGENTS.md`](AGENTS.md).

**Deployed URL:** TODO — not deployed yet.

**Team:** TODO — add all four members' names and student numbers here
before submission.

## Local setup

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill
in a real Supabase project's URL and key (never commit the real file — it's
gitignored). Then apply `schema.sql` to that project via its SQL editor.

To enable check-in photos, run
[`migrations/setup_checkin_photo_storage.sql`](migrations/setup_checkin_photo_storage.sql)
in the Supabase SQL editor after the `drink_entries` table exists. It adds the
capture-time column and creates the private `check-in-photos` bucket. It can
also run on a project that already has the column and a private bucket.

Use a server-only Supabase secret or service role key for `SUPABASE_KEY`.
Restrict object access to the app server, which checks lobby membership before
serving an image. Restrict direct writes to player, membership, season, and
drink entry records to the app server so it can rely on those records for
authorization.

In the test project, save a check-in and reopen it under **Lobby photos**
after restarting the app. Verify access with a lobby member and an account
outside the lobby.

### Run the app

```bash
streamlit run app.py
```

### Run the tests

```bash
pytest
```

The test suite (`tests/`) runs without a live Supabase connection.

## Project structure

- `core/` — every game rule, as plain Python with no Streamlit/database
  imports. This is what the tests cover.
- `data/db.py` — the only file that talks to Supabase.
- `pages/` — one Streamlit screen per file; each only calls into
  `core`/`data`, no rules live here.
- `tests/` — one file per `core/` module.

New here, or working on a building block? Read
[`docs/WORKING_GUIDE.md`](docs/WORKING_GUIDE.md) first — it explains every
file in plain language, how `docs/ontology/` connects to the code, the
four building blocks, and the team's workflow rules.

## Known gaps in this first increment

- **No real GPS capture.** The Check-in page takes manual latitude/longitude
  input instead of reading the device's actual location — Streamlit has no
  built-in geolocation. Replace with a browser-location component.
- **Map, Memories, and Minigames pages aren't built yet** — Standings shows
  territory ownership as a list for now. See the build order in
  `AGENTS.md`/the project plan for what's next.
- Several game-rule numbers (points per drink, GPS/photo mismatch
  tolerance, season-length day counts) are placeholders in
  `core/constants.py` — see `docs/ontology/OPEN_DECISIONS.md`.

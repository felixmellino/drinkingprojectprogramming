# drinkingprojectprogramming (WeGoPub)

WeGoPub: a social drinking-game app where players log drinks with a photo
and GPS location, capture territories on a map, and compete on a season
leaderboard. Game design lives in [`docs/ontology/`](docs/ontology/) and
[`AGENTS.md`](AGENTS.md).

**Deployed URL:** TODO — not deployed yet.

**Team:** TODO — add all four members' names and student numbers here
before submission.

## Local setup

Requires Python 3.11+.

The team uses one shared Supabase project. Ask the Data owner for its
credentials through a secure transfer and put them in the ignored local
secrets file. If that project already has the schema, do not run `schema.sql`
again. The Data owner applies reviewed migrations once for the whole team.
Each teammate then pulls the merged code and uses the same project locally.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill
in a real Supabase project's URL and key (never commit the real file — it's
gitignored). Use the **server-only service-role key** for `SUPABASE_KEY`; never expose it
in browser code. The account tables deny access through public/anonymous keys.
For a **new database**, apply `schema.sql` via the Supabase SQL editor.

For an **existing database**, back it up and apply only
`migrations/001_personal_accounts.sql` once, then
`migrations/002_remembered_devices.sql` once, then
`migrations/003_text_territory_ids.sql` once, then
`migrations/004_server_game_tables.sql`. Skip the ones already applied.
Do not recreate the tables.
The migration adds email, unique indexes, recovery codes and login throttling;
it keeps every player ID, membership, drink entry and score. It aborts safely
if existing usernames collide after trimming and ignoring capitalization.
Resolve such collisions with the account owners before retrying.
Migration 004 restricts game tables, including lobby invite codes, to the
server's service-role key. Fresh databases get these restrictions in the
schema. All app database access continues through `data/db.py`.

Password recovery is currently unavailable; no SMTP configuration is needed.
Existing databases need no migration for this removal. Historical account SQL
still defines unused reset-code objects; the app no longer calls them.

To enable check-in photos, run
[`migrations/setup_checkin_photo_storage.sql`](migrations/setup_checkin_photo_storage.sql)
in the Supabase SQL editor after the `drink_entries` table exists. It adds the
capture-time column and creates the private `check-in-photos` bucket. It can
also run on a project that already has the column and a private bucket.
It removes exact GPS coordinates from legacy entries, keeping their points
and assigned territory. Re-run it if an older photo setup was already applied.

The script restricts direct access to membership, season, and drink entry
records to the server, and blocks anonymous and authenticated Supabase clients
from the photo bucket. The app checks the signed-in player's lobby membership
before serving an image. Player accounts keep the access restrictions from
the account migrations.

In the test project, save a check-in and reopen it under **Lobby photos**
after restarting the app. Verify access with a lobby member and an account
outside the lobby.

The [security and data handling protocol](docs/SECURITY.md) describes photo
access, upload limits, secrets, and the privacy decisions to complete before
collecting real player photos.

Owners can delete their photo in **Lobby photos** while keeping the score.
Photo access ends 30 days after its season ends. The Data owner must schedule
`python -m data.cleanup_checkin_photos --apply` on the server at least daily
and monitor failures. Without `--apply`, the command only reports counts.
It removes expired photos and abandoned uploads older than 24 hours, keeping
all scored entries. Physical deletion happens on a successful cleanup run.

### Run the app

```bash
streamlit run app.py
```

### Run the tests

```bash
pytest
```

The test suite covers pure logic and Streamlit forms with mocked database
services; it needs no live Supabase connection. Run from the repository
root. The mocks do not verify PostgreSQL migrations.

## Accounts

Profile has one Create account / Log in selector; only the chosen form is shown.
Password recovery and account upgrades are currently unavailable.
First visit shows registration and login. Every game page requires a signed-in
account. Registration requires first name, surname, unique username, unique
email and a password of at least 8 characters, entered twice. Email and
username uniqueness ignore surrounding whitespace and capitalization.
Email verification is not required. Only the username is public.

Returning players log in with email and password. The optional **Remember
password** checkbox keeps the device signed in for 30 days. It saves a random
opaque token in browser local storage and only its hash in Supabase; no password
is saved in the browser. Remembered access survives a browser or app restart.
Unchecked means login lasts for the current Streamlit session only. Logout
revokes the current device's token and clears its storage; a password change
invalidates all remembered tokens. If browser storage is blocked, login still
works for the current visit. Serve the deployed app over HTTPS.

Existing player IDs and all linked game records are retained. Legacy accounts
without an email cannot use email login: an administrator must link the correct
email and replace their credential hash while retaining the original player ID.
There is no self-service PIN upgrade flow.

Logins allow ten attempts per account per 15-minute window.
Password changes invalidate previous sessions on their next action.
Logout clears the browser session and remembered device; accounts and progress remain in Supabase.

### Verify against a configured Supabase project

1. Apply the migration to a copy of existing data; confirm player IDs,
   membership IDs and drink entries remain unchanged.
2. Log in with a test account and confirm the same lobby and standings after
   restarting Streamlit. The player
   may need to select their active lobby again after logging in.
3. Try a duplicate username/email with different capitalization and invalid
   or mismatched passwords. Confirm no account or points are added.
4. Tick Remember password, close and reopen the app, and confirm login is
   restored without entering credentials. Log out and reopen: login must be
   required. Repeat with the checkbox unticked; a fresh browser session must
   require login. Verify an administrator password change also cancels remembered access.
5. Open each game page while logged out. Confirm no game content is shown.
   Verify an anonymous Supabase key cannot read players/remembered-device records or
   call the account RPCs.

This live migration/restart check still needs the configured Supabase
project; the automated suite does not replace it.

## Project structure

- `core/` — every game rule, as plain Python with no Streamlit/database
  imports. This is what the tests cover.
- `data/db.py` — the only file that talks to Supabase.
- `account_ui.py` — one account form with registration and login.
- `device_login.py` and `components/remember_device/` — persistent device login.
- `migrations/` — changes for already-populated databases.
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

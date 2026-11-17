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
gitignored). Use the **server-only service-role key** for `SUPABASE_KEY`; never expose it
in browser code. The account tables deny access through public/anonymous keys.
For a **new database**, apply `schema.sql` via the Supabase SQL editor.

For an **existing database**, back it up and apply only
`migrations/001_personal_accounts.sql` once, then
`migrations/002_remembered_devices.sql` once, then
`migrations/003_text_territory_ids.sql` once. Skip the ones already applied.
Do not recreate the tables.
The migration adds email, unique indexes, recovery codes and login throttling;
it keeps every player ID, membership, drink entry and score. It aborts safely
if existing usernames collide after trimming and ignoring capitalization.
Resolve such collisions with the account owners before retrying.

Set the SMTP entries shown in `.streamlit/secrets.toml.example` to enable
Forgot password. Port 465 uses implicit TLS; other ports use STARTTLS
(usually 587). Missing mail settings show a recovery-unavailable message;
registration and login still work. Credentials can also be set as environment
variables. Recovery messages require a real sender configured with your mail
provider.

### Run the app

```bash
streamlit run app.py
```

### Run the tests

```bash
pytest
```

The test suite covers pure logic and Streamlit forms with mocked database and
email services; it needs no live Supabase connection. Run from the repository
root. The mocks do not verify PostgreSQL migrations or real email delivery.

## Accounts

Profile has one Create account / Log in selector; only the chosen form is shown.
Forgot password is expandable beneath login. There is no account-upgrade screen.
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

Forgot password emails a random code valid for 15 minutes, with at most one
request per account per minute. Paste the code and email into the reset form
and enter the new password twice. Codes are hashed in the database and
consumed atomically so an expired or reused code cannot reset a password.
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
4. Request a recovery code and check delivery. Reset once, then try reusing
   the code and a code older than 15 minutes; both must fail. Restart the
   app and confirm only the new password works.
5. Tick Remember password, close and reopen the app, and confirm login is
   restored without entering credentials. Log out and reopen: login must be
   required. Repeat with the checkbox unticked; a fresh browser session must
   require login. Verify a password reset also cancels remembered access.
6. Open each game page while logged out. Confirm no game content is shown.
   Verify an anonymous Supabase key cannot read players/recovery/remembered-device records or
   call the account RPCs.

This live migration/restart/email check still needs the configured external
services; the automated suite does not replace it.

## Project structure

- `core/` — every game rule, as plain Python with no Streamlit/database
  imports. This is what the tests cover.
- `data/db.py` — the only file that talks to Supabase.
- `account_ui.py` — one account form with registration, login and expandable recovery.
- `device_login.py` and `components/remember_device/` — persistent device login.
- `data/mail.py` — recovery email transport using the Python standard library.
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
- **No real photo storage.** Photos aren't uploaded to Supabase Storage yet;
  only a placeholder reference is saved.
- **Map, Memories, and Minigames pages aren't built yet** — Standings shows
  territory ownership as a list for now. See the build order in
  `AGENTS.md`/the project plan for what's next.
- Several game-rule numbers (points per drink, GPS/photo mismatch
  tolerance, season-length day counts) are placeholders in
  `core/constants.py` — see `docs/ontology/OPEN_DECISIONS.md`.

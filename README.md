# drinkingprojectprogramming (WeGoPub)

WeGoPub: a social drinking-game app where players log drinks with a photo
and GPS location, capture territories on a map, and compete on a season
leaderboard. Game design lives in [`docs/ontology/`](docs/ontology/) and
[`AGENTS.md`](AGENTS.md).

**Deployed URL:** https://wegopubnow.streamlit.app/

**Team:** TODO — add all four members' names and student numbers here
before submission.

## Hosting (deployed app)

The public app runs on **Streamlit Community Cloud** at
https://wegopubnow.streamlit.app/ and uses the team's shared Supabase project
(region West EU) as its database and photo storage.

- **Source:** repository `felixmellino/drinkingprojectprogramming`, branch
  `main`, main file `app.py`. Every merge into `main` redeploys the app
  automatically within a few minutes.
- **Python:** 3.14 (chosen when the app was created; it can only be changed by
  deleting and re-creating the app). Dependencies come from the pinned
  `requirements.txt`.
- **Secrets:** set in the app's Settings → Secrets, never in the repository:
  ```
  SUPABASE_URL = "https://<project>.supabase.co"
  SUPABASE_KEY = "<legacy service_role key, starts with eyJ>"
  ```
  Use the legacy `service_role` key (Supabase → Project Settings → API Keys →
  Legacy API keys). The newer `sb_secret_…` key is rejected with
  "Invalid API key".
- **Territories:** on its first start after a deploy, the app copies
  `data/territories.geojson` into the database (`shared.get_territories()`),
  so editing the file and merging is all that's needed.
- **Location on phones:** browsers only share GPS over HTTPS and after the
  player allows it. The app asks once right after login. On iPhone, if it
  says location is blocked: Settings → Privacy & Security → Location Services
  → Safari Websites → While Using the App; then in Safari tap "aA" →
  Website Settings → Location → Allow.
- **Before a demo:** the free plan puts the app to sleep after a few days
  without visitors. Open the URL once beforehand and click "Wake up" if shown.
- **Check-ins** are only scored Thursday 18:00 – Sunday 18:00 (lobby time);
  the map and location work at any time.

## Local setup

Requires Python 3.11+.

SDK upgrade and live photo-storage verification, including daily GitHub
Actions cleanup setup: [storage verification](docs/STORAGE_SDK_VERIFICATION.md).

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

The app pins `supabase==2.34.1` to support the current Storage bucket
response, including its `versioning_status` field. Use Python 3.11 or newer
(Python 3.12 is also supported). After pulling this upgrade, reinstall
`requirements.txt` in your local environment and restart the app. Update
the deployed environment too. Keep using the team's server-only credentials;
an SDK upgrade does not require recreating the database or changing keys.

For a **new database**, apply `schema.sql` via the Supabase SQL editor.
Territories load automatically from `data/territories.geojson` into the
database the first time the app runs (see `shared.get_territories()`) —
no separate seed step needed.

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

### Scoring v1 setup

After the base schema, account/territory migrations, server game-table security
and photo setup, apply [`migrations/005_scoring_v1.sql`](migrations/005_scoring_v1.sql).
Do not rerun `schema.sql` on the shared existing project. New projects also need
migration 005 after the base schema and photo setup.

Existing populated seasons remain legacy, preserving their points and rules.
New lobbies start scoring v1 with a chosen timezone. Each lobby runs one
competition; after its duration ends it stays in Past Lobbies and cannot be
renewed. Create another lobby for a new competition. Rules, timezone and
dates are frozen; historical points and ownership are preserved.

The new scoring provides the 1-5 category/size table, additional 25% owner
season income, exact quarters, Thu 18:00-Sun 18:00 lobby-time eligibility,
a shared two-minute cooldown and author corrections with downstream replay.
History includes point breakdowns and revision records. See the
[implementation/Data handoff](docs/SCORING_IMPLEMENTATION.md) and
[current ontology contract](docs/ontology/SCORING_V1.md) for defaults, testing
commands and the remaining live checks. The three-page PDF is the historical
team-review proposal. Camera and phone GPS now start automatically when
Check-in opens. For Wednesday testing, create a new lobby with **Test season**
selected; its window is Wednesday 08:00–Sunday 18:00. Normal and existing
seasons retain their rules. See [camera and QA seasons](docs/CAMERA_AND_QA_SEASONS.md).

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

On reconnect, each new server session requests the saved token with a fresh
request ID, even if the browser's storage component is still open. The account
form waits for that read before appearing. Regression coverage in
`tests/test_account_ui.py` checks delayed reads and lost server state; token
expiry, password changes and logout remain covered by
`tests/test_remembered_sessions.py`.

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
- `phone_location.py` and `components/phone_location/` — automatic phone GPS for Check-in and Map.
- `map_ui.py` and `pages/5_Map.py` — territory map coloured by owner.
- `migrations/` — changes for already-populated databases.
- `pages/` — one Streamlit screen per file; each only calls into
  `core`/`data`, no rules live here.
- `tests/` — one file per `core/` module.

New here, or working on a building block? Read
[`docs/WORKING_GUIDE.md`](docs/WORKING_GUIDE.md) first — it explains every
file in plain language, how `docs/ontology/` connects to the code, the
four building blocks, and the team's workflow rules.

## Known gaps in this first increment

- **Testing GPS on a laptop:** Check-in and Map only use the browser's real
  location, followed automatically. To test or demo a territory you're not
  standing in, open Chrome DevTools → More tools → Sensors → Location and set
  the coordinates (e.g. 38.7133, -9.1456 lands in Shortys).
- **The Minigames page isn't built yet.** See the build order in
  `AGENTS.md`/the project plan for what's next.
- Scoring v1 has an implemented point table and weekly window. Legacy/minigame
  constants and calendar-month season
  semantics still need team review; see `docs/ontology/OPEN_DECISIONS.md`.

### Profile friends

For existing databases, apply `migrations/006_friendships.sql` once after
migration 004. Fresh databases running `schema.sql` already include it.
Restart the app, log in and open **Profile**. Search any player's username
(partial and case-insensitive), send a request, then use the recipient's
Profile to accept or decline. Outgoing requests can be cancelled; either
friend can remove the friendship. Friends lists are private, and a decline
prevents either player from sending another request for that pair for ten
minutes. Use **Refresh friends** to load actions made by another player.

Tests: `python -m pytest tests/test_friends.py tests/test_friends_ui.py tests/test_friends_db.py -q`.
The UI tests use a persistent fake repository across fresh Streamlit
sessions. Real PostgreSQL concurrency, migration installation and saved
state after a server restart still require verification against Supabase;
see the Profile friends checklist in `docs/WORKING_GUIDE.md`.

Migration `005_scoring_v1.sql` adds scoring; `006_friendships.sql` adds
friends. The friendship migration was previously named `005_friendships.sql`;
only its filename changed. If the old filename was already applied, do not
run it again under the new name. Existing databases need each feature's
migration once. Fresh databases already include friends in `schema.sql`, but
still need `005_scoring_v1.sql` after photo setup as described above.

### Profile menu

Profile opens Edit profile, Friends, My stats and Account & security as
separate views with Back to Profile. Log out signs out immediately. Players
can edit username/first name/surname; email stays read-only. Password changes
require the current password and sign out all devices. My stats uses the
selected lobby's current season (points, rank and territories owned).
Name/password changes need no new migration beyond the account indexes/access
rules already described above. Profile pictures need migration 008 below.

Validation: `python -m pytest tests/test_profile.py tests/test_profile_ui.py tests/test_account_ui.py tests/test_friends_ui.py -q`.
Before deployment, use a test account to save a name change, restart Streamlit,
then verify it remains saved and its friends/scores remain linked. Change that
test account's password, verify old credentials and remembered devices fail,
and log in with the new password. Automated persistence checks use a fake
repository; they do not replace this live Supabase check.

### Profile pictures

The Data owner applies [`migrations/008_profile_pictures.sql`](migrations/008_profile_pictures.sql)
after account setup, for both new and existing databases. It creates the
server-only picture reference table and private `profile-pictures` storage
bucket. Do not rerun `schema.sql` on the shared project. Friends visibility
also needs the existing `006_friendships.sql` migration.

Edit profile offers Upload photo / Take photo, an automatic circular centre
crop preview and Save picture. JPEG, PNG and WebP are supported (10 MiB,
20 megapixels; still images). Saved pictures persist across devices. Replace
or Remove picture is available; removal shows initials. Pictures appear in
Profile and friend lists/requests, with access checked against current
accepted/pending relationships. They do not appear in unrelated search results.

Schedule `python -m data.cleanup_profile_pictures --apply` daily to remove
unlinked uploads older than 24 hours; omit `--apply` for a dry run. Current
pictures are kept. Apply the migration and complete the live camera/library,
restart and audience checks in `docs/SECURITY.md` before claiming deployment
verification. These scripts have not been applied to the shared project by
this local implementation.

Tests: `python -m pytest tests/test_profile_photo.py tests/test_profile_picture_db.py tests/test_profile_picture_ui.py -q`.

### Lobby migration 007 compatibility revision

After schema/account setup and `005_scoring_v1.sql`, the revised
[`007_lobby_battles.sql`](migrations/007_lobby_battles.sql) adds a private,
read-only lobby snapshot view. It preserves the current create/join/start
flow and scoring rules. Use the revised file from reviewed, merged `main`;
the original recovered SQL in PR #17 is incompatible and must not be run.
If an old `lobby_states` table already exists, stop for separate migration
review. Do not drop it or rerun the base schema. No new runtime dependencies
or application write calls are required. Friends and profile-picture setup
are independent.

The owner-managed lobby feature remains deferred. See
[`docs/LOBBY_MIGRATION_REVIEW.md`](docs/LOBBY_MIGRATION_REVIEW.md) for the
scope, deployment checks and exact disposable PostgreSQL test commands.

### Lobby cards and fixed duration (18 November 2026)

Lobby lists all joined lobbies directly: running competitions newest-started
first in green, then Past Lobbies newest-finished first in grey. It selects
the newest running lobby automatically. Clicking anywhere on a card opens
a popup showing the lobby name, invite code and all members over the blurred
lobby overview. Long member lists scroll. View leaderboard below the list
closes the popup and opens the full Leaderboard for that lobby; there is no
top-three preview. Close, ×, outside click and Escape dismiss the popup.
Member rows offer Add friend or Accept/Decline for incoming requests, with
You/Friends/Request sent status where appropriate. Create lobby and Join with
a code are separate buttons above the list, opening dismissible dialogs over
a blurred/dimmed background. Successful creation/join opens the lobby member popup.
Cards use public usernames, existing
ranking/tie rules, and authorized profile pictures with initials as fallback.
No scores shows **No Leader**, including finished lobbies. Create and join
remain above the list. The countdown/list refresh every minute while open.

Apply [`migrations/009_single_competition_lobbies.sql`](migrations/009_single_competition_lobbies.sql)
after migration 005 for atomic database enforcement of one competition per
lobby. Existing multi-season history is retained; its latest competition
summarizes that lobby. No season renewal control remains. A failed initial
season setup can be retried in the incomplete lobby’s member popup.

Validation: `python -m pytest -q`; optional disposable SQL checks:
`python scripts/verify_single_competition_lobbies.py` with the isolated test
packages documented in `docs/LOBBY_MIGRATION_REVIEW.md`.
Shared database installation and deployed/restart checks remain the Data
owner's integration step after review; no migration runs on app startup.

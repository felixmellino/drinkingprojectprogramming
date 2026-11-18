# Security and photo data handling

## Access to photos

Every photo page and check-in submission requires the account login helper.
It checks the current credential version, including after an administrator password change.
The server looks up the viewer's current lobby membership before each photo
download. The photo path must match the entry and lobby being opened.
The photo view displays the username, capture time and territory label.

Storage uses the private `check-in-photos` bucket. The setup migration blocks
direct access by anonymous and authenticated Supabase clients and protects
the membership, season and drink-entry tables used for access decisions.
The app's service-role key stays on the server. Images are sent within the
authorized page, without a public storage URL.

For existing projects, `migrations/004_server_game_tables.sql` also protects
lobby invite codes, territory definitions, arenas and minigame attempts.
Public clients cannot bypass the app to read invites or change game state.
Fresh databases get the same restrictions from `schema.sql`. The account
migrations protect credentials and remembered sessions. Password recovery is currently
unavailable; historical reset-code database objects are unused by the app.

## Image handling

Check-in accepts camera JPEGs up to 10 MiB and 20 million pixels. The byte
limit and image dimensions are checked before the pixels are decoded. The
image is re-encoded with its orientation preserved and embedded metadata
removed. Photo GPS is not used for the location check (R-L01); the phone's
browser location and its reported accuracy are checked instead. Saved entries keep the
verification result and territory, and have empty exact-coordinate fields.
The photo setup migration clears exact coordinates from legacy entries too,
preserving scores and territory assignments.

Each capture has one entry ID and storage path. Retrying a submission uses
that ID and cannot insert another scored row. A failed upload records no
points. If an upload succeeds and a database save fails, retrying can finish
the same submission. An abandoned upload may leave a private unlinked file
until the retention process handles it.

## Configuration

Use HTTPS for the deployed app and the hosted Supabase endpoint. The app
rejects HTTP Supabase endpoints except on localhost. Streamlit's CORS and
XSRF protections are enabled. Usage telemetry is disabled in the project
configuration. Configure HTTPS and access to logs and backups with the
hosting provider.

Put local credentials in the ignored `.streamlit/secrets.toml`. Use the
hosting provider's secrets settings for deployment. Store service keys and
remembered-device tokens outside Git and issue descriptions.
If a secret is disclosed, revoke or rotate it at its provider, replace it
in the deployment secrets, and check access logs for misuse.
Use an encrypted secrets transfer rather than pasting keys into chats.
Coordinate replacement across the team's local apps and the deployment.
The current Supabase 2.9.1 client validates keys as JWTs. If replacing the
legacy service-role key with an `sb_secret_` key, upgrade and test the SDK
before the cutover. Follow the provider's
[key rotation procedure](https://supabase.com/docs/guides/security/rotate-leaked-api-keys)
so the exposed credential actually stops working.

## Dependency review

The security review on 17 November 2026 found advisories affecting the old
Streamlit, Pillow and pytest pins. Their replacements require Python 3.11
or newer. Run the full test suite after installing `requirements.txt` and
check the resolved packages with `pip-audit` before deployment.
The updated environment audit checked 70 installed packages and reported no
known advisories. This is a dated check; repeat it before deployment and after
dependency changes.

## Team decisions and deployment verification

R7 resolves the photo lifecycle part of D-13. The signed-in owner can delete
their image in Lobby photos. Ownership is checked on the server. The image
is removed and its reference is marked `deleted`; the entry and score stay.
Removal can be retried safely if a response is lost. Other members cannot
delete it. Copies already saved by viewers cannot be recalled.

Lobby access stops exactly 30 days after the season ends, using UTC.
Legacy season timestamps without a timezone are interpreted as UTC for this
cutoff. Cleanup removes expired objects and marks their reference `expired`.
Abandoned uploads without an entry have a 24-hour retry grace period since
their last update, then become eligible for removal. No scores are changed.

Run `python -m data.cleanup_checkin_photos` first to count eligible files.
Run `python -m data.cleanup_checkin_photos --apply` to remove them. The Data
owner must configure a server scheduler, at least daily, and monitor failures.
The command uses the same server secrets as the app. It reports counts only.
Run it from the repository root with the project's Python environment.
Expiry denies access immediately; physical removal occurs on the next
successful cleanup run. This repository does not provision a hosted scheduler.
Confirm the removal timing and any backup retention before collecting real
photos; do not promise immediate erasure of backups.

Before collecting real player photos, publish a privacy notice explaining
the purpose of the data, who runs the app, the lobby audience, retention,
the hosting providers and how to request access, correction or deletion.
Record the applicable basis for processing and the team's contact for
privacy requests. Confirm the project region and backup handling with the
Data owner.

Assign a team member to handle privacy and security reports. Verify the
requester's identity privately before exporting or deleting their records;
never post records or credentials in issues or the group chat. Requests from
former lobby members need that contact route. The team must define retention
for accounts and scored entries separately from the photo policy. For an
incident, restrict access, rotate affected secrets, preserve relevant logs
with limited access, establish which records were exposed, and assess any
notification duties using the team's applicable policy. Avoid logging photo
contents, exact GPS, passwords or access tokens.

Local verification on 17 November 2026: `python -m pytest -q` passed 155
tests, including photo deletion through the Streamlit page and retry after
partial failure. Temporary PGlite PostgreSQL checks exercised fresh and
upgraded schemas, repeat migration runs, preserved scores, GPS removal,
server access and public-client denial. The source scan found no matches
for common private-key, GitHub-token or Supabase-secret patterns. These
checks do not replace the configured project's live verification below.

Read-only connection checks on 17 November 2026 reached the shared project
and confirmed the core tables and account email column. The drink-entry
`photo_captured_at` column was missing (PostgreSQL code 42703), and the
`check-in-photos` bucket could not be retrieved. No shared records or schema
were changed. The Data owner still needs to apply the reviewed photo setup
and game-table security migrations. A successful service-role request alone
does not verify public-client restrictions.

The live check should include a successful upload and reopen after an app
restart, an outsider being denied, removal of a viewer's membership, and
direct object access through an anonymous Supabase client being denied.
Also verify owner deletion leaves scores unchanged, another member cannot
delete the image, expiry blocks downloads at the boundary, and two cleanup
runs remove expired and abandoned files safely without removing active ones.

The upload controls follow the [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
The retention and notice work supports the [European Commission's data protection principles](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en).

## Profile pictures

`migrations/008_profile_pictures.sql` adds a separate server-only reference
table and private `profile-pictures` bucket. It does not alter Player or game
records. Apply it to new projects too, after account setup. The migration
refuses an existing public bucket and blocks anonymous/authenticated direct
object access. The app checks the viewer's credential version and current
accepted/pending relationship before retrieving another player's image.
Profile pictures are served as authorized inline bytes, without public or
signed object URLs. They are not cached across app requests. A cancelled,
declined or removed relationship loses access on its next request, although
already-displayed/downloaded copies remain outside our control.

Images are limited to 10 MiB/20 megapixels, decoded only as JPEG, PNG or WebP,
rotated using orientation metadata, centre-cropped to 512 by 512 and saved as
new JPEG pixels without metadata. Still pictures only; transparency is placed
on white. The owner alone may replace/remove their picture. Profile editing
and picture editing are separate saves; no new game points are generated.

A successfully replaced image is deleted where possible. Uncertain saves or
failed old-object deletion can leave private unlinked files. Configure daily
`python -m data.cleanup_profile_pictures --apply` alongside check-in cleanup;
without `--apply` it only reports. It keeps every current referenced picture
and gives abandoned uploads 24 hours before removal. Saved current pictures
remain until replaced/removed. Provider backups follow the team's separately
confirmed backup policy. Include this purpose, friend/request audience and
retention in the privacy notice before collecting real photos.

Live verification still required after the Data owner applies migration 008:
upload from a library and a phone camera; restart Streamlit and reopen on
another device; replace/remove; check owner, accepted friend, both directions
of a pending request and unrelated accounts; cancel/decline/remove and verify
further access ends. Confirm public-client table/object requests fail. Run
cleanup in dry-run mode and verify it never selects a current picture.

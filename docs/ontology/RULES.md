# Rules

This file will hold every decided game rule with an ID and its allowed, rejected and boundary cases.

## Scoring v1 working implementation

The contributor authorised implementation on 17 November 2026. The current
contract is [SCORING_V1.md](SCORING_V1.md); [the handoff](../SCORING_IMPLEMENTATION.md)
records the explicit boundary defaults and verification. It is implemented
on `Scoring`, awaiting teammate review and shared migration. Existing seasons
remain legacy; the new rules apply to new v1 seasons. The earlier
[planning proposal](SCORING_PROPOSAL.md) and three-page PDF are historical
review records, not a claim of current deployment.

## Ranking

### R-R01 Ties
When two Players have the same Points, the Player who reached that score first ranks higher.

Source: team decision, 2026-11-17.

## Season

### R-R02 Season length
A lobby's season length is chosen when the lobby is created, from exactly
three options: one week, one month, or three months.

Source: team decision, 2026-11-17.

## Territories

### R-T01 Territory set
The game starts with 12 hand-drawn Territories in Lisbon: 8 in Bairro Alto,
Santa Catarina, and 3 in Santos. Their outlines live in one shared file,
`data/territories.geojson`, as GeoJSON Polygons with a display `name`
(for example "Shortys") and a short, permanent `id` (for example
`shortys`: lowercase letters and digits, words joined by hyphens). The
file is drawn and edited in geojson.io. Every
lobby plays on the same Territories; each lobby's Seasons have their own
Owners.

The file is the only source of truth. The app reads it for the location
check and the standings, and copies it into the database's `territories`
table when the app starts, because saved drinks refer to a Territory by its
`id`. After editing the file, restart the app.

| Case | Outcome |
| --- | --- |
| Allowed | Adding, removing, renaming or reshaping a Territory by editing the file, as long as R-T02 still holds. A renamed or reshaped Territory keeps its `id`; only the `name` changes. A new Territory gets a new, unused `id`. |
| Rejected | A Territory without a `name`, with a missing or badly formed `id` (capitals, spaces, underscores), or with an outline that is not a closed Polygon; two Territories with the same `id` or `name`. The app refuses to load such a file. |
| Boundary | Changing an outline mid-Season does not move drinks that were already saved; their stored Territory stays. A Territory removed from the file stays in the database so older drinks still point at it, but it is no longer matched or shown in the standings. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-03.

### R-T02 Territories never overlap
Neighbouring Territories may share a border but must never overlap, so a
location lies inside at most one Territory. Gaps between Territories are
allowed. A drink in a gap counts as outside every Territory (see R1).

| Case | Outcome |
| --- | --- |
| Allowed | Two Territories sharing an edge; empty space between Territories. |
| Rejected | Any area that lies inside two Territories. |
| Boundary | A location near or on a shared border belongs to the Territory that contains the measured point (R-L03). |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-03.

## Location

### R-L01 Location source
The app follows the phone's GPS automatically while the Check-in or Map
page is open; there is no button. The browser asks for permission once. A
check-in uses the newest reading at the moment the player submits. GPS data
stored in the photo is not used. Readings stay in the open session only and
are never saved; only the check-in's result and territory are stored.

| Case | Outcome |
| --- | --- |
| Allowed | The newest automatic phone reading (R-L02, R-L04 apply). |
| Rejected | No phone reading (permission denied, no signal, unsupported browser) or a malformed one: Submit stays disabled, nothing is saved, and the page explains what to do (R2). Typed-in coordinates are not accepted. |
| Boundary | A photo with GPS data that points somewhere else does not change the result. With the app closed or the phone locked, tracking pauses; the next reading arrives when the page is open again. |

Source: Location & Territories block (Felix), 2026-11-17, updated 2026-11-18 (automatic tracking). Resolves D-09.

### R-L02 Accuracy limit
The phone reports how many metres its reading may be off. A reading off by
at most 50 m is accepted. A worse reading counts as uncertain: the
check-in is not saved and the player retries (R2).

| Case | Outcome |
| --- | --- |
| Allowed | Accuracy of 50 m or better. |
| Rejected | Accuracy worse than 50 m. |
| Boundary | Exactly 50 m is accepted. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-10 (uncertainty).

### R-L03 Borders
An accepted reading belongs to the Territory that contains the measured
point, even if its accuracy circle reaches into a neighbouring Territory.
A point in a gap or outside every Territory counts as outside (R1).

| Case | Outcome |
| --- | --- |
| Allowed | A point inside a Territory, however close to its border. |
| Boundary | A point exactly on a shared border is assigned to one of the two Territories; which one is not defined. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-10 (edge handling).

### R-L04 Fresh readings only
A reading may be at most 60 seconds old when it is used. The app refreshes
the reading at least every 30 seconds while the page is open, and whenever
the player moves more than 20 m.

| Case | Outcome |
| --- | --- |
| Allowed | A reading up to and including 60 s old. |
| Rejected | A reading older than 60 s: Submit stays disabled until a fresh one arrives. A reading time more than 60 s in the future (wrong phone clock or tampering) is invalid. |
| Boundary | Exactly 60 s old is accepted. |

Source: Location & Territories block (Felix), 2026-11-18. Resolves D-10 (age).

## Direction agreed on 17 November 2026

The user's updated direction replaces buddy confirmation. Exact values and
boundary behavior listed in `OPEN_DECISIONS.md` are not yet agreed.

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| R1 | A city is divided into territories. An accepted check-in with a matched territory contributes its points there. | Assign a territory only when location verification identifies one. A verified location outside every territory can earn season points only, subject to the same eligibility rules. |
| R2 | Check-in requires a drink type, a size, a fresh photo taken in the app, and automatic location verification. | If location is missing or uncertain, keep the photo and drink selection on the form so the player can retry. Save the entry and award points only after verification. Only the phone's GPS reading counts (R-L01, R-L02). Discard raw coordinates after verification. |
| R3 | New v1 seasons use the frozen category/size table in [SCORING_V1.md](SCORING_V1.md). | Four categories; sizes for beer/wine/mixed; one shot serving. Reject unsupported combinations. Large bonuses are already included. Legacy seasons keep their prior awards. |
| R4 | The player with the most points in a territory owns it. | A unique leader owns the territory. Ties follow R-R01. Initial ownership, scoring window and resets remain open. |
| R5 | In v1, the previous territory owner earns an additional 25% of another player's base award in season points only. | The visitor keeps full base points. No self-income, territory income or income cap. Use exact quarters; replay affected ownership/income after a timely correction. See [SCORING_V1.md](SCORING_V1.md). |
| R6 | All current members of a lobby can view the photos saved with that lobby's drink entries. | Before serving a photo, verify that the viewer is signed in and is a current member of the lobby that owns the entry. |
| R7 | The owner can delete their photo while keeping the drink entry and its awarded points. Photos expire 30 days after their season ends. | Only the entry's author may request deletion. Remove the stored image and mark its reference as deleted, preserving the score and standings. Deny photo access at the expiry boundary and remove expired files through scheduled cleanup. |

## Implementation recommendations (not yet agreed rules)

- Capture the current device location when the player submits (R-L01).
- Validate location, configured drink/size, eligibility and score on the server.
  Determine territory from the location; do not trust a client-selected territory.
- Keep an accepted check-in's drink/size, base points, applied modifier,
  awarded points and rule version so its score can be explained later.
- Prevent retries or concurrent submissions from awarding points twice.
- Evaluate the modifier using ownership immediately before accepting the
  check-in; save points and recompute ownership atomically. This avoids a
  check-in changing the modifier used to score itself. Team agreement needed.

Location evidence can support a location check; it does not automatically
verify that the selected drink type/size is accurate or that it was consumed.

## Accounts (agreed 17 November 2026)

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| A1 | Game pages require authentication; first visit offers registration and login. | A returning player logs in without recreating an account. Logged-out access stops before any game content or actions. |
| A2 | Registration requires first name, surname, username, email and a personally chosen password entered twice. | Reject empty names, malformed email, mismatched passwords and passwords shorter than 8 characters. Eight characters are accepted; implementation also rejects whitespace-only passwords and bounds input length. |
| A3 | Username and email must each be unique, ignoring case and surrounding whitespace. | Duplicate submissions cannot create another account, including concurrent submissions. Only username is public; name and email stay private. |
| A4 | Login uses email and password, without registration email verification. Password recovery is currently unavailable (removed 17 November 2026). | Incorrect credentials leave credentials and game points unchanged. No reset-code request or password-reset form is offered. |
| A5 | Existing game progress is preserved. | Keep player IDs and all linked game records. No account-upgrade screen is shown; legacy records without an email require administrator migration to use email login. |
| A6 | Profile offers one Create account / Log in selector. | Only the selected account form is shown. No upgrade or password-recovery controls. |
| A7 | Login has an optional Remember password checkbox. | Checked: remember this device for 30 days using an opaque token, without storing the password. Unchecked: no persistent login. Logout revokes this device; password changes invalidate remembered access. Expired/invalid tokens do not authenticate. |

Login throttling (ten attempts per account per 15 minutes) is a security
implementation setting, not a scoring rule. SMTP is not required.

## Friends (agreed 17 November 2026)

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| F1 | Signed-in players search all app usernames, independent of lobbies. | Search is partial, ignores case and surrounding whitespace, and returns at most 20 results sorted by username. Empty search returns none. Search excludes yourself and exposes only username, never name, email or credentials. No profile pictures or new profile fields. |
| F2 | Friendship requires an explicit request and acceptance by the recipient. | Only the recipient may accept or decline a pending request; only the sender may cancel it. Reject self-requests, duplicate requests, requests between existing friends, and responses to non-pending requests. An opposite-direction request does not automatically accept. |
| F3 | Declining a request starts a 10-minute waiting period. | Neither player can create a new request for that pair before 10 minutes have elapsed; exactly 10 minutes is allowed. This pair-wide interpretation prevents reversing a request to bypass the wait. Cancellation does not start a waiting period. |
| F4 | Accepted friends appear in both players' private lists. | Each player can see only their own relationships. Either friend may remove the friendship, removing it from both lists. Removal allows a new request, which again needs acceptance. No friendship changes points, lobby membership or photo access. |
| F5 | Requests are managed on Profile and stored across sessions. | Incoming requests offer Accept/Decline, outgoing requests offer Cancel, and accepted friends offer Remove. Refresh friends reloads changes made by other players; no email notifications. Concurrent actions cannot overwrite an unseen change. |

Implementation: `core/friends.py` holds validation and search rules;
`friends_ui.py` renders controls using the authenticated session's player ID;
`data/db.py` stores state through a version-checked database function. The
server service key is the only database role with friendship access.

### Profile edits (agreed 18 November 2026)

- A8: A signed-in player can change their own username, first name and surname.
  Registration name limits and case-insensitive username uniqueness still
  apply. Email is read-only. Player ID and all linked game progress/friends
  remain unchanged. An expired credential version cannot save an edit.
- A9: Password changes require the correct current password and a matching
  new password following A2. The new password must differ from the current
  one. Current-password attempts share the login throttle. Successful changes
  invalidate active and remembered sessions; the player logs in again.

### Profile pictures (agreed 18 November 2026)

- A10: A signed-in player may take a camera photo or upload a JPEG, PNG or
  WebP from their library in Edit profile. Show a circular centre-cropped
  preview; save only after Save picture. Saved pictures persist across visits
  and devices. The player can replace or remove their own picture. Without a
  saved picture, use username initials. Neither pictures nor changes affect
  points, memberships or account identity.
- A11: Show the picture left of the username in Profile, and beside that
  player in friend lists and incoming/outgoing requests. Only the owner,
  accepted friends and both participants of a pending request can retrieve
  it. Declining, cancelling or removing the relationship ends further access.
  Search results for unrelated players show initials. No lobby-wide avatar
  visibility is introduced. Previously downloaded copies cannot be recalled.
- A12: Profile pictures use private server-only storage. Accept at most
  10 MiB and 20 million pixels; reject unreadable/animated images. Preserve
  orientation, centre-crop to a 512-pixel square, flatten transparency to white
  and re-encode JPEG without embedded metadata. Current images remain until
  replaced or removed. Failed writes can leave inaccessible uploads; remove
  unlinked uploads after a 24-hour grace period through server maintenance.

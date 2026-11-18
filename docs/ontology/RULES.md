# Rules

## QA season exception (18 November 2026)

For explicitly selected **test seasons only**, posting opens Wednesday at
08:00 inclusive and closes Sunday at 18:00 exclusive in the season's lobby
timezone. Create lobby / Retry lobby setup opt in with an unchecked checkbox;
the choice is stored as `scoring_rules.test_mode=true` with start weekday 2
and hour 8. Normal seasons retain Thursday 18:00–Sunday 18:00. All other rules
and server validation still apply, including GPS, photos, cooldown, points
and corrections. The snapshot stays frozen; existing seasons are not changed.
This exception does not change minigame night boundaries.

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

### R-R03 One competition per lobby
A lobby runs for its chosen 7/30/91-day duration exactly once. At its
competition's end timestamp it becomes a past lobby automatically and cannot
start another season. Start a new lobby for another competition. Keep the
existing Season entity/IDs for scoring and history; retain older multi-season
records unchanged, using their latest competition for the overview.

Allowed: create/join a lobby and start its first competition, or retry setup
when no season was saved. Rejected: adding a second competition even after
expiry. Boundary: `now == ends_at` is past; existing check-in cutoff applies.
The database serializes season inserts per lobby to reject concurrent renewals.

Source: contributor decision, 2026-11-18; supersedes same-lobby renewal in the
earlier scoring contract. Photo access and ranking rules are unchanged.

## Territories

### R-T01 Territory set
The game has 24 Territories. In Lisbon, 12 are hand-drawn (8 small ones in
Bairro Alto, Santa Catarina and 3 in Santos) and 11 larger ones fill the rest
of central Lisbon (from Santos and Madragoa to Chiado, from Príncipe Real down
to the river), so neighbouring areas border each other without gaps. In
Carcavelos, one area covers the Nova SBE campus and the beach next to it. Busy streets
get small areas, quieter neighbourhoods bigger ones. Their outlines live in one shared file,
`data/territories.geojson`, as GeoJSON Polygons with a display `name`
(for example "Shortys") and a short, permanent `id` (for example
`shortys`: lowercase letters and digits, words joined by hyphens). The
file is drawn and edited in geojson.io. Every
lobby plays on the same Territories; each lobby's Seasons have their own
Owners.

The file is the only source of truth. The app reads it for the location
check and the standings, and copies it into the database's `territories`
table when the app starts, because saved drinks refer to a Territory by its
`id`. When the file changes (e.g. after a merge), the app notices on the next
page load and copies the new version; no restart is needed.

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
Right after login the app asks the phone for its location once per login
session, so the browser shows its "Allow location?" prompt straight away.
Whether the browser asks again on later visits is the browser's setting
(e.g. Safari: website settings → Location → Allow). The
Check-in and Map pages then keep following the GPS automatically; there is
no button. A
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
| A4 | Login uses email and password, without registration email verification. Password recovery is available through the registered email (authorised 18 November 2026). | Incorrect credentials leave credentials and game points unchanged. The login screen offers Forgot password and a code-based reset form. |
| A5 | Existing game progress is preserved. | Keep player IDs and all linked game records. No account-upgrade screen is shown; legacy records without an email require administrator migration to use email login. |
| A6 | Profile offers one Create account / Log in selector. | Only the selected account form is shown. No upgrade controls; Log in offers Forgot password. |
| A7 | Login has an optional Remember password checkbox. | Checked: remember this device for 30 days using an opaque token, without storing the password. Unchecked: no persistent login. Logout revokes this device; password changes invalidate remembered access. Expired/invalid tokens do not authenticate. |

Login throttling (ten attempts per account per 15 minutes) is a security
implementation setting, not a scoring rule. Recovery requests and reset attempts
share this throttle. Brevo's HTTPS API sends recovery emails; SMTP is not required.

- A11 (authorised 18 November 2026): Forgot password sends a random 16-character
  hexadecimal code, grouped with hyphens for readability, to the registered email.
  The database stores only a hash bound to the current password hash. Codes expire
  at 15 minutes (the exact expiry is rejected) and can be consumed once, atomically
  with the password update. A new request replaces the prior code, with at least
  one minute between requests. Changing the password invalidates outstanding codes
  on their next credential lookup. Invalid input, missing/expired/used codes and
  throttled resets leave passwords and points unchanged. The new password follows
  A2 and must differ from the old one. Reset does not automatically sign in;
  existing active and remembered sign-ins fail their next credential check.
  Requests give the same public message for unknown accounts, throttling and email
  delivery failures. Delivery failures remove only their own pending code.
  Names, game records, player ID and email remain unchanged.

## Friends (agreed 17 November 2026)

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| F1 | Signed-in players search all app usernames, independent of lobbies. | Search is partial, ignores case and surrounding whitespace, and returns at most 20 results sorted by username. Empty search returns none. Search excludes yourself and exposes only username, never name, email or credentials. No profile pictures or new profile fields. |
| F2 | Friendship requires an explicit request and acceptance by the recipient. | Only the recipient may accept or decline a pending request; only the sender may cancel it. Reject self-requests, duplicate requests, requests between existing friends, and responses to non-pending requests. An opposite-direction request does not automatically accept. |
| F3 | Declining a request starts a 10-minute waiting period. | Neither player can create a new request for that pair before 10 minutes have elapsed; exactly 10 minutes is allowed. This pair-wide interpretation prevents reversing a request to bypass the wait. Cancellation does not start a waiting period. |
| F4 | Accepted friends appear in both players' private lists. | Each player can see only their own relationships. Either friend may remove the friendship, removing it from both lists. Removal allows a new request, which again needs acceptance. No friendship changes points, lobby membership or photo access. |
| F5 | Requests are managed on Profile or beside lobby members and stored across sessions. | Incoming requests offer Accept/Decline, outgoing requests offer Cancel, and accepted friends offer Remove. Refresh friends reloads changes made by other players; lobby member controls reload with Refresh lobbies and the 60-second lobby refresh. No email notifications. Concurrent actions cannot overwrite an unseen change. |

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

### Lobby member controls (agreed 18 November 2026)

- Joined lobby cards display their invite code alongside the name, leader and
  timing. Only joined lobbies are shown.
- Clicking a lobby card opens a popup over the blurred/dimmed overview showing
  its name, invite code and, in individual mode, all current member usernames, including players
  with no points. This works for active, past, upcoming and incomplete lobbies.
  There is no top-three preview. View leaderboard below the members closes
  the popup and opens the full Leaderboard for that lobby. Close, ×, outside
  click and Escape dismiss it. Long lists scroll; no scoring rules change.
- Create lobby and Join with a code are separate top-of-overview buttons.
  Forms open in dismissible modals over a blurred/dimmed background. Cancel,
  ×, outside click and Escape do not save. Successful creation/join opens
  that lobby's member or team popup with a notice. Existing options and validation stay.
- Each member row shows only the viewer's relationship: You, Friends, Request
  sent, Incoming friend request with Accept/Decline, or Add friend. F2–F5
  still apply, including the decline waiting period and concurrent-write checks.
  No new friendship rules, account fields or lobby-wide picture access.
- Membership is rechecked before showing members. Service failures show an
  error; unavailable friendship state disables actions without hiding usernames.

## Team lobbies (R-TEAM01–R-TEAM05, authorised 18 November 2026)

### R-TEAM01 Competition mode and settings
The creator chooses Individual (default) or Team. Individual lobbies keep
existing rules. Team setup chooses 2–16 teams, 1–20 players per team, and
Random or Players choose. These are fixed settings, not editable after creation.
The capacity is a maximum, not a required roster: play starts immediately,
late arrivals are allowed until the lobby ends, and uneven rosters can occur.
Equal capacities do not guarantee equal participation. There is no normalization
of points by team size. Existing lobbies stay individual.

### R-TEAM02 Joining teams
Teams are created together with the lobby, initially named Team 1, Team 2,
etc. Players choose a team with space in manual mode. A player may switch
before their first accepted scoring entry; after that, assignment is locked.
A member without a team cannot score. Random mode assigns each arriving
member to a randomly selected smallest team with space; no manual switching
or reshuffling. Lobby capacity includes members who have not chosen a team.
Repeated lobby joins retain the same membership and assignment.

Rejected: full lobby/team, another lobby's team, changes after scoring,
manual changes in random mode, joining/switching at or after the finish.
Concurrent joins serialize on the lobby lock, so the final slot admits only
one member. Rejection changes neither membership nor score.

### R-TEAM03 Names and pictures
Only current members of a team can click its name to edit its name and picture.
Names are trimmed, 1–40 characters, without control characters, and unique
within the lobby ignoring case. Members may upload or take a picture, replace
it or remove it. JPEG/PNG/WebP, 10 MB and 20 megapixels maximum; existing
profile photo processing crops to 512×512 JPEG and strips metadata. Encoded
output is limited to 512 KiB. No picture uses initials as the avatar.
Names/pictures can be edited after play and do not change identity or points.
Team pictures are visible only within their lobby. Member profile pictures
retain A11 privacy; other members see initials when access is unavailable.

### R-TEAM04 Combined competition and territory ownership
Every accepted entry snapshots the member's team. The leaderboard ranks teams,
not individual contributions. A team's territory account sums all members'
base points in that territory; the highest total owns it. Ties keep the team
that reached the total first, using the existing database acceptance order.
Season totals combine the members' base awards and the team's owner income.

The existing 25% prior-owner income goes to the owning team when a rival
team scores there. A teammate's entry never generates owner income. The
visiting team keeps all base points. Income counts only toward the season,
never territory ownership. Outside entries earn team season points only.
Corrections replay combined ownership and downstream owner income from the
original event position. Photos/minigames remain attached to their submitting
player; cooldown and minigame limits remain per player, not per team.

### R-TEAM05 Persistence and authorization
Team settings, roster, names, sanitized pictures and entry team identities
are saved in PostgreSQL through migration 010. Assignment and scoring share
the same lobby lock; accepted entry identity is immutable. Team writes and
reads require the authenticated app's existing member checks; anonymous and
Supabase authenticated roles have no access to the team table or write RPCs.
Source: contributor's explicit team-mode choices, 18 November 2026.

## Profile statistics

### R-P01 Lifetime statistics from finished lobbies

Profile → My stats shows four cards: Total points, Drinks, Lobbies played,
and Total Wins. Include only retained lobbies whose competitions have all
ended (`now >= ends_at`); do not depend on the selected lobby. In older
multi-season lobbies, include every season once the whole lobby has ended.

Points sum the player's own accepted drink awards across those seasons, plus
personal territory-owner income in individual seasons. Replay each season
separately so corrections and owner income agree with standings. Team scores,
teammates' drinks and team owner income are excluded from personal points.
Drinks counts accepted positive-point check-ins, including verified outside
locations and entries whose photo has since expired or been deleted.
Lobbies played counts distinct finished lobbies with at least one such drink.
Total Wins counts seasons won individually or by the player's team, using
existing leaderboard tie-breaking. Empty seasons have no winner.

Allowed: five finished lobbies with 11 personal points each show 55 points.
Rejected: counting an active lobby, a teammate's drink as one's own, or
counting a duplicate entry twice. Boundary: a lobby counts at its end
instant; no history shows zero on all four cards. A history-load failure
shows an error rather than a partial total. No scores or entities are changed.

Source: contributor request and clarified answers, 18 November 2026.

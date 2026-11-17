# Rules

This file will hold every decided game rule with an ID and its allowed, rejected and boundary cases.

## Ranking

### R-R01 Ties
When two Players have the same Points, the Player who reached that score first ranks higher.

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
| Boundary | A location exactly on a shared border is still open under D-10 (territory edge handling). |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-03.

## Direction agreed on 17 November 2026

The user's updated direction replaces buddy confirmation. Exact values and
boundary behavior listed in `OPEN_DECISIONS.md` are not yet agreed.

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| R1 | A city is divided into territories. An accepted check-in with a matched territory contributes its points there. | Assign a territory only when location verification identifies one. A verified location outside every territory can earn season points only, subject to the same eligibility rules. |
| R2 | Check-in requires a drink type, a size, a fresh photo taken in the app, and automatic location verification. | If location is missing or uncertain, keep the photo and drink selection on the form so the player can retry. Save the entry and award points only after verification. Use photo metadata as supporting evidence and discard raw coordinates after verification. |
| R3 | Base points depend on both drink type and size; beer earns fewer points than a longdrink in the intended comparison. | Accept only configured type/size combinations. Reject unsupported combinations. Exact table, units and comparisons between different sizes remain open. |
| R4 | The player with the most points in a territory owns it. | A unique leader owns the territory. Ties follow R-R01. Initial ownership, scoring window and resets remain open. |
| R5 | Other players earn a percentage fewer points on a drink in an owned territory than its owner. | **Proposal only, not agreed:** whether the Owner takes a share of other Players' Points or weakens their Points is still open (D-01). If agreed: apply the reduction to non-owners; percentage, rounding, unclaimed territory behavior and ownership timing remain open. |
| R6 | All current members of a lobby can view the photos saved with that lobby's drink entries. | Before serving a photo, verify that the viewer is signed in and is a current member of the lobby that owns the entry. |
| R7 | The owner can delete their photo while keeping the drink entry and its awarded points. Photos expire 30 days after their season ends. | Only the entry's author may request deletion. Remove the stored image and mark its reference as deleted, preserving the score and standings. Deny photo access at the expiry boundary and remove expired files through scheduled cleanup. |

## Implementation recommendations (not yet agreed rules)

- Capture current device location alongside a newly captured photo. Inspect
  embedded photo coordinates when available as supplementary evidence.
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

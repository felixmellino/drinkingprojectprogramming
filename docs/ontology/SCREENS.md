# Screens

> Scoring v1 implementation was authorised on 17 November 2026. See
> [the current contract](SCORING_V1.md) and [Data handoff](../SCORING_IMPLEMENTATION.md).
> Earlier scoring drafts below are historical where they differ. Legacy seasons
> retain their old behaviour; migration and teammate review are pending.


Interface structure proposal. Colors, typography, icons, dimensions and
other detailed design choices remain undecided. Gameplay rules belong in
`RULES.md`; step-by-step journeys belong in `WORKFLOWS.md`.

## Drink Entries interface (implemented 17 November 2026)

The Drink Entries block has a mobile layout on Check-in and Lobby photos.
`drink_entry_ui.py` supplies escaped headings/context and decorative inline
SVGs; `assets/drink_entries.css` styles only pages carrying that header.
Native Streamlit controls retain their accessible labels and keyboard input.
These presentation choices introduce no new scoring or database rules.

- Check-in starts with the camera. Drink/size controls appear only after a
  fresh photo is present, followed by the location status and submission.
  Drink/size choices have large selectable areas and an immediate points
  preview. Closed-window/cooldown messages appear before the form, and Submit
  spans the available width. Camera permission remains controlled by the browser.
- The Location card uses the Location block's Use my location browser button
  after the photo and drink selection. Manual coordinate inputs are removed.
  The phone supplies coordinates and accuracy; missing permission/signal and
  readings worse than 50 m keep the form open without saving (R-L01–R-L03).
  Photo GPS is not used. Exactly 50 m is accepted. Final checks still run on
  submission; the territory preview does not reserve eligibility or ownership.
- Photo history opens a newest-first gallery of the lobby's retained entries,
  four per page, with username, territory, image, drink/size, base season and
  territory awards, applicable owner income and photo-receipt/submission time.
  Native Older/Newer controls make every retained entry reachable while limiting
  image downloads. Each image download rechecks membership. Missing/removed
  images retain their entry details and score.
- View details opens that specific entry's full breakdown, exact timestamps,
  correction audit and permitted actions. A single-entry history opens its
  detail directly. All photos returns to the gallery. Exact timestamps remain
  available in expanders. The owner's separate Manage your photo expander
  keeps explicit permanent-deletion confirmation; removal preserves scores.
- Images remain inline authorized bytes, with no public media URLs. Raw GPS
  retention, image metadata stripping and lobby access follow R6/R7 unchanged.

The shared navigation and Standings refresh below were explicitly requested
as follow-ups. Account/lobby behavior and the map remain separate blocks. The
broader screen proposal below remains a future design outline.

## Standings interface (implemented 17 November 2026)

- Personal summary: current rank, exact season total and territories owned.
  Unranked members have no invented position. An unavailable territory service
  shows an unknown count, rather than zero.
- Season leaderboard: numbered top-three badges, username initials, a YOU
  marker and highlighted current-player row. Exact quarter-points remain
  visible. Rows preserve the order from `core.leaderboard.season_leaderboard`;
  the UI never re-sorts or changes the tie rule.
- Territory cards show each owner, explicit unclaimed states, every recorded
  player total and relative bars based only on base territory points. Cards
  stack on narrow screens. These bars do not represent a capture threshold.
- Refresh standings reloads the current season. Service failures show a retry
  message, without writing entries or replacing unavailable scores with zero.
- `standings_ui.py` escapes public usernames and territory names. It reuses
  the page header and adds `assets/standings.css`; core rules, database APIs,
  membership checks and season scope are unchanged.

Integration note, 18 November 2026: the UI/GPS overlap from the Scoring PR is
resolved by combining the camera-first cards with `phone_location.py`. Both
sets of UI tests remain, including permission retry without losing the photo
or drink selection, the 50 m boundary, missing/inaccurate readings, gallery
access and saved-result recovery. Live camera/location permission testing on
a phone still needs the configured app; mocked tests do not grant permissions.

## Bottom navigation (requested 17 November 2026)

- Authenticated pages use **Profile | Lobby | + Check in | Leaderboard | Photo history**.
- The large central plus opens the camera-first Check-in. Leaderboard and
  Photo history sit to its right. These are the English player-facing names.
- Native Streamlit page switching preserves the signed-in session and normal
  server-side access checks. The bar remains visible when a lobby still needs
  to be selected; it is absent before login. The former sidebar navigation is
  hidden on signed-in pages, and content leaves space above the fixed bar.
- `app_navigation.py` renders the shared bar after `require_login` verifies
  identity. `assets/navigation.css` controls its five-slot layout and safe-area
  spacing. It makes no changes to account fields, lobby rules or scoring.

## Broader structure proposal

- Shared header: current lobby and Season, with access to lobby switching
  and the invite code.
- First opening: Profile creation. Returning players with a completed
  profile and lobby start in Standings.

## First opening: Profile creation

- Required fields: real first name, real surname, unique username, unique
  login email, password of at least 8 characters and password confirmation.
- Returning users log in with email and password; registration does not
  require email verification. Password recovery is currently unavailable.
- A single Create account / Log in selector shows one form at a time.
- No password-recovery or upgrade option is shown.
- Login includes an optional Remember password checkbox, keeping the device
  signed in for 30 days. Logout cancels remembered access on that device.
- All game pages require authentication. Account rules are in `RULES.md` (A1–A7).
- A note explains that only the username is visible to other players;
  real names and other personal information remain private.
- Create profile button.
- After profile creation, a lobby-joining screen contains an invite-code
  field and a Join lobby button.

## Profile

- Username and personal Season summary: points, rank and territories owned.
- Recent check-ins with their status and points.
- Access to private profile details, profile editing, settings and sign out.
- Other players are identified by username only throughout the interface.

## Standings

- Player leaderboard with usernames, ranks and points.
- Territory standings with their owners and competing players' points.
- The player's own rank and points are easy to find.
- Recent lobby activity and an entry to minigames when available.

## Check in

- Camera action and captured-photo preview first.
- Drink type and drink size selection after capture.
- Detected territory and current owner.
- Points summary: base season/territory points and additional owner income,
  following the current scoring v1 contract.
- Submit, Back and Cancel controls.
- Submission status and resulting points or an error message.

## Map

Implemented 18 November 2026 (`pages/5_Map.py`, `map_ui.py`), for the
current lobby's season only. Bars are not part of the game, so none are shown.

- City map with the 12 territories coloured for the viewer: green = yours,
  red = someone else's, grey = unclaimed.
- Tapping a territory shows its name, what it means for you and your points
  there: "Unclaimed: your next drink here claims it", "Yours: you lead by X
  points", or "Owned by Y: you need X more points to take it" (owner's
  territory points − yours + 1, because a tie keeps the owner, R-R01).
  Owner income never counts towards territory points.
- A blue dot shows where you are (automatic location, R-L01/R-L04), with a
  line saying which territory you're in; nothing is shown if location is
  blocked, stale or worse than 50 m.
- A territory table below the map gives the same information.

## Memories

- Implemented as Photo history: retained lobby photos arranged chronologically,
  with the player, territory, drink/size, points and timestamp.
- Selecting View details opens the corresponding check-in detail. Bars are not
  part of the location or scoring model.

## Visit detail

- Photo, drink type and size, date/time and territory.
- Check-in status and a breakdown of awarded points.
- Links to the relevant territory and Standings.

## Scoring proposal: screen changes awaiting approval

See [P-S04/P-S14](SCORING_PROPOSAL.md#p-s04) for the historical discussion and [SCORING_V1.md](SCORING_V1.md) for the implemented contract. Check-in uses four category choices, Small/Medium/Large where applicable, and an automatic points preview. It shows a two-minute wait when necessary and the next opening outside the weekly window. History shows precise lobby-time timestamps, base awards, owner income and correction history. Earlier territory-reduction labels in the future Map outline above are historical; scoring v1 uses additional owner income instead.

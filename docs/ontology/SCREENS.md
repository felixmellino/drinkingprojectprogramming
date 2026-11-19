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
- Follow-up, 18 November 2026: tapping the central + mounts the camera
  into a full-viewport stage, hiding page navigation while taking the photo.
  The camera has a bottom-centre circular shutter, a front/back switch and
  Close (returns to Lobby without saving). Browser chrome/permission prompts
  remain browser-controlled; there is no separate Enable camera or gallery step.
  Taking the photo automatically opens the form: rounded photo preview,
  Retake, then drink/size controls and location. Retake discards the pending
  capture and returns to the full-screen camera. Success shows the receipt;
  New check-in or + starts the next photo. Pending photos are session-only,
  bound to player/membership/season, and are not saved until Submit. The camera stops
  after capture, when backgrounded and when leaving the page. A blocked or
  unavailable camera has a clear message and Retry control.
- Location tracking starts as soon as Check-in opens, while the player is
  taking the photo. After capture, the Location card shows the latest status
  and territory below drink/size choices. Manual coordinate inputs are removed.
  The phone supplies coordinates and accuracy; missing permission/signal and
  readings worse than 50 m keep the form open without saving (R-L01–R-L03).
  Photo GPS is not used. Exactly 50 m is accepted. Final checks still run on
  submission; the territory preview does not reserve eligibility or ownership.
- Create lobby and Retry lobby setup have an unchecked Test season option.
  A selected test season is labelled on its lobby card and Check-in page.
  Its frozen scoring window is Wednesday 08:00–Sunday 18:00 in the lobby
  timezone. Normal seasons keep Thursday 18:00–Sunday 18:00.
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
  require email verification. Log in offers **Forgot password?** (18 November 2026).
- A single Create account / Log in selector shows one form at a time.
- Forgot password shows a registered-email request form and a reset form for
  account email, emailed code, new password and confirmation. Request responses
  do not disclose whether an email is registered. Show success/error clearly and
  offer Back to log in; a reset does not automatically authenticate. Codes expire
  after 15 minutes. No upgrade option is shown.
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

- City map with the 24 territories coloured for the viewer: green = yours,
  red = someone else's, grey = unclaimed.
- Tapping a territory shows its name, what it means for you and your points
  there: "Unclaimed: your next drink here claims it", "Yours: you lead by X
  points", or "Owned by Y: you need X more points to take it" (owner's
  territory points − yours + 1, because a tie keeps the owner, R-R01).
  Owner income never counts towards territory points.
- A blue dot shows where you are (automatic location, R-L01/R-L04), with a
  line saying which territory you're in; nothing is shown if location is
  blocked, stale or worse than 50 m.
- Hovering or tapping an area tints it in the app's dark green.
- The base map shows streets, parks and water in colour (Carto Voyager).
- Three cards below the map: territories you own (e.g. "1 of 24"),
  unclaimed territories, and the easiest one to take (fewest points needed).
- Small quick-zoom buttons right above the map jump to "Bairro Alto",
  "Lisbon", "Nova SBE" or "All" (and "📍 Me" when your location is usable),
  so the map isn't mostly empty city. The map is the first big element.
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

## Profile menu (implemented 18 November 2026)

The authenticated Profile is a vertical list: **Edit profile**, **Friends**,
**My stats**, **Account & security**, then **Log out**. Each of the first
four opens a separate view with **Back to Profile**. Logout is immediate.

- Edit profile updates username, first name and surname. Names use the same
  required/100-character limits as registration. Usernames remain unique,
  ignoring case and surrounding whitespace. Player ID, email, credentials,
  friendships, memberships and scores are retained. Profile pictures are described below.
- Friends shows four fully clickable cards in two rows: **Find players** next
  to **Current Friends**, then **Incoming requests** next to **Outgoing requests**.
  On phones they stack in that order. The three lists show counts; failed
  loading shows Unavailable rather than a misleading zero. Each opens a native,
  dismissible popup. Find players focuses the username search on opening.
  Current Friends lists accepted relationships from either direction, sorted
  by username. Remove friend requires confirmation inside the same popup;
  Keep friend cancels it. Incoming requests offers Accept/Decline and Outgoing
  requests offers Cancel for pending sent requests only. Successful actions
  keep the popup open, reload its list and update the card counts, and show a
  success message. Refresh friends reloads other players' changes. Closing or
  dismissing a popup clears its open state. Existing F1–F5 rules still apply.
- My stats shows Total points, Drinks, Lobbies played and Total Wins across
  all retained active and finished lobbies, independently of lobby selection.
  Accepted scoring check-ins count immediately. Personal points include own
  drink awards and individual owner income, excluding teammates' points and
  team owner income. Wins count only completed seasons, with leaderboard
  tie-breaking. No history shows zero totals; failed loading shows an error
  rather than partial totals. R-P01 defines the calculation.
- Account & security shows private name and read-only email, then a password
  change form requiring current password, new password and confirmation.
  Existing password length rules and login throttling apply. A successful
  change signs out this device; all other active/remembered sign-ins become
  invalid on their next check. Logged-out password recovery is described above.

Authorized by the contributor's Profile choices on 18 November 2026. Account
updates use existing columns and unique indexes, so no new migration is needed.

### Profile picture interface (implemented 18 November 2026)

Profile has a circular picture left of the username, with initials as the
fallback. Edit profile keeps its name form and adds a separate Profile picture
section: Upload photo / Take photo, circular preview, then Save picture.
Camera permission is requested by the browser. JPEG/PNG/WebP library selection
and camera captures share validation and centre cropping. A saved picture
can be removed, restoring initials, or replaced. Picture actions do not submit
unsaved name fields. Friends displays pictures beside accepted friends and
incoming/outgoing requests; unrelated search results use initials.
Storage failures retain the name editor and a clear picture status. Account
pictures need `008_profile_pictures.sql`; friend data needs the existing
`006_friendships.sql`. Neither script is applied automatically on app startup.

## Lobby overview (implemented 18 November 2026)

- Show only the signed-in player's joined lobbies, with no lobby/season dropdown.
- Active Lobbies are light green, latest competition start first. Each shows
  lobby name, leader's public username, a small authorized picture (otherwise
  initials), invite code, and time until finish plus the exact lobby-time finish timestamp.
- Automatically select the newest running lobby unless a lobby is explicitly open.
  The whole card is a keyboard-accessible button labelled View lobby → opening
  a dismissible popup over the blurred/dimmed overview. This works for active,
  past, upcoming and incomplete lobbies.
- The popup shows only the lobby name, invite code and member list, with the
  existing friendship controls. It has no leaderboard preview, leader or
  countdown; those summaries remain on overview cards. Long lists scroll.
  View leaderboard sits below the members and closes the popup to open the
  full Leaderboard for that lobby. Close, ×, outside click and Escape dismiss
  it and leave the overview visible. Membership is checked on each interaction.
- Member rows show public usernames, You/Friends/Request sent status, Add friend
  for unrelated players, and Accept/Decline for incoming requests. Existing
  friendship rules apply; only your own relationships are exposed.
- Past Lobbies are light grey, latest finish first: name, winner's public
  username and finish timestamp. No scored entries reads **No Leader** in both
  lists. Service failure reads Standings unavailable, never an invented result.
- A timed fragment refreshes the list/countdown every 60 seconds while open,
  rechecks memberships and moves expired cards at the next refresh. Server
  check-ins still enforce the exact finish boundary independently of the UI.
- Create lobby / Join with a code are individual buttons above the list.
  Each opens a native modal over a subtly blurred, dimmed, non-interactive
  background. Cancel, ×, outside click and Escape dismiss without saving.
  Existing duration/timezone/test-season and invite-code controls remain.
  Invalid submissions stay in the modal with errors. Success closes it,
  opens the lobby member or team popup and displays a success message.
- Duration is fixed; no renewal or season selection is offered. Incomplete
  setup has a retry form in the member popup. A failed initial season start opens
  that popup with a notice, so retrying cannot create another lobby by mistake.
  Future legacy competitions are labelled Upcoming instead of running.
- R-R03 governs one competition per lobby. Existing multiple-season history
  is retained; only its latest competition is summarized. Picture privacy
  remains A11; lobby membership alone does not grant picture access.

## Team lobby extension (18 November 2026)

Create lobby now opens a dialog with Individual/Team selection. Team settings
react immediately and expose count, capacity and Random/Players choose.
Open lobby on a team card opens a dialog showing the numbered teams, member
identities, occupancy and combined points. Available teams have Join buttons
in manual mode. Clicking one's own team name opens its name/picture editor;
other teams have no editing controls. A View leaderboard action opens the
combined team standings. Map and leaderboard show team totals and
ownership; My stats retains personal totals and counts completed team wins
under R-P01. Check-in blocks unassigned members and previews team ownership.
The lobby card's Leader/Winner also names the leading team. Individual lobby
navigation remains as described above. R-TEAM01–R-TEAM05 govern these flows.

Lobby action placement updated 18 November 2026: both entry points are
full-width buttons in two columns directly below the page title. Forms are
shown only in their respective popups. Successful joining closes the popup
and refreshes the lobby cards; an invalid code keeps the popup open with its
error. Creation settings and team rules remain unchanged.

## Chug Duel playing view (18 November 2026)

After the shared check-in is saved, the host sees two named tap targets that
fill the app viewport. Both tap once to get ready, then the same board shows
3, 2, 1 and GO. Early finish taps are ignored. Navigation and page scrolling
stay disabled; server updates do not move or remount the board. The first
finish tap locks the result locally, which is then confirmed by the server.
The winner remains visible on this board until Back to Minigames restores
the normal page. A small × preserves End without winner. The recipient's
device continues to show the running game's status and then its result.
Rules, limits and awards remain R-M01–R-M05.

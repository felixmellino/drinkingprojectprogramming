# Error feedback and rejected-action verification

Reviewed 21 November 2026. UI contract: [Screens](ontology/SCREENS.md).
All app text is English. Tap a blocked action to get a reason and recovery
step; dismiss the popup with OK or its close control. Existing dialogs show
feedback inside the same window. Background failures remain inline so polling
does not interrupt the player repeatedly.

`action_feedback.py` provides the enabled button guard and popup. Shared
location and check-in explanations live in `core/action_feedback.py`;
game-specific server rejections remain beside their rules in `core/*duel.py`.
Team rejections in `core/teams.py` are reused for joining, rejoining and team edits,
so a full lobby is not presented as an unexplained connection failure.
Client guards improve feedback; database validation remains authoritative.
Unknown check-in rejection codes get a safe recovery message, never raw codes.

## Workflow matrix

| Workflow / rejected case | How to reproduce | Expected explanation and next step | Verification |
| --- | --- | --- | --- |
| Check-in: tracking off | Turn Location off in Profile, take a photo, press Submit | Open Profile → Location and turn it on | `test_action_feedback.py` |
| Check-in: permission denied | Deny site location, press Submit | Allow site permission and phone location services, then turn Location on | `test_action_feedback.py` |
| Check-in: no reading, stale reading | Submit before a fix, or simulate a reading older than 60 s | Wait for a fresh reading; toggle Location if updates stop | `test_scoring_ui.py` |
| Check-in: unavailable / timeout / unsupported / invalid | Simulate each browser response, press Submit | Distinct instructions: move outside, retry tracking, use a supported HTTPS browser, or reload | `test_action_feedback.py` |
| Check-in: inaccurate GPS | Simulate 80 m accuracy and submit | Current accuracy and 50 m limit; move outside and wait | `test_scoring_ui.py` |
| Check-in: outside territories | Use a valid position outside every territory | Accepted for season points only; this is not an error | Existing location/scoring tests and check-in preview |
| Check-in: cooldown or window closes after capture | Save on another session, or advance the clock after taking a photo | Wait countdown / view next opening; photo and selection survive | `test_scoring_ui.py` |
| Check-in: season closed before capture | Open outside scoring hours or after season end | Opening in lobby timezone, or choose a new lobby; camera does not open | `test_scoring_ui.py` |
| Check-in: no team or lobby/season access | Open without the required selection or team | Go to Lobby and select a valid lobby / join a team | Existing bootstrap/team tests |
| Check-in: server rejects input, photo, territory or membership | Simulate rejection at save | Specific recovery; unknown codes are hidden; form retained | `test_action_feedback.py`, existing scoring tests |
| Check-in: save reply lost | Simulate disconnect after commit | Retry the same photo to recover saved result; award only once | `test_scoring_ui.py` |
| Check-in: recent history unavailable | Fail the initial history read | Explain that cooldown cannot be checked; reload Check in | Manual failure injection / guarded read |
| Camera: denied / missing / busy / unsupported | Deny camera, remove device, occupy camera, use unsupported context | Allow camera, use a camera device, close other camera apps, or use HTTPS; Retry offered | `camera_component.cjs` |
| Camera: initializing or invalid image | Delay preview or return invalid bytes | Visible loading status or retake instruction; cannot submit unreadable photo | Camera and photo validation tests |
| All duels: no eligible player/team | Use one-player lobby or only same-team players | Invite another player; team mode needs an opposing team; own missing team explained | Duel UI tests |
| All duels: no opponent selected | Give two eligible opponents, select neither, press Challenge | Choose a player; no invitation is sent | `test_chug_duel_ui.py` |
| Quiz / Reaction: insufficient available stake | Choose more than available points and press Challenge | Required and available points; lower stake or earn points; reserved points unavailable | Duel UI tests |
| All duels: server-only limits, busy player, changed/expired invite, permissions | Simulate mapped RPC rejections | Explain affected rule and finish, cancel, refresh, choose another player or wait until 06:00 as appropriate | Existing duel RPC tests; message catalogues |
| Time / Chug: acceptance already used/reserved | Press Accept with no incoming allowance | Finish reserved game or wait for 06:00 in lobby timezone; no accept RPC | Duel UI tests |
| Time: challenge used/reserved or invite pending | Press Send Time Duel challenge | Finish/wait for reset, or cancel existing invitation first; no invite RPC | `test_time_duel_ui.py` |
| Chug: missing/inaccurate host location | Accept, capture shared photo, press Start duel | Same precise location recovery as ordinary check-in; duel does not start | `test_chug_duel_ui.py` |
| Minigame service unavailable | Fail the Chug list request, tap its tile | Refresh Minigames or contact organizer; other games remain reachable | Existing outage tests / shared guard |
| Team: full / locked / finished | Try joining another team in each state | Choose free team, continue locked team, or use new lobby; reserved departed slots explained | `test_team_ui.py` |
| Team edit: invalid/conflicting name or picture, permissions | Submit invalid edits | Name/photo requirement or own-team restriction and recovery | Team/profile-picture validation tests |
| Lobby: bad code / full / failed rejoin | Submit invalid code or simulate membership rejection | Check invite code; explain full lobby/reserved places or exact rejoin rejection | Lobby UI / team RPC tests |
| Lobby setup: existing season / timezone / rules | Reject setup with a known scoring reason | Distinct explanation rather than one generic setup error | Shared scoring-message catalogue |
| Lobby departure/deletion | Leave during a game or delete without creator access | Finish game/wait for expiry, or creator-only permission explanation | Existing leave/delete tests |
| Photos: unchanged correction | Press Save correction without a change | Choose a different drink or size; no correction is sent | `test_scoring_ui.py` |
| Photos: expired / duel / somebody else's correction | View each kind of entry | Explain two-minute/season limit, shared-duel lock or owner restriction | Existing correction rules; visible caption |
| Photos: concurrent correction / reserved points | Reject a correction at save | Refresh and review current revision, or finish duel holding reserved points | Existing correction/RPC tests |
| Photos: deletion not confirmed | Press Delete my photo without checkbox | Tick confirmation, then retry; image and points retained | `test_photo_lifecycle.py` |
| Photos: more history | Scroll through the continuous list and select Load more while more photos remain | Additional photos are appended; the control disappears once all available photos are shown | `test_scoring_ui.py` |
| Photos: private / expired / deleted / download failure | Review inaccessible or removed image | Existing privacy/retention/removed-photo state; score stays; refresh on access change | Existing photo lifecycle/privacy tests |
| Map: unusable location | Tap Location help with denied/unsupported/timeout reading | Explain actual browser failure and recovery, rather than generic waiting | `test_map_page.py` |
| Account: registration / credentials / duplicate name/email | Submit each invalid form | Field requirement, different username or existing-account login/reset route | Account/auth tests |
| Account: repeated login attempts / reset | Submit invalid credentials or reset code | Check credentials/reset route; retry after 15 minutes after repeated attempts. Reset responses preserve account privacy | Existing auth/reset tests |
| Profile / password / picture / photo privacy | Submit invalid values or fail save | Field rule or retry/check-saved-state instruction; existing privacy/password dialogs retain inline feedback | Profile/picture tests |
| Friends: pending, accepted, declined cooldown, stale or wrong-role request | Try the corresponding invalid transition | Check incoming/outgoing/current friends, refresh, or wait ten minutes | Existing friendship tests |
| Standings/map/profile loading | Fail a read | Inline reload/retry instruction; optional missing avatars keep initials | Existing page outage tests |

## Verification commands

From the repository root:

```powershell
.venv/Scripts/python.exe -m pytest -q
node tests/location_component.cjs
node tests/camera_component.cjs
.venv/Scripts/python.exe -m streamlit run tests/fixtures/feedback_browser_app.py
```

Tests use isolated service doubles and synthetic photos; they do not submit
drinks to the shared database. Streamlit AppTest needs local sockets, which
may need a sandbox exception on Windows. Real camera/OS permission dialogs
still require a phone check in Safari and Chrome. No database migration or
game-rule change is required for this UI update.

The last command opens the actual Check in page with synthetic photo/location
inputs and the shared database disabled. In the sidebar, choose off or inaccurate,
tap Submit, dismiss the explanation, then choose ready and submit the same
photo. A browser check verified both popups, retained drink selection and the
accepted retry. Screenshot: `output/previews/action-feedback-location.jpg`.

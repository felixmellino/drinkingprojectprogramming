# Instant camera and QA seasons

The central + opens Check-in and starts the camera and phone GPS together.
Browser permission is still required. `camera_capture.py` is the Streamlit
bridge to `components/drink_camera/index.html`; it replaces the native
camera widget's separate enable step without automating browser prompts.

The camera has its own full-viewport stage: a rear-camera preview, bottom-centre
circular shutter, front/back switch and close button. It uses no microphone.
Browser chrome and permission prompts remain controlled by the browser; this
is an in-app camera, not a launch of the phone's native Camera application.
Single-camera devices may return the same camera for either preference.

Taking the photo automatically leaves the camera stage and opens the form,
with a rounded photo preview, Retake, drink/size controls, location and Submit.
The JPEG matches the preview's centre crop (including front-camera mirroring),
and is at most 1600 pixels on its longest edge. Capture, switching cameras,
closing, backgrounding and navigation stop the old media stream, including
late permission responses. Retake opens a fresh full-screen camera.

Validated pending photos live only in the signed-in Streamlit session and
are bound to player, membership and season. GPS reruns retain that photo and
submission ID without remounting the camera. Retake or a context change clears
the old capture; a server restart loses an unsaved photo. Nothing is uploaded
until Submit. Success clears pending bytes and keeps the receipt visible;
New check-in or the navigation + explicitly starts another capture.

The server validates the base64 transport and capture UUID, applies the
existing byte/pixel/decode limits, strips metadata and retains a stable
capture identity across GPS reruns. Existing submission, lost-reply recovery,
cooldown and access checks remain in place. No additional package is required.

## Enable test check-ins

Create a QA lobby and check **Test season (check in any day)** before
submitting Create lobby. The checkbox defaults to off. An
incomplete setup also exposes that choice under Retry lobby setup. The
lobby card and Check-in page label test seasons visibly for all members.

Migration 032 allows ordinary check-ins throughout the configured season,
including in existing test lobbies. Check-ins still require a photo and
verified phone GPS and use the standard points table. Migration 031 uses
the same frozen test flag to remove the posting cooldown for ordinary
check-ins and Chug Duel entries.

QA seasons also allow unlimited sequential Chug Duel replays after migration
012 (R-M02). Minigames shows Unlimited for both roles, including after an
earlier win or abort. The frozen boolean test flag controls this, not the
lobby's name. Finish or end the active game before starting another. Photo,
GPS and the frozen Wednesday 08:00–Sunday 18:00 window still apply to Chug Duel.

## Verification

Run the normal Python suite with `python -m pytest -q`.
`tests/test_camera_capture.py` checks transport validation and metadata removal;
`tests/test_test_seasons.py` checks off-hours availability, season cutoffs,
the Chug Duel window and the frozen database payload. Streamlit AppTests
exercise creating both kinds of season and submitting test check-ins on Monday.
The migration-chain test exercises the same eligibility through the scoring RPC.

`node tests/camera_component.cjs` checks the actual camera JavaScript with
synthetic media objects: automatic opening, no reopen on GPS rerenders,
capture/crop/mirroring, front/back switch, close, permission denial/retry, navigation and background cancellation.
It never requests a real camera.

A synthetic browser preview can verify the interface, but real iPhone/Android
camera permission, video startup and GPS still need the deployed HTTPS app.
On a phone: open +, grant permissions, take a photo, check its preview and
location, choose drink/size and submit in a QA lobby. Check that Retake and
leaving/backgrounding the page stop the old camera stream.

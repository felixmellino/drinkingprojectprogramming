# Instant camera and QA seasons

The central + opens Check-in and starts the camera and phone GPS together.
Browser permission is still required. `camera_capture.py` is the Streamlit
bridge to `components/drink_camera/index.html`; it replaces the native
camera widget's separate enable step without automating browser prompts.

The component prefers the rear camera, uses no microphone, captures JPEG
at at most 1600 pixels on its longest edge, and displays the image in a
rounded frame. Capture stops the media stream. Retake clears the submitted
component value, releases the old capture and opens a fresh stream. Navigation,
backgrounding and late permission responses release the stream as well.

The server validates the base64 transport and capture UUID, applies the
existing byte/pixel/decode limits, strips metadata and retains a stable
capture identity across GPS reruns. Existing submission, lost-reply recovery,
cooldown and access checks remain in place. No additional package is required.

## Enable Wednesday testing

Create a **new QA lobby** and check **Test season: Wednesday 08:00–Sunday
18:00** before submitting Create lobby. The checkbox defaults to off. An
incomplete setup also exposes that choice under Retry lobby setup. The
lobby card and Check-in page label test seasons visibly for all members.

The normal points table is used; only the opening day/hour changes. The
choice is part of the existing frozen JSON rules snapshot sent to the
season-creation RPC. The existing database scoring-window function reads
that snapshot, so **no new migration is required**. Existing seasons,
normal-season defaults and minigame night rules remain unchanged. Test
points stay inside the separate QA lobby. Never change the server clock
or edit an active season's snapshot to enable testing.

## Verification

Run the normal Python suite with `python -m pytest -q`.
`tests/test_camera_capture.py` checks transport validation and metadata removal;
`tests/test_test_seasons.py` checks exact cutoffs, timezone behavior and the
frozen database payload. Streamlit AppTests exercise creating both kinds of
season and starting location before capture.

`node tests/camera_component.cjs` checks the actual camera JavaScript with
synthetic media objects: automatic opening, no reopen on GPS rerenders,
capture/retake, permission denial/retry, navigation and background cancellation.
It never requests a real camera. The optional isolated PostgreSQL suite in
`tests/scoring_postgres.cjs` also checks the server's Wednesday 08:00/Sunday
18:00 boundaries and QA-rule persistence after restart; see
`docs/SCORING_IMPLEMENTATION.md` for setup.

A synthetic browser preview can verify the interface, but real iPhone/Android
camera permission, video startup and GPS still need the deployed HTTPS app.
On a phone: open +, grant permissions, take a photo, check its preview and
location, choose drink/size and submit in a QA lobby. Check that Retake and
leaving/backgrounding the page stop the old camera stream.

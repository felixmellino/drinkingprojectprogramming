# Features

This file will hold every feature we plan to build with its priority and owner.

## Activity feed (21 November 2026)

- **Built (v1):** the Activity tab lists the season's check-ins and territory
  captures, newest first, derived from saved drink entries (`core/activity.py`,
  `activity_ui.py`, `pages/8_Activity.py`). Screen details: [SCREENS.md](SCREENS.md#activity-feed-21-november-2026).
- **Planned:** more event kinds in the same feed: achievements, duel results,
  players joining or leaving the lobby. Each one adds a new `kind` to
  `ActivityEvent`; the rendering and the Activity screen stay the same.

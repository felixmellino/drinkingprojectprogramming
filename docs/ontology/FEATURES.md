# Features

This file will hold every feature we plan to build with its priority and owner.

## Activity feed (21 November 2026)

- **Built (v1):** the Activity tab lists the season's check-ins and territory
  captures, newest first, derived from saved drink entries (`core/activity.py`,
  `activity_ui.py`, `pages/8_Activity.py`). Screen details: [SCREENS.md](SCREENS.md#activity-feed-21-november-2026).
- **Planned:** more event kinds in the same feed: achievements, duel results,
  players joining or leaving the lobby. Each one adds a new `kind` to
  `ActivityEvent`; the rendering and the Activity screen stay the same.

## Season recap and awards (21 November 2026)

- **Built:** when a season ends, each player gets a **Finish season** banner.
  It plays an animated story (season over, podium, one slide per award, your
  season) and ends on a static awards card with a CSV download of the final
  standings. Rules: [RULES.md R-S01 to R-S03](RULES.md#season-awards-21-november-2026).
  Code: `core/season_recap.py`, `season_recap_ui.py`, `pages/9_Season_recap.py`,
  `components/season_recap/`, migration 029.
- **Planned:** a shareable image of the awards card; lifetime achievements
  across seasons.

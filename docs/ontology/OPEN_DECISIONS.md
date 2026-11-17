# Open Decisions

This file will hold every question the team has not decided yet, with its options.

The current check-in rules use automatic location verification. D-14 proposes a fallback for cases where that check fails.

| ID | Topic | Open question |
| --- | --- | --- |
| D-01 | Owner advantage | Does the Owner of a Territory take a small share of the Points other Players earn there, or weaken those Players' Points on that Territory? If Points are weakened: reduction percentage, rounding, and Points in an unclaimed Territory. |
| D-02 | Points per Drink | How many Points does each category (beer, wine, shots, long drinks) give, and how does the amount count for beer and wine? Supported drinks and sizes (with units), exact base Points, and whether size uses a lookup table or a formula. |
| D-03 | Territory areas | How are the Territory areas drawn and stored on the map? |
| D-04 | Special items | Which special items do Minigames give, and what does each one do? |
| D-05 | Game Night boundaries | When does a Game Night start and end, and which night does a Drink after midnight belong to? Exact Thursday to Sunday hours, timezone and out-of-hours behavior. |
| D-06 | Season length | How long is the playing period, and when does it start and end? Initial ownership, scoring window and Season resets. |
| D-07 | Minigame interruption | If a Minigame is interrupted, does it count as the Player's one play for that evening? |
| D-08 | Ownership timing | Recommended: ownership immediately before acceptance. Define the order of concurrent check-ins. |
| D-09 | Location source | Recommended: fresh phone location alongside the photo capture. Define the role of photo metadata, missing metadata and conflicting coordinates. |
| D-10 | Location acceptance | Maximum coordinate age and uncertainty, and territory edge handling. |
| D-11 | Photo validation | How to detect reused images, supported formats and size, and how to handle false drink or size declarations. |
| D-12 | Check-in limits | Repeat drinks, cooldowns and duplicate submissions. |
| D-13 | Privacy | Photo visibility, coordinate retention, image metadata removal before sharing, and deletion behavior. |
| D-14 | Later confirmation by another player | Should R2 allow the [proposed confirmation fallback](WORKFLOWS.md#proposed-fallback-after-automatic-location-verification-fails) when automatic location verification fails? |

Design consideration: an ownership reduction can make leaders harder to
catch. Test the agreed percentage with sample standings before fixing it.

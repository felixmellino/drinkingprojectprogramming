# Open Decisions

This file will hold every question the team has not decided yet, with its options.

The current check-in rules use automatic location verification. D-14 proposes a fallback for cases where that check fails.

| ID | Topic | Open question |
| --- | --- | --- |
| D-01 | Owner advantage | Does the Owner of a Territory take a small share of the Points other Players earn there, or weaken those Players' Points on that Territory? If Points are weakened: reduction percentage, rounding, and Points in an unclaimed Territory. |
| D-02 | Points per Drink | How many Points does each category (beer, wine, shots, long drinks) give, and how does the amount count for beer and wine? Supported drinks and sizes (with units), exact base Points, and whether size uses a lookup table or a formula. |
| D-03 | Territory areas | **Decided 2026-11-17**, see [R-T01 and R-T02](RULES.md#territories). Still open: Territories around Nova SBE (Carcavelos) for demos, and possibly Praça das Flores. |
| D-04 | Special items | Which special items do Minigames give, and what does each one do? |
| D-05 | Game Night boundaries | When does a Game Night start and end, and which night does a Drink after midnight belong to? Exact Thursday to Sunday hours, timezone and out-of-hours behavior. |
| D-06 | Season length | How long is the playing period, and when does it start and end? Initial ownership, scoring window and Season resets. |
| D-07 | Minigame interruption | If a Minigame is interrupted, does it count as the Player's one play for that evening? |
| D-08 | Ownership timing | Recommended: ownership immediately before acceptance. Define the order of concurrent check-ins. |
| D-09 | Location source | **Decided 2026-11-17**, see [R-L01](RULES.md#location): phone GPS at submission only, photo GPS is not used. |
| D-10 | Location acceptance | Uncertainty and edge handling **decided 2026-11-17**, see [R-L02, R-L03](RULES.md#location). Still open: how old a phone reading may be. |
| D-11 | Photo validation | How to detect reused images, supported formats and size, and how to handle false drink or size declarations. |
| D-12 | Check-in limits | Repeat drinks, cooldowns and duplicate submissions. |
| D-13 | Privacy | Who can delete a saved photo and what happens to its drink entry afterwards? The [photo workflow](WORKFLOWS.md#save-and-view-a-check-in-photo) defines what the server keeps and what lobby members can see. |
| D-14 | Later confirmation by another player | Should R2 allow the [proposed confirmation fallback](WORKFLOWS.md#proposed-fallback-after-automatic-location-verification-fails) when automatic location verification fails? |

Design consideration: an ownership reduction can make leaders harder to
catch. Test the agreed percentage with sample standings before fixing it.

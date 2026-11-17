# Open Decisions

This file tracks team review and unresolved decisions. [SCORING_V1.md](SCORING_V1.md) records the working implementation authorised by the contributor; teammate review, merge, migration and live verification remain pending. The [planning record](SCORING_PROPOSAL.md) preserves earlier choices.

The current check-in rules use automatic location verification. D-14 proposes a fallback for cases where that check fails.

| ID | Topic | Open question |
| --- | --- | --- |
| D-01 | Owner advantage | Implemented on Scoring: additional 25% prior-owner income, season only, exact quarters, no visitor deduction/self-income/cap. Team review and migration pending. See [v1](SCORING_V1.md). |
| D-02 | Points per Drink | Implemented on Scoring: four categories and frozen fixed size table; Large bonuses embedded. Legacy seasons preserved. Team review pending. See [v1](SCORING_V1.md). |
| D-03 | Territory areas | **Decided 2026-11-17**, see [R-T01 and R-T02](RULES.md#territories). Still open: Territories around Nova SBE (Carcavelos) for demos, and possibly Praça das Flores. |
| D-04 | Special items | Which special items do Minigames give, and what does each one do? |
| D-05 | Game Night boundaries | Implemented on Scoring: continuous Thu 18:00 inclusive-Sun 18:00 exclusive in the season timezone; database scoring-request receipt is authoritative. Outside submissions blocked. Minigame nights remain separate. See [v1](SCORING_V1.md). |
| D-06 | Season length | Working defaults: retain 7/30/91-day options; a new season ID resets scores and owners without deleting history. Any member can start the next season after the last ends. Calendar-month/host-role changes remain team decisions. See [v1](SCORING_V1.md). |
| D-07 | Minigame interruption | If a Minigame is interrupted, does it count as the Player's one play for that evening? |
| D-08 | Ownership timing | Implemented on Scoring: prior owner paid before captures; serialized database event order; corrections replay affected history. Exact same-event tie default is recorded in D-17. See [v1](SCORING_V1.md). |
| D-09 | Location source | Recommended: fresh phone location alongside the photo capture. Define the role of photo metadata, missing metadata and conflicting coordinates. |
| D-10 | Location acceptance | Maximum coordinate age and uncertainty, and territory edge handling. |
| D-11 | Photo validation | Trust-based category/size selection, with lobby photo review, is selected for the proposal; exact shot volume and stronger reuse detection remain unspecified. See [P-S02/P-S04](SCORING_PROPOSAL.md#p-s04). |
| D-12 | Check-in limits | Implemented on Scoring: TWO-minute shared per-member/lobby cooldown; retain rejected form; retries award once; no fixed nightly count. See [v1](SCORING_V1.md). |
| D-13 | Privacy | **Photo lifecycle decided 2026-11-17**, see R7: owner deletion preserves the score; photos expire 30 days after the season ends. The [photo workflow](WORKFLOWS.md#save-and-view-a-check-in-photo) defines stored data and lobby access. Still needed before real use: privacy contact, published notice, provider region and backup/deletion procedures, and scheduled cleanup. |
| D-14 | Later confirmation by another player | Should R2 allow the [proposed confirmation fallback](WORKFLOWS.md#proposed-fallback-after-automatic-location-verification-fails) when automatic location verification fails? |
| D-15 | Entry corrections | Implemented on Scoring: author can correct drink/size before original submission +120s and season end. Timely edits may finish after weekly closing. Audit and downstream replay included; defaults await team review. See [v1](SCORING_V1.md). |
| D-16 | Frozen scoring rules and timezone | Implemented on Scoring: v1 season dates, lobby, rules, version and timezone immutable. New rules start in later seasons; populated legacy seasons cannot be upgraded in place. See [v1](SCORING_V1.md). |
| D-17 | Exact ties and concurrent ordering | Working default: database acceptance order resolves concurrent entries. Within one event, a season-score tie preserves the previously higher-ranked owner recipient. All other ties use earliest reaching order. Team review pending. See [v1](SCORING_V1.md). |

Design consideration: an ownership reduction can make leaders harder to
catch. Test the agreed percentage with sample standings before fixing it.

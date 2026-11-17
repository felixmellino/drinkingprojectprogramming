# Rules

This file will hold every decided game rule with an ID and its allowed, rejected and boundary cases.

## Ranking

### R-R01 Ties
When two Players have the same Points, the Player who reached that score first ranks higher.

Source: team decision, 2026-11-17.

## Direction agreed on 17 November 2026

The user's updated direction replaces buddy confirmation. Exact values and
boundary behavior listed in `OPEN_DECISIONS.md` are not yet agreed.

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| R1 | A city is divided into territories. An accepted check-in with a matched territory contributes its points there. | Assign a territory only when location verification identifies one. A verified location outside every territory can earn season points only, subject to the same eligibility rules. |
| R2 | Check-in requires a drink type, a size, a fresh photo taken in the app, and automatic location verification. | If location is missing or uncertain, keep the photo and drink selection on the form so the player can retry. Save the entry and award points only after verification. Photo metadata may support the device reading. |
| R3 | Base points depend on both drink type and size; beer earns fewer points than a longdrink in the intended comparison. | Accept only configured type/size combinations. Reject unsupported combinations. Exact table, units and comparisons between different sizes remain open. |
| R4 | The player with the most points in a territory owns it. | A unique leader owns the territory. Ties follow R-R01. Initial ownership, scoring window and resets remain open. |
| R5 | Other players earn a percentage fewer points on a drink in an owned territory than its owner. | **Proposal only, not agreed:** whether the Owner takes a share of other Players' Points or weakens their Points is still open (D-01). If agreed: apply the reduction to non-owners; percentage, rounding, unclaimed territory behavior and ownership timing remain open. |

## Implementation recommendations (not yet agreed rules)

- Capture current device location alongside a newly captured photo. Inspect
  embedded photo coordinates when available as supplementary evidence.
- Validate location, configured drink/size, eligibility and score on the server.
  Determine territory from the location; do not trust a client-selected territory.
- Keep an accepted check-in's drink/size, base points, applied modifier,
  awarded points and rule version so its score can be explained later.
- Prevent retries or concurrent submissions from awarding points twice.
- Evaluate the modifier using ownership immediately before accepting the
  check-in; save points and recompute ownership atomically. This avoids a
  check-in changing the modifier used to score itself. Team agreement needed.

Location evidence can support a location check; it does not automatically
verify that the selected drink type/size is accurate or that it was consumed.

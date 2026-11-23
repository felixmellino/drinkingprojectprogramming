# Rules

## Minigames

### R-M11 Reaction Duel (replaces the solo Reaction Test, 19 November 2026)

Decided by Felix (Location & Territories) on 19 November 2026; the Games tile that
showed the solo Reaction Test (R-M06–R-M09) now opens the Reaction Duel.
- A player challenges another lobby member (in team lobbies: a player of another
  team) for a stake of **1–10 season points**. Both must have the full stake free;
  acceptance reserves it on both accounts (same reservation as Quiz Duel).
- After acceptance both play **three reaction tries** on their own phone within
  15 minutes. Each try waits a random 3.5–6.5 s, then TAP NOW; the time counts if it is
  100–2000 ms. A tap before the signal, or under 100 ms (a guess), is a false start:
  red screen, the try repeats. No tap within 2 s = missed.
- **Best of three:** try n is compared with the opponent's try n; the faster time wins
  the round. More rounds wins. Equal rounds -> lower total time wins. Equal total -> draw.
- The winner receives the stake from the loser (shared `quiz_transfers` ledger, so it
  counts in standings and profile stats). A draw returns both stakes.
- Time runs out: unplayed tries count as missed (a player who played beats one who did
  not; nobody played -> draw). Invitations expire after 10 minutes.
- Normal seasons: one accepted outgoing and one accepted incoming duel per 06:00-based
  night. Test seasons: no nightly limit. Opens with the scoring window (test seasons:
  any time while the season is active). One running Reaction Duel per player.
- The opponent's times stay hidden until the duel ends; only their progress is shown.
- Limit: like the old Reaction Test, the phone measures the time; the server checks
  that it is 100–2000 ms and that the tap arrives after the signal.
- Code: `migrations/025_reaction_duel.sql` (decides results), `core/reaction_duel.py`,
  `reaction_duel_ui.py`, `components/reaction_duel/`. Old Focus attempts and boosts
  stay in the database and in scoring history.

### R-M06 Focus Challenge unlocks and attempts

**Replaced on the Games tab by R-M11 (19 November 2026).** Kept for history: old
attempts and boosts still count in scoring.

Players see this game as **Reaction Test** (renamed on screen 19 November
2026); the rules, code and saved data keep the name Focus Challenge.

Team approval reported by the contributor on 19 November 2026. New v1 seasons
whose frozen snapshot contains `focus_challenge.version = 1` enable this game.
Existing snapshots are not edited. The following gates apply to normal seasons.
Contributor-approved QA exception, 19 November 2026: the frozen JSON boolean
`scoring_rules.test_mode=true` enables Focus immediately, including existing v1
test seasons without a Focus snapshot. No uploads are required; failed and
successful attempts can be replayed sequentially without a nightly limit.
Names, string values and normal seasons never enable the exception. Migration
015 supplies the fixed v1 configuration for older QA snapshots without editing
them. Focus can run any time during an active QA season.

Count the member's accepted v1 drink entries in this lobby/season and the same
06:00-based evening, irrespective of type/size. Their shared Chug Duel entry
counts once. Retakes, rejected submissions and duplicate retries do not count;
deleting an image preserves its accepted entry and this count under R7.
The first attempt unlocks at five entries, then at seven, nine, eleven, etc.
after failures. Starting atomically consumes that attempt; simultaneous starts
recover the same saved attempt. Focus and Chug Duel allowances are separate.
Only one game may be actively running for a member at a time.

### R-M07 Focus Challenge tasks and variation

Play reaction, memory and precision in order, even after a failed task.
Contributor revision, 19 November 2026: failures mark only their current task;
all three tasks contribute to the final reward under R-M09. Migration 022 applies
this to new attempts while preserving previously started games. Contributor revision,
19 November 2026: new attempts use one signal and a tap within 220 ms; no early
taps. Migration 021 supersedes reaction-only migrations 018/019/020 and applies this
to new attempts in existing eligible seasons
without editing season snapshots. Attempt-level configuration preserves rules
for games already started before this revision. Memory requires reproducing seven
positions exactly. Precision requires twelve correct taps within twelve seconds;
a wrong tap fails Precision. Difficulty is a pilot setting needing human phone
calibration, not a health benchmark. Passing is not a sobriety assessment.

Each new attempt receives private server-generated random material: independent
3500–6500 ms reaction waits, a fresh 3x3 memory sequence with no adjacent repeats,
and new valid precision positions. Refreshing cannot reroll it. Memory flashes
650 ms per position with 200 ms gaps, followed by fifteen seconds for input.
New attempts include all three stages (contributor choice resolving PR #64).
Already-running reaction-only attempts retain their previous rules and
repeatable false starts.
For new flow-version-3 attempts, an early or slow reaction tap marks Reaction
as missed and opens Start memory with its one-second lead-in and preview.
Finishing or failing Memory opens Start precision. Each completed task's
pass/fail result is saved and shown, including after a refresh. These ready screens keep
the next stage from starting unexpectedly during a page update.
Precision targets are 52 px with consistent normalized margins and minimum
movement; no colour-only matching is required.

### R-M08 Focus Challenge interruptions and deadlines

Resume the same persisted attempt and progress; its clock keeps running.
Ready screens have thirty seconds. New reaction signals allow 500 ms for a
response, but anything above 220 ms still fails R-M07. The whole attempt has a
three-minute maximum and ends sooner at 06:00, scoring closure (normal seasons)
or season end. A task timeout marks that task as missed and offers the next
task; expiration of the whole attempt ends it without an incomplete reward.
An attempt finishing with zero or one pass requires the next unlock count in
normal seasons; QA may retry immediately. Leaving the screen itself
does not create or refund an attempt.

The server allows two seconds for delivery of stage evidence, while browser
timers enforce the actual task budget. This does not extend the overall,
06:00, normal scoring or season cutoff. Timers use a monotonic browser clock anchored
to server timestamps. Replayed/stale messages recover the recorded result.
Precision checkpoints save full tap prefixes without blocking the next local tap.

### R-M09 Focus boost and scoring

Contributor revision, 19 November 2026: after all three tasks are resolved,
three passes grant x1.5, two grant x1.25, and zero or one leave points unchanged.
Both reward tiers count as the one successful attempt per normal lobby evening.
Either reward applies to future ordinary drink season and matched-territory points for sixty minutes,
ending earlier at scoring closure or season end. It can continue past 06:00.
Boosts never exceed x1.5; an unexpired prior-evening boost blocks a new Focus
attempt until it ends. QA may replay while a boost is active; a further win
refreshes that tier's hour rather than multiplying or adding durations. When QA
effects overlap, use the highest currently active multiplier; a later x1.25
win cannot downgrade a still-active x1.5 reward. QA boosts
end at the earlier of sixty minutes or season end, and never change when drink
submissions are accepted. Chug Duel entries/transfers keep their normal scoring.
The owner earns 25% of the boosted award as additional season income, using
the owner immediately before the entry as usual. No self/team-self income.

In team mode only the successful member's ordinary entries are boosted; their
awards add to the team totals. Teammates' other entries are unchanged. Eligibility
uses authoritative receipt time: boost start <= check-in receipt < expiry.
The entry stores its source Focus attempt and exact multiplier. Owner income
on a one-point drink boosted to 1.25 is exactly 0.3125, without rounding.
Corrections retain that original
multiplier and replay ownership/income without compounding or depending on
whether the boost is still active. Photo deletion does not remove awards.

Store awards as exact PostgreSQL numeric half-points. Existing
`owner_bonus_quarters` remains compatible but can contain half a quarter,
representing exact eighth-points: boosted 1 -> 1.5; owner income -> 0.375.
Display up to three decimals without rounding this income away. The server
determines rewards and awards; browser timing/tap evidence is trust-based and
does not establish automated anti-cheat or sobriety verification.

See [implementation and activation](../FOCUS_CHALLENGE.md).


### R-M10 Time Duel

Contributor-approved 19 November 2026: [Time Duel](TIME_DUEL.md) defines three
hidden-timer rounds on two phones, identical random 5–12 second targets,
independent outgoing/incoming nightly roles, abandonment and exact-tie rules,
and an automatic one-hour x1.25 **season-only** ordinary-check-in reward.
Focus retains its existing effects; only the higher active multiplier applies.
Shared migration 017 was applied on 19 November 2026. Teammate review and
deployment remain pending.


### R-M01 Chug Duel invitation and opponents

In a v1 season with scoring open, challenge another member of the same lobby.
The challenger selects a drink and size from the frozen scoring table; the
recipient must accept these terms on their own account/device. Both drinks
have that selection. Self-challenges and cross-lobby opponents are rejected.
In a team lobby both players need different teams. Recheck teams before start.
One pending outgoing invitation and one accepted/started duel per player are
allowed at a time. Decline/cancel before start awards no points.

Source: contributor's explicit answers, 18 November 2026. Operational defaults
are explained in [CHUG_DUEL.md](../CHUG_DUEL.md).

### R-M02 Two separate nightly allowances

Each member can play once as challenger and once as recipient per lobby and
game night. A night rolls over at 06:00 in the season timezone: 23:59 and the
following 00:01 share the allowance; exactly 06:00 starts the next one.
Other lobbies have independent allowances. Acceptance reserves both respective
roles atomically; starting consumes them. A rejected, declined, expired or
cancelled pre-start invitation consumes neither. A second acceptance cannot
reserve an already used role, including concurrent requests. The opposite
role remains available after a finished game.

Source: contributor's explicit answers, 18 November 2026. This is an explicit
exception to the earlier shared-one-minigame-per-night design for Chug Duel.

QA exception, contributor decision 18 November 2026: when the season's frozen
`scoring_rules.test_mode` is the JSON boolean `true`, players may challenge and
accept repeatedly without a daily/nightly count limit, including after a
started abort. Show Unlimited in both allowance indicators. A lobby name or
a caller-supplied flag cannot enable this. Existing QA seasons also qualify.
One pending outgoing invitation and one accepted/started duel per member still
apply, as do the scoring window, season end, photo/GPS rules, countdown
and exactly-once point transfer. Migration 031 removes the posting cooldown
from both check-in paths in test seasons. A player may
repeat only after the previous game has ended. Normal seasons retain the two
separate nightly allowances. This is enforced in Python and migration 012.

### R-M03 Shared check-in and base-point transfer

After acceptance the host takes one shared fresh photo and supplies their
current accepted phone GPS for both players. Apply normal photo sanitation,
location, territory and season/window checks, plus the per-member cooldown
in standard seasons. Store two
linked normal drink entries in one transaction, each with its own private
copy of the shared image. Invalid evidence or either member's cooldown
rejects the entire start: neither gets a new entry or points. Exact GPS is
discarded after validation. Each image copy follows its owner's existing R7
deletion/retention policy. Duel drink/size selections cannot be corrected
individually after start; delete images without changing points as usual.

At start both get normal base season/territory awards and normal owner income.
At a recorded win transfer only the loser's drink's base season points to the
winner's saved member/team account. Two 3-point drinks yield 6/0 base season
points. Territory base points and all owner income stay unchanged. Result
retries award nothing extra. The transfer gets its own ordered scoring event
so earliest-reaching ties use result time. Within an exact same-event tie,
preserve the previously higher-ranked account. Replaying corrected unrelated
entries preserves the transfer and recalculates normal owner income.

Source: contributor's explicit answers, 18 November 2026. Supersedes the
items-only reward rule for Chug Duel. Earlier source entries are unchanged.

### R-M04 Shared-phone finish

The challenger hosts a split screen with one named half per participant.
Both press Ready, then the server starts a three-second countdown. Ignore
early taps; the first finish tap after GO wins. Only the authenticated host
can submit one of these two participants as winner. A nonparticipant,
recipient-device result, invalid winner or pre-countdown result is rejected.
First tap wins even when browser events arrive close together. Completed
results are immutable, including retries with a different winner. Physical
completion is trust-based; the app only records the tap.

Host presentation, contributor request 18 November 2026: once started, show
the two named halves in a fixed full-viewport board. Hide app navigation and
disable page scrolling through Ready, countdown, GO and the outcome. Keep
the same board mounted while the server arms the game; show all three
countdown seconds without restarting them on refresh polling. A compact
exit retains the existing no-winner abort action. Keep the confirmed outcome
visible until the host chooses Back to Minigames, then restore navigation.

Source: contributor's explicit shared-device decision, 18 November 2026;
three seconds and first-browser-event handling are operational defaults.

### R-M05 Expiry, interruption and navigation

Invitations expire at ten minutes (inclusive). Accepted setup and started
play each also have ten minutes, capped by the next 06:00 rollover, scoring
close and season end. An accepted pre-start cancellation/expiry releases
reservations. After start, either participant can end without a winner;
expiry does the same. Both retain their normal drink awards, no base-point
transfer happens and the used role allowances remain consumed. A connection
loss can resume the saved started game until expiry. A lost successful reply
recovers its existing start/result instead of creating another one.

Minigames is the Games tab, immediately right of the check-in plus in the bottom navigation.
The catalogue shows pending incoming invitation counts on the Chug Duel, Quiz
Duel and Time Duel tiles for the selected season. The Games tab icon shows
the combined count. Counts refresh automatically. Open a game to accept or
decline an invitation, cancel a sent invitation or resume an accepted or
running duel. Accepting opens that game's setup on the recipient's device.
Migration 021 for Time Duel and migration
022 for Quiz Duel keep every pending invitation visible when a player has
more than 20. Both migrations were verified on the shared WeGoPub database
on 19 November 2026.

New games are blocked outside normal scoring availability.

Source: contributor's explicit interruption and navigation answers,
18 November 2026; accepted/start phase deadlines are operational defaults.

## QA season check-ins (updated 23 November 2026)

Ordinary check-ins are open 24/7 in explicitly marked test seasons, from
`starts_at` inclusive to `ends_at` exclusive. Ending a test season early
closes check-ins immediately (R-S04). Create lobby and Retry lobby setup
offer an unchecked Test season option. The rule applies to existing and new
seasons with the frozen JSON boolean `scoring_rules.test_mode=true`.
Standard seasons use Thursday 18:00–Sunday 18:00 in the lobby timezone.
Photo, GPS, points, and correction rules still apply.

Test seasons allow consecutive ordinary check-ins and Chug Duel entries
with no posting cooldown. Standard seasons have a two-minute posting
cooldown. R-M02 allows unlimited sequential Chug Duel replays in test seasons.
Since 23 November 2026 (contributor decision, migration 033) Chug Duel is open
on any day of an active test season, like check-ins and the other duels, so the
demo lobby can play every day. Standard seasons keep Thursday 18:00–Sunday 18:00.

This file will hold every decided game rule with an ID and its allowed, rejected and boundary cases.

## Scoring v1 working implementation

The contributor authorised implementation on 17 November 2026. The current
contract is [SCORING_V1.md](SCORING_V1.md); [the handoff](../SCORING_IMPLEMENTATION.md)
records the explicit boundary defaults and verification. It is implemented
on `Scoring`, awaiting teammate review and shared migration. Existing seasons
remain legacy; the new rules apply to new v1 seasons. The earlier
[planning proposal](SCORING_PROPOSAL.md) and three-page PDF are historical
review records, not a claim of current deployment.

## Check-in

### R-C01 Drink suggestion from the photo (21 November 2026)

When the server has an Anthropic API key, the Check in page offers a
**Suggest my drink from the photo** switch, on by default. While it is on,
the page sends the check-in photo (metadata removed, scaled to at most
1024 px) to Claude, once per photo, and preselects the drink and size it
suggests. The switch says where the photo goes; a player who turns it off
sends nothing, and the choice stays for the rest of the visit. A photo that
cannot be submitted (outside the game window or during the two-minute
cooldown) is never sent. It is only a suggestion. (The submit check was added
21 November 2026 after the code review; on by default since 22 November 2026,
contributor decision, replacing the opt-in of 21 November.)

| Case | Outcome |
| --- | --- |
| Drink and size recognised with high or medium confidence | Both are preselected; the page says "Looks like a large beer. Change it if that's wrong." |
| Low confidence in drink or size (revised 21 November 2026: always the best guess) | Claude's most likely drink and size are still preselected; the page says "Best guess: a large beer. Check it before you submit." Claude has no "unknown" answer. |
| Several drinks visible | The drink in front is preselected; the page says so and asks the player to check. |
| A shot, or no size given | Only the drink is preselected (a shot has no size). |
| No drink visible | Nothing is preselected; the page says so. Check-in is not blocked. |
| No key, timeout (12 s), API error, refusal or malformed answer | Normal form, no message. Asked once per photo, not on every rerun. |
| More than 10 recognitions by one player in a rolling hour | The 11th photo is not sent; the page says suggestions are paused. A call exactly one hour old no longer counts. Failed calls count too. The count lives in the server process and resets on restart. |

The player always confirms or changes the selection, and points come only
from the selected drink and size (R3, SCORING_V1). The suggestion never
blocks a check-in, never changes points, and is not anti-cheat evidence.
Legacy seasons do not use it. The server log records Claude's answer
(drink, size, confidence, several drinks) without the photo or the player.
Code: `core/drink_recognition.py` (rules),
`drink_recognition.py` (API call), `pages/3_Check_in.py`.

## Ranking

### R-R01 Ties
When two Players have the same Points, the Player who reached that score first ranks higher.

Source: team decision, 2026-11-17.

## Season

### R-R02 Season length
A lobby's season length is chosen when the lobby is created, from exactly
three options: one week, one month, or three months.

Source: team decision, 2026-11-17.

### R-R03 One competition per lobby
A lobby runs for its chosen 7/30/91-day duration exactly once, with the early
closure option for test seasons in R-S04. At its competition's end timestamp
it becomes a past lobby automatically and cannot
start another season. Start a new lobby for another competition. Keep the
existing Season entity/IDs for scoring and history; retain older multi-season
records unchanged, using their latest competition for the overview.

Allowed: create/join a lobby and start its first competition, or retry setup
when no season was saved. Rejected: adding a second competition even after
expiry. Boundary: `now == ends_at` is past; existing check-in cutoff applies.
The database serializes season inserts per lobby to reject concurrent renewals.

Source: contributor decision, 2026-11-18; supersedes same-lobby renewal in the
earlier scoring contract. Photo access and ranking rules are unchanged.

## Season awards (21 November 2026)

### R-S01 Awards and what they mean
When a season has ended, every player of that lobby can open its recap. It
shows the podium (top three of the final ranking) and these awards:

- **MVP**: rank 1 of the final ranking (R-R01 decides ties).
- **Most territories held**: the most territories owned at the season's end.
- **Biggest takeover**: the takeover (a territory taken from another owner, not
  a first claim of a free one) where the previous owner had the most points in
  that territory at that moment.
- **Most captures**: the most times a player gained a territory, first claims
  included.
- **Most drinks**: the most accepted check-ins.
- **Your season**: the viewer's rank, points, drinks, territories held and captures.

Awards are derived from the saved entries and duel transfers with the same
replay as Ranks and the Map (`core/season_recap.py`). They are not points and
change nothing in the ranking. An award without a winner (for example no
takeovers) is left out. Team lobbies award teams. Seasons scored before v1
(legacy) show MVP and Most drinks only.

### R-S02 Award ties
A tie for most territories, captures or drinks goes to the better final rank.
Two equally big takeovers: the earlier one wins.

### R-S03 Finishing a season
After the season ends, **Finish season** appears only for that lobby's
current admin on its card in Past Lobbies, beside **Make current** when
available. The creator is the only implemented admin and must still be a
member. The button plays the personal recap story and opens the awards card.
**Close** saves the viewer's recap completion (migration 029,
`season_recap_views`). On later visits the admin sees **Season awards**.
Regular members can open **Season awards** as soon as the season ends and
replay the story from there. The recap offers a CSV of the final standings.

**Watch summary on Ranks (22 November 2026, contributor decision).** Once
the season has ended, normally or early by the creator (R-S04), every player
whose current lobby it is sees only a "The season is finished" card with
**Watch summary** on Ranks. Map, Check in, Games, Activity and Check-in photos
show "This season is finished" with **Go to Ranks** and load nothing else.
Watch summary plays the story; **Close** saves it as watched and returns to
Ranks, which then shows the final ranking again, and the lobby's pages open
for viewing. The lobby card's recap button replays it later. Lobbies and
Profile always stay usable, so a player can switch lobby. If the watched
history can't be read (before migration 029 or during an outage), nobody is
held back. The check runs on each page load against the season read fresh
from the database, so an early end reaches other players on their next page.

Recap access is available to players of that lobby, including former members.
Outsiders and players in a still-running season cannot open the recap.
At `now == ends_at` the season counts as ended (R-R03). Finishing twice saves
once.

Source: Niklas, 21 November 2026.

### R-S04 Ending a test season early

Only the original creator, while still a member, can end the lobby's current
active v1 season with the frozen JSON flag `test_mode: true`. A confirmation
sets a permanent cutoff at the database's current time. The cutoff stops
check-ins, drink corrections and new games. Open games use their existing
timeout outcomes at the earlier of their previous deadline and the new cutoff.
Reaction Duel counts unplayed tries as misses and can settle a stake. The
30-day photo retention period starts at the new cutoff. The recap opens for
the creator after confirmation, and other participants get the usual R-S03
recap entry points.

A successful closure is safe to retry. Migration `030_end_test_season.sql`
applies the cutoff and settles the games in the same lobby transaction.

## Territories

### R-T01 Territory set
The game has 48 Territories covering the whole north bank from Alfama and
Baixa to Carcavelos. Central Lisbon has 23 small or medium areas (8
hand-drawn ones in Bairro Alto, Santa Catarina, 3 in Santos and 11 filling
the centre). 24 large areas fill the rest of the way to Nova (Baixa,
Alfama, Graça, Avenida da Liberdade, Marquês de Pombal, Amoreiras, Campo de
Ourique, Lapa, Alcântara, Ajuda, Monsanto, Belém, Restelo, Algés,
Linda-a-Velha, Cruz Quebrada, Caxias, Paço de Arcos, Oeiras, Santo Amaro,
Carcavelos), with the Jamor golf course as its own area. In Carcavelos, the
Nova SBE campus (with the beach) has two small neighbours, Carcavelos
Centro and Rebelva. Neighbouring areas border each other; the outlines stop
at the coastline. Busy streets get small areas, quiet neighbourhoods big ones. Their outlines live in one shared file,
`data/territories.geojson`, as GeoJSON Polygons with a display `name`
(for example "Shortys") and a short, permanent `id` (for example
`shortys`: lowercase letters and digits, words joined by hyphens). The
file is drawn and edited in geojson.io. Every
lobby plays on the same Territories; each lobby's Seasons have their own
Owners.

The file is the only source of truth. The app reads it for the location
check and the standings, and copies it into the database's `territories`
table when the app starts, because saved drinks refer to a Territory by its
`id`. When the file changes (e.g. after a merge), the app notices on the next
page load and copies the new version; no restart is needed.

| Case | Outcome |
| --- | --- |
| Allowed | Adding, removing, renaming or reshaping a Territory by editing the file, as long as R-T02 still holds. A renamed or reshaped Territory keeps its `id`; only the `name` changes. A new Territory gets a new, unused `id`. |
| Rejected | A Territory without a `name`, with a missing or badly formed `id` (capitals, spaces, underscores), or with an outline that is not a closed Polygon; two Territories with the same `id` or `name`. The app refuses to load such a file. |
| Boundary | Changing an outline mid-Season does not move drinks that were already saved; their stored Territory stays. A Territory removed from the file stays in the database so older drinks still point at it, but it is no longer matched or shown in the standings. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-03.

### R-T02 Territories never overlap
Neighbouring Territories may share a border but must never overlap, so a
location lies inside at most one Territory. Gaps between Territories are
allowed. A drink in a gap counts as outside every Territory (see R1).

| Case | Outcome |
| --- | --- |
| Allowed | Two Territories sharing an edge; empty space between Territories. |
| Rejected | Any area that lies inside two Territories. |
| Boundary | A location near or on a shared border belongs to the Territory that contains the measured point (R-L03). |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-03.

### R-T03 Random territory boost

Contributor-selected 21 November 2026. Migration 027 and the Map and Check-in
pages implement this rule for newly created competitions with the boost in
their frozen scoring rules. Team review and deployment are tracked in D-21.

- A verified ordinary check-in starts a boost if another competitor had a
  verified ordinary check-in in the same territory within the preceding 30
  minutes, inclusive. Competitors are distinct players or opposing teams.
- The lobby draws uniformly from the triggering territory and territories
  up to two shared borders away in the current map. The draw uses the map's
  shared-border test with its 0.5 m drawing tolerance. Corner contact alone
  does not count. The map highlights the drawn territory with a clock pin.
- Boosts start at least 150 minutes apart in each lobby. A boost lasts 15
  minutes and starts only if that whole duration fits before the scoring
  window and season close. The triggering check-in earns its usual points.
- Subsequent ordinary check-ins received in the boosted territory before
  expiry earn ×1.25 territory and season points. When another boost also
  applies, use the highest applicable multiplier for each account. Eligible
  prior owners get 25% of the territory award as additional season income.
  The original boost is retained when correcting a saved drink or size.
  Chug Duel entries neither trigger the draw nor receive the boost.

## Location

### R-L01 Location source
Changed 20 November 2026 (Location owner): the app no longer asks for the phone's
location by itself right after login; Safari answered such unprompted requests
unreliably. Instead Profile has a **Location switch**. Turning it on is a tap inside
the page, so the browser asks for permission right then. The choice is remembered
in this browser. The Check-in and Map pages (and the Chug Duel start) follow the
GPS automatically only while the switch is on. The Map also has a small Location pill
under its top bar (same on/off choice, synced with the Profile switch through the
browser and across tabs); on the Map that pill itself follows the position. Before the switch was ever turned on
they ask nothing. If the browser has forgotten its answer (Safari does, per visit),
they probe once for four seconds; without a quick position they report "off" so the
player taps the switch again, because an invisible frame cannot show the question
reliably. When the switch is off they say
"Location is off. Turn it on in Profile → Location." (Check-in also offers an
"Open Profile" button.) If the browser blocks location, the switch says so and
the player allows it in the browser settings (e.g. Safari: website settings →
Location → Allow) and turns the switch on again. If the browser asks again for
each new visit, the player taps the switch off and on once to answer it.
A check-in uses the newest reading at the moment the player submits. GPS data
stored in the photo is not used. Readings stay in the open session only and
are never saved; only the check-in's result and territory are stored.

| Case | Outcome |
| --- | --- |
| Allowed | Location is on and the newest phone reading passes R-L02 and R-L04. |
| Rejected | Location is off, unavailable, denied, malformed, inaccurate or stale: Submit remains disabled and no entry or points are saved. |
| Boundary | Switching location off clears its usable reading. Re-enabling requires a fresh valid reading; previous readings cannot authorize a submission. |

### R-L02 Accuracy limit
The phone reports how many metres its reading may be off. A reading off by
at most 50 m is accepted. A worse reading counts as uncertain: the
check-in is not saved and the player retries (R2).

| Case | Outcome |
| --- | --- |
| Allowed | Accuracy of 50 m or better. |
| Rejected | Accuracy worse than 50 m. |
| Boundary | Exactly 50 m is accepted. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-10 (uncertainty).

### R-L03 Borders
An accepted reading belongs to the Territory that contains the measured
point, even if its accuracy circle reaches into a neighbouring Territory.
A point in a gap or outside every Territory counts as outside (R1).

| Case | Outcome |
| --- | --- |
| Allowed | A point inside a Territory, however close to its border. |
| Boundary | A point exactly on a shared border is assigned to one of the two Territories; which one is not defined. |

Source: Location & Territories block (Felix), 2026-11-17. Resolves D-10 (edge handling).

### R-L04 Fresh readings only
A reading may be at most 60 seconds old when it is used. The app refreshes
the reading at least every 30 seconds while the page is open, and whenever
the player moves more than 20 m.

| Case | Outcome |
| --- | --- |
| Allowed | A reading up to and including 60 s old. |
| Rejected | A reading older than 60 s: Submit stays disabled until a fresh one arrives. A reading time more than 60 s in the future (wrong phone clock or tampering) is invalid. |
| Boundary | Exactly 60 s old is accepted. |

Source: Location & Territories block (Felix), 2026-11-18. Resolves D-10 (age).

## Direction agreed on 17 November 2026

The user's updated direction replaces buddy confirmation. Exact values and
boundary behavior listed in `OPEN_DECISIONS.md` are not yet agreed.

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| R1 | A city is divided into territories. An accepted check-in with a matched territory contributes its points there. | Assign a territory only when location verification identifies one. A verified location outside every territory can earn season points only, subject to the same eligibility rules. |
| R2 | Check-in requires a drink type, a size, a fresh photo taken in the app, and automatic location verification. | If location is missing or uncertain, keep the photo and drink selection on the form so the player can retry. Save the entry and award points only after verification. Only the phone's GPS reading counts (R-L01, R-L02). Discard raw coordinates after verification. |
| R3 | New v1 seasons use the frozen category/size table in [SCORING_V1.md](SCORING_V1.md). | Four categories; sizes for beer/wine/mixed; one shot serving. Reject unsupported combinations. Large bonuses are already included. Legacy seasons keep their prior awards. |
| R4 | The player with the most points in a territory owns it. | A unique leader owns the territory. Ties follow R-R01. Initial ownership, scoring window and resets remain open. |
| R5 | In v1, the previous territory owner earns an additional 25% of another player's base award in season points only. | The visitor keeps full base points. No self-income, territory income or income cap. Use exact quarters, or eighth-points for Focus under R-M09; replay affected ownership/income after a timely correction. See [SCORING_V1.md](SCORING_V1.md). |
| R6 | Current lobby members see their own unexpired photos. Sharing with other players is OFF by default for all accounts and controlled by one account-wide switch in Profile → Account & security → Photo privacy. | The switch applies to past and future photos across all lobbies. In individual mode, another member needs the uploader's consent. In team mode, current members of the entry's saved team can view its photos internally regardless of the switch; opponents need the uploader and every current member of that team to opt in. Check membership and consent again before each image download, as well as filtering the gallery. See R-PH01 below. |
| R7 | The owner can delete their photo while keeping the drink entry and its awarded points. Photos expire 30 days after their season ends. | Only the entry's author may request deletion. Remove the stored image and mark its reference as deleted, preserving the score and standings. Deny photo access at the expiry boundary and remove expired files through scheduled cleanup. |

### R-PH01 Photo sharing and attribution

Contributor choices, 19 November 2026: a missing preference means OFF for
existing and new accounts. Only the signed-in owner can save their account's
preference. The current roster controls team consent even for old photos:
one new member with sharing OFF hides that team's photos from opponents.
An empty team grants no opponent access. Historical attribution uses the
team saved on the check-in, not a later team assignment; if an uploader has
left that team their own consent is still required for opponent access.
Lobby membership is required for every audience, including the owner.

Chug Duel's two image copies follow each entry owner's sharing setting
independently. One participant opting out does not block the other copy.
This can leave the same shared image visible through the other participant;
the control does not promise consent from every person pictured.

Solo photos have a stable player-coloured frame and username. Team photos
have a stable team-coloured frame, team name and uploader's username. Names
remain readable independently of colour. Deleted/unavailable photos keep
their attribution on otherwise visible history cards. Scoring, check-in
requirements, standings, corrections and R7 retention do not change.

Turning sharing OFF denies subsequent gallery/download requests; images
already delivered to a page, downloaded or screenshotted cannot be recalled.
No public image URL is generated. Missing consent denies sharing; a failed
consent lookup never falls back to serving the image.

## Implementation recommendations (not yet agreed rules)

- Capture the current device location when the player submits (R-L01).
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

## Accounts (agreed 17 November 2026)

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| A1 | Game pages require authentication; first visit offers registration and login. | A returning player logs in without recreating an account. Logged-out access stops before any game content or actions. |
| A2 | Registration requires first name, surname, username, email and a personally chosen password entered twice. | Reject empty names, malformed email, mismatched passwords and passwords shorter than 8 characters. Eight characters are accepted; implementation also rejects whitespace-only passwords and bounds input length. |
| A3 | Username and email must each be unique, ignoring case and surrounding whitespace. | Duplicate submissions cannot create another account, including concurrent submissions. Only username is public; name and email stay private. |
| A4 | Login uses email and password, without registration email verification. Password recovery is available through the registered email (authorised 18 November 2026). | Incorrect credentials leave credentials and game points unchanged. The login screen offers Forgot password and a code-based reset form. |
| A5 | Existing game progress is preserved. | Keep player IDs and all linked game records. No account-upgrade screen is shown; legacy records without an email require administrator migration to use email login. |
| A6 | Profile offers one Create account / Log in selector. | Only the selected account form is shown. No upgrade controls; Log in offers Forgot password. |
| A7 | Login has an optional Remember Me checkbox. | Checked: remember this device for 30 days using an opaque token, without storing the password. Unchecked: no persistent login. Logout revokes this device; password changes invalidate remembered access. Expired/invalid tokens do not authenticate. |
| A8 | Successful registration opens Lobbies with a one-time WeGoPub welcome. | Join a lobby and Create a lobby have equal prominence and open the existing forms. Dismissing the welcome or choosing either action ends it. Ordinary sign-in keeps its usual destination, including for accounts with no lobby. |

Login throttling (ten attempts per account per 15 minutes) is a security
implementation setting, not a scoring rule. Recovery requests and reset attempts
share this throttle. Unregistered emails share a separate per-process budget
for password checks. Brevo's HTTPS API sends recovery emails; SMTP is not required.

- A11 (authorised 18 November 2026): Forgot password sends a random 16-character
  hexadecimal code, grouped with hyphens for readability, to the registered email.
  The database stores only a hash bound to the current password hash. Codes expire
  at 15 minutes (the exact expiry is rejected) and can be consumed once, atomically
  with the password update. A new request replaces the prior code, with at least
  one minute between requests. Changing the password invalidates outstanding codes
  on their next credential lookup. Invalid input, missing/expired/used codes and
  throttled resets leave passwords and points unchanged. The new password follows
  A2 and must differ from the old one. Reset does not automatically sign in;
  existing active and remembered sign-ins fail their next credential check.
  Requests give the same public message for unknown accounts, throttling and email
  delivery failures. Delivery failures remove only their own pending code.
  Names, game records, player ID and email remain unchanged.

## Friends (agreed 17 November 2026)

| ID | Rule | Allowed / rejected / boundary outcomes |
| --- | --- | --- |
| F1 | Signed-in players search all app usernames, independent of lobbies. | Search is partial, ignores case and surrounding whitespace, and returns at most 20 results sorted by username. Empty search returns none. Search excludes yourself and exposes only username, never name, email or credentials. No profile pictures or new profile fields. |
| F2 | Friendship requires an explicit request and acceptance by the recipient. | Only the recipient may accept or decline a pending request; only the sender may cancel it. Reject self-requests, duplicate requests, requests between existing friends, and responses to non-pending requests. An opposite-direction request does not automatically accept. |
| F3 | Declining a request starts a 10-minute waiting period. | Neither player can create a new request for that pair before 10 minutes have elapsed; exactly 10 minutes is allowed. This pair-wide interpretation prevents reversing a request to bypass the wait. Cancellation does not start a waiting period. |
| F4 | Accepted friends appear in both players' private lists. | Each player can see only their own relationships. Either friend may remove the friendship, removing it from both lists. Removal allows a new request, which again needs acceptance. No friendship changes points, lobby membership or photo access. |
| F5 | Requests are managed on Profile or beside lobby members and stored across sessions. | Incoming requests offer Accept/Decline, outgoing requests offer Cancel, and accepted friends offer Remove. Refresh friends reloads changes made by other players; lobby member controls reload with Refresh lobbies and the 60-second lobby refresh. No email notifications. Concurrent actions cannot overwrite an unseen change. |

Implementation: `core/friends.py` holds validation and search rules;
`friends_ui.py` renders controls using the authenticated session's player ID;
`data/db.py` stores state through a version-checked database function. The
server service key is the only database role with friendship access.

### Profile edits (agreed 18 November 2026)

- A8: A signed-in player can change their own username, first name and surname.
  Registration name limits and case-insensitive username uniqueness still
  apply. Email is read-only. Player ID and all linked game progress/friends
  remain unchanged. An expired credential version cannot save an edit.
- A9: Password changes require the correct current password and a matching
  new password following A2. The new password must differ from the current
  one. Current-password attempts share the login throttle. Successful changes
  invalidate active and remembered sessions; the player logs in again.

### Profile pictures (agreed 18 November 2026)

- A10: A signed-in player may take a camera photo or upload a JPEG, PNG or
  WebP from their library in Edit profile. Show a circular centre-cropped
  preview; save only after Save picture. Saved pictures persist across visits
  and devices. The player can replace or remove their own picture. Without a
  saved picture, use username initials. Neither pictures nor changes affect
  points, memberships or account identity.
- A11: Show the picture left of the username in Profile, and beside that
  player in friend lists and incoming/outgoing requests. Only the owner,
  accepted friends and both participants of a pending request can retrieve
  it. Declining, cancelling or removing the relationship ends further access.
  Search results for unrelated players show initials. Previously downloaded
  copies cannot be recalled.
  **Revised 22 November 2026 (Felix): lobby-wide visibility.** Players who are
  both current members of the same lobby also see each other's picture. It
  replaces the initials wherever players are shown: Ranks (podium and rows),
  the Activity feed, map owner badges and the territory list, lobby leader
  cards and team member lists. Leaving the lobby ends access on the next page
  load. Strangers still see initials. Checked fresh on every page render
  (`core/profile_photo.can_view_profile_photo`, `db.list_co_member_players`).
- A12: Profile pictures use private server-only storage. Accept at most
  10 MiB and 20 million pixels; reject unreadable/animated images. Preserve
  orientation, centre-crop to a 512-pixel square, flatten transparency to white
  and re-encode JPEG without embedded metadata. Current images remain until
  replaced or removed. Failed writes can leave inaccessible uploads; remove
  unlinked uploads after a 24-hour grace period through server maintenance.

### Lobby member controls (agreed 18 November 2026)

- Joined lobby cards display their invite code alongside the name, leader and
  timing. Only joined lobbies are shown.
- Clicking a lobby card opens a popup over the blurred/dimmed overview showing
  its name, invite code and, in individual mode, all current member usernames, including players
  with no points. This works for active, past, upcoming and incomplete lobbies.
  There is no top-three preview. View leaderboard below the members closes
  the popup and opens the full Leaderboard for that lobby. Close, ×, outside
  click and Escape dismiss it. Long lists scroll; no scoring rules change.
- Create lobby and Join with a code are separate top-of-overview buttons.
  Forms open in dismissible modals over a blurred/dimmed background. Cancel,
  ×, outside click and Escape do not save. Successful creation/join opens
  that lobby's member or team popup with a notice. Existing options and validation stay.
- Each member row shows only the viewer's relationship: You, Friends, Request
  sent, Incoming friend request with Accept/Decline, or Add friend. F2–F5
  still apply, including the decline waiting period and concurrent-write checks.
  No new friendship rules, account fields or lobby-wide picture access.
- Membership is rechecked before showing members. Service failures show an
  error; unavailable friendship state disables actions without hiding usernames.

## Team lobbies (R-TEAM01–R-TEAM05, authorised 18 November 2026)

### R-TEAM01 Competition mode and settings
The creator chooses Individual (default) or Team. Individual lobbies keep
existing rules. Team setup chooses 2–16 teams, 1–20 players per team, and
Random or Players choose. These are fixed settings, not editable after creation.
The capacity is a maximum, not a required roster: play starts immediately,
late arrivals are allowed until the lobby ends, and uneven rosters can occur.
Equal capacities do not guarantee equal participation. There is no normalization
of points by team size. Existing lobbies stay individual.

### R-TEAM02 Joining teams
Teams are created together with the lobby, initially named Team 1, Team 2,
etc. Players choose a team with space in manual mode. A player may switch
before their first accepted scoring entry; after that, assignment is locked.
A member without a team cannot score. Random mode assigns each arriving
member to a randomly selected smallest team with space; no manual switching
or reshuffling. Lobby capacity includes members who have not chosen a team.
Repeated lobby joins retain the same membership and assignment.

Rejected: full lobby/team, another lobby's team, changes after scoring,
manual changes in random mode, joining/switching at or after the finish.
Concurrent joins serialize on the lobby lock, so the final slot admits only
one member. Rejection changes neither membership nor score.

### R-TEAM03 Names and pictures
Only current members of a team can click its name to edit its name and picture.
Names are trimmed, 1–40 characters, without control characters, and unique
within the lobby ignoring case. Members may upload or take a picture, replace
it or remove it. JPEG/PNG/WebP, 10 MB and 20 megapixels maximum; existing
profile photo processing crops to 512×512 JPEG and strips metadata. Encoded
output is limited to 512 KiB. No picture uses initials as the avatar.
Names/pictures can be edited after play and do not change identity or points.
Team pictures are visible only within their lobby. Member profile pictures
retain A11 privacy; other members see initials when access is unavailable.

### R-TEAM04 Combined competition and territory ownership
Every accepted entry snapshots the member's team. The leaderboard ranks teams,
not individual contributions. A team's territory account sums all members'
base points in that territory; the highest total owns it. Ties keep the team
that reached the total first, using the existing database acceptance order.
Season totals combine the members' base awards and the team's owner income.

The existing 25% prior-owner income goes to the owning team when a rival
team scores there. A teammate's entry never generates owner income. The
visiting team keeps all base points. Income counts only toward the season,
never territory ownership. Outside entries earn team season points only.
Corrections replay combined ownership and downstream owner income from the
original event position. Photos/minigames remain attached to their submitting
player; cooldown and minigame limits remain per player, not per team.

### R-TEAM05 Persistence and authorization
Team settings, roster, names, sanitized pictures and entry team identities
are saved in PostgreSQL through migration 010. Assignment and scoring share
the same lobby lock; accepted entry identity is immutable. Team writes and
reads require the authenticated app's existing member checks; anonymous and
Supabase authenticated roles have no access to the team table or write RPCs.
Source: contributor's explicit team-mode choices, 18 November 2026.

## Profile statistics

Quiz Duel's contributor-approved point-stake exception, separate nightly roles,
team-purse rules and twenty-second rounds are defined in [QUIZ_DUEL.md](QUIZ_DUEL.md).
Individual quiz transfers adjust personal lifetime points; team quiz transfers
adjust team season scores and season wins without becoming personal drink points.

### R-P01 Lifetime statistics across active and finished lobbies

Profile → My stats shows four cards: Total points, Drinks, Lobbies played,
and Total Wins. Include all retained active and finished lobbies; do not
depend on the selected lobby. Include every season in multi-season lobbies.
Accepted scoring check-ins count immediately, including existing history.

Points sum the player's own accepted drink awards across those seasons, plus
personal territory-owner income in individual seasons. Replay each season
separately so corrections and owner income agree with standings. Team scores,
teammates' drinks and team owner income are excluded from personal points.
Drinks counts accepted positive-point check-ins, including verified outside
locations and entries whose photo has since expired or been deleted.
Lobbies played counts distinct lobbies with at least one such drink.
Total Wins counts completed seasons (`now >= ends_at`) won individually or
by the player's team, using existing leaderboard tie-breaking. An active
season's current leader is not a winner. A completed season counts even if
another season in that lobby is active. Empty seasons have no winner.

Allowed: five finished lobbies plus one active lobby with 11 personal points
each show 66 points and six lobbies played; leading the active season adds no win.
Rejected: counting a teammate's drink as one's own, a duplicate entry twice,
or an active season as a win. Boundary: a win counts at the season's end
instant; no history shows zero on all four cards. A history-load failure
shows an error rather than a partial total. No scores or entities are changed.

Source: contributor request and clarified answers, 18 November 2026;
active-lobby inclusion and completed-season-only wins confirmed 19 November 2026.

### R-P02 Lifetime stat medals and lobby promotions

Each of the four My stats cards displays its current medal and progress toward
the next rank. Rank thresholds are inclusive and independent per category.

| Rank | Total points | Drinks | Lobbies played | Total wins |
| --- | ---: | ---: | ---: | ---: |
| Newcomer | 0 | 0 | 0 | 0 |
| Beginner | 1 | 1 | 1 | 1 |
| Regular | 10 | 5 | 2 | 2 |
| Contender | 25 | 10 | 3 | 3 |
| Expert | 50 | 20 | 5 | 4 |
| Veteran | 100 | 35 | 8 | 5 |
| Master | 250 | 60 | 12 | 8 |
| Legend | 500 | 100 | 20 | 12 |

Existing history immediately qualifies for profile medals. Feed promotions begin
at the database rollout cutoff (migration 028). A promotion is shown only to
viewers of the lobby where the relevant credit happened, including wins at the
season end and personal owner income or stake transfers that cross a threshold.
One action advancing multiple categories shows one post, naming the highest new
rank in each and omitting totals. An earlier rank crossing suppresses a repeat
announcement after a score drop and recovery. Like check-ins and captures, the
feed is rebuilt from retained, corrected records. Corrections are replayed at
the original check-in position and can change the ranks or posts in that history.
Past-season promotions remain in the lobby feed when another season is selected.

Source: contributor's profile medal thresholds and feed choices, 21 November 2026.

## Leaving and rejoining a lobby

### R-LB01 Departure preserves history

A signed-in member can choose Leave lobby inside the individual or team lobby
popup, review the consequences and confirm, or choose Stay in lobby. This works
before, during and after the competition. Departure sets `LobbyMembership.left_at`;
it does not delete the membership, entries, earned points, team assignment or
minigame history. The lobby disappears from the departing player's joined list.
Fresh membership checks deny further check-ins, corrections, games, team edits
and lobby photo viewing, including from an already-open page. Retained scores
remain in lobby/territory standings and personal lifetime statistics; existing
win and tie rules remain unchanged. Thus a departed player can still win.

### R-LB02 Owner income while absent

Previously earned personal territory-owner income is kept. Individual territory
ownership and territory points remain unchanged, but visitors' accepted drinks
pay no personal owner income to a member who is absent at their acceptance.
Rejoining resumes eligibility for future income; no missed income is backfilled.
Team ownership and income belong to the team and continue normally.

Each accepted entry records the absent membership IDs under the lobby lock.
Replay and corrections use this immutable roster snapshot, including when a
correction changes who owned a territory. This prevents a later departure or
return from changing previously earned income. Existing entries start with an
empty absent roster because departure was not available before migration 016.

### R-LB03 Return and interruptions

Joining again with the invite code restores the same membership, original
joining time, scores, team assignment, cooldown and minigame allowances. A team
slot remains reserved while absent and is shown as Left (slot reserved); leaving
does not let another player occupy it. Returning to a finished lobby restores
history access but does not restart its competition or reopen scoring.

Leaving is rejected while the member has an accepted/started Chug Duel or a
running Focus Challenge. Finish the game or wait for its existing timeout;
expired games are settled by the normal expiry rules when departure is retried.
Unaccepted duel invitations are cancelled on departure. A retry of an already
completed departure is harmless. The player's saved selection of that lobby is
cleared, and the UI can select another active lobby.

Allowed: leave after scoring, keep points in both statistics and standings,
return with the same identity. Rejected: leaving during an active game, acting
for another player, scoring while absent, editing an absence snapshot, claiming
a departed member's reserved team slot. Boundaries: scoring and departure share
the lobby lock; whichever is accepted first determines the absent roster.
Corrections never rewrite that roster. Saved departure and score history survive
a database restart.

Source: contributor request and explicit answers, 19 November 2026. Migration
016 was applied to shared Supabase with contributor authorization on
19 November 2026. All 19 schema/access/history checks and a fresh app-process
read/RPC check passed. Frontend review, merge, deployment and deployed browser
verification remain pending.

### R-LB04 Deleting a lobby

Only the player who created a lobby (its earliest membership, even if they have
since left) can delete it. Deleting hides the lobby for everyone: it leaves
every lobby list, nobody can open it, check in, or play minigames in it, and
saved lobby choices pointing at it are cleared. Nothing is erased: scores,
photos and history stay in the database, in the same spirit as R-LB01. Open
duel invitations and running duels are cancelled. There is no undo in the app.
Allowed: creator deletes after a second, deliberate click. Rejected: any other
player, even a current member, gets "Only the person who created this lobby can
delete it." Boundary: a retry of an already completed deletion is harmless.
Needs migration `017_delete_lobby.sql` (the app keeps working without it, but
Delete lobby fails until it is applied).

Source: contributor request, 19 November 2026 (who may delete and "hide, keep
history" are the implementer's decisions; the team should confirm).

### R-LB05 Personal lobby invitations

After lobby setup, its creator can invite accepted friends while still an
active member, until the competition ends. Existing join codes still work.
A friend already in the lobby cannot receive an invite. Former members can
be invited. Invitations are private to the addressed account and expire
after seven days or at competition end, whichever comes first.

The server sends an email to the friend's registered address using Brevo.
The link opens the invitation on the Lobby page after login. The same request
appears under Pending invites, including when email delivery cannot be
confirmed. Opening the email link is read-only. The recipient can explicitly
accept or decline while signed in. Response links forwarded to another
account, repeated responses, expired requests and deleted lobbies are
rejected.

Accept uses the existing lobby membership and team rules in the same
database transaction as the invitation response. There is no slot
reservation. A full lobby leaves the invitation pending, and the recipient
can still decline. Rejoining restores the existing membership and any
reserved team slot. Joining by code before responding leaves only the
original membership when the invitation is accepted. Declining never
changes membership or scores.

There is at most one pending invitation per lobby and recipient. Sending is
limited to one invite per lobby and recipient per 24 hours and 20 per
creator across lobbies per 24 hours. Migration `026_lobby_invitations.sql`
enforces sending permissions, response ownership, expiry and rate limits.

# Quiz Duel decisions and preparation

Contributor decisions, 19 November 2026. The question foundation is prepared;
the game is not yet active in Minigames.

## Agreed rules

- A lobby member challenges another player, who accepts on their own account.
- Each round gives one quiz point to the faster correct answer. Incorrect answers
  do not earn a point. Each player receives the same question and four choices.
- Normal order: general knowledge, multiplication, logic. There are up to three
  normal rounds. A 2:0 ends the game early.
- If tied after three rounds, play an additional deciding question.
- The challenger proposes an integer stake from 3 to 10 season points, visible
  before acceptance. The winner receives that stake from the loser; quiz points
  only determine the duel winner. Territory points/owner income are unaffected.
- Quiz has its own normal allowance: one outgoing challenge and one acceptance
  per member/lobby/night, independently of Chug Duel. Reuse the season-zone
  06:00 rollover. Explicit test seasons allow unlimited sequential quizzes.

These are the user's selections in this chat, not active scoring code. The earlier
items-only minigame proposal is superseded for Quiz Duel by the explicit stake
decision. The existing Chug Duel exception and Focus Challenge are unaffected.

## Content foundation

- 100 source-linked English general-knowledge questions are checked into the repo.
- The contributor's revised content target is easy/easy-medium: 20% football,
  80% broader general knowledge. Football events/transfers refer to 2022 onward;
  stable club facts may be undated. Detailed census and older niche sports
  questions were removed.
- Multiplication is generated from factors 1–10, not individually authored.
- Logic uses five short templates by default; a sixth, longer box puzzle is an
  explicit advanced preview option. Names and values vary.
- Private snapshots preserve both the question and the answer order across devices
  and reloads; player payloads exclude the answer key.
- A fresh general-knowledge decider can be generated without repeating a question.

See [the preparation handoff](../QUIZ_QUESTION_PREPARATION.md) for code and verification.

## Resolve before activating stakes and live play

- Final round duration; one locked answer per participant is the proposed default.
- What happens if both miss the decider, timing is exactly equal, or play disconnects.
- Invitation/setup expiry, cancellations after acceptance/start, and forfeits.
- Sufficient balance, stake reservation, simultaneous bets and avoiding negative balances.
- In team lobbies: whose purse funds the stake, eligible opponents and score attribution.
- The service's authoritative answer-receipt time and the effect of network latency.

These points do not block preparing question content. They must not be silently
invented by an import script or a browser component when game/scoring is added.

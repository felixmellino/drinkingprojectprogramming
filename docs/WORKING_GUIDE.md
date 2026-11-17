# WeGoPub — Working Guide

How this codebase is organized, how it connects to `docs/ontology/`, how
the four building blocks are split, and exactly how to work on your piece
using Claude Code, even if you can't read code yourself. Read `AGENTS.md`
first for the short version of the team workflow rules; this file is the
full explanation behind them.

## The big picture

Think of the app like a restaurant.

- **`pages/` and `app.py`** are the dining room — what a player actually
  sees and clicks on. The waiter takes an order and brings back a plate;
  no cooking happens here.
- **`core/`** is the recipe book — it says exactly how things are made
  ("a beer is worth 5 points per unit", "a drink only counts Thursday noon
  to Sunday night"). It never touches the real database, it's just the
  written-down rules.
- **`data/db.py`** is the fridge and pantry — the actual data, stored so
  it's still there tomorrow. It's the only file allowed to open the fridge.
- **`tests/`** is a food inspector who checks every recipe against known
  cases, without needing a working kitchen — it proves the rules work
  correctly, with no real database needed.

Follow one real action through the kitchen: a player opens Check-in (the
waiter), submits a drink, the waiter asks the recipe book "is this
allowed?" (`core/checkins.py`), the recipe book checks the rules and says
yes or no, and if yes, the waiter stores it in the fridge (`data/db.py`).
Nobody in the dining room decides the rules; nobody in the recipe book
stores real data.

## `core/` — the rulebook

Every file here is plain Python with no screen code and no database code
in it — that's why `tests/` can check it instantly, with no internet
connection.

| File | What it means, in one sentence |
| --- | --- |
| `models.py` | Defines the "things" in the game — Player, Lobby, Territory, DrinkEntry, etc. — just their labels and fields, nothing else. |
| `constants.py` | Every tunable number in one place: points per drink, the GPS tolerance, the duplicate-check window. Change a rule here, nowhere else. |
| `auth.py` | Turns a PIN into a scrambled code so the real PIN is never stored, and checks a typed PIN against it at login. |
| `lobbies.py` | Creating a player, creating a lobby (with an invite code), joining a lobby, and setting up that lobby's season. |
| `game_window.py` | One job: "is this moment inside Thursday-noon-to-Sunday-evening?" Drinks only count inside that window. |
| `location.py` | Checks whether the phone's GPS reading is accurate enough (50 m) and which territory's drawn area it falls inside. |
| `scoring.py` | Works out how many points a drink is worth (beer and wine scale with amount; shots and long drinks are flat). |
| `checkins.py` | The main gatekeeper: pulls together the window check, the location check, and the scoring to decide if a submitted drink is valid, and builds the record of it. |
| `territories.py` | Works out who currently owns each territory, replaying every drink in time order so that a tie always favors whoever got there first. |
| `leaderboard.py` | The same tie-breaking idea as territories, but for the whole season's ranking instead of one territory. |
| `minigames.py` | Makes sure a player can only play one minigame per lobby per week — no actual minigame logic yet, just the limit. |

## `data/db.py` — the fridge

One file. It's the only place in the whole app that opens a connection to
the real database (Supabase) and reads or writes a row. It converts
between a database row and the plain `core/models.py` objects, but
contains no rules of its own — if you want to know whether something is
*allowed*, that question always belongs in `core/`, never here.

## What you see on screen

| File | What it means |
| --- | --- |
| `app.py` | The very first screen. On purpose, it does almost nothing — just a welcome message — so it never becomes a file everyone has to edit at once. |
| `shared.py` | A handful of tiny helpers every screen reuses: "stop and ask the player to log in if they haven't", "stop and ask them to pick a lobby if they haven't". No rules, no database calls — just plumbing. |
| `pages/1_Profile.py` | Create an account (real name stays private, username is public) or log in with a username + PIN. |
| `pages/2_Lobby.py` | Create a new lobby (and pick how long the season runs), join an existing lobby with its invite code, or switch between lobbies you've already joined. |
| `pages/3_Check_in.py` | Log a drink: pick the type and amount, take a photo, enter your location, and submit. |
| `pages/4_Standings.py` | Shows the season leaderboard and, for each territory, who currently owns it. |

Every page follows the same shape: ask `data/db.py` for the data it needs,
hand it to one `core/` function to get an answer, and just display that
answer. If a page looks wrong, the bug is almost always in the `core/`
function it called, not in the page itself.

## The rest

| File / folder | What it means |
| --- | --- |
| `schema.sql` | The blueprint for the real database tables — run once inside Supabase to create them. |
| `requirements.txt` | The outside tools the app needs installed (Streamlit, Supabase, Pillow, pytest). |
| `tests/` | One file per `core/` file, same name, each proving that file's rules behave correctly. |
| `docs/ontology/` | The actual game design, written in plain English by the team — the source of truth the code is built from. |
| `AGENTS.md` | Course requirements, grading criteria, and the team's own workflow rules. |
| `README.md` | How to set up, run, and test the app locally, plus what's not built yet. |

## How `docs/ontology/` connects to the code

`docs/ontology/` is the design, written first, in plain English. `core/`
(and the rest) is the implementation of it. The code should always match
the docs — if they disagree, that's a bug to fix, not a detail to shrug off.

| In `docs/ontology/` | Implemented in |
| --- | --- |
| `ENTITIES.md` (the "things" in the game) | `core/models.py` |
| `GAME.md` → Points | `core/scoring.py` |
| `GAME.md` → Territories, Ownership | `core/location.py`, `core/territories.py` |
| `RULES.md` R-R01 (tie rule) | `core/territories.py`'s `replay_leader` |
| `RULES.md` R-T01, R-T02 (territory set, no overlap) | `data/territories.geojson`, read by `data/territory_file.py` and checked by `core/territories.py`'s `parse_territories`; copied into the database by `shared.get_territories()`; overlap checked in `tests/test_territory_data.py` |
| `GAME.md` → Minigames | `core/minigames.py` |
| `SCREENS.md` | `pages/*.py` |
| `OPEN_DECISIONS.md` items not yet decided (like D-01) | A placeholder that does nothing yet, e.g. `core/scoring.py`'s `apply_owner_modifier` — already wired in, waiting for the real rule |

**The rule going forward:** whenever the team decides something that was
open, or changes a rule, update the `docs/ontology/` file *and* the
matching `core/` file in the same change — never just one.

## Building blocks — four pieces to split

Each block is a vertical slice: its `core/` rule files, their tests, and
the one page that uses them. One person can own a block end-to-end and
explain all of it.

| Block | Owns these files | In plain words |
| --- | --- | --- |
| **A. Identity & Lobbies** | `core/auth.py`, `core/lobbies.py`, `core/game_window.py`, `pages/1_Profile.py`, `pages/2_Lobby.py` | Accounts, logging in, creating/joining lobbies, and the Thursday-to-Sunday time window. |
| **B. Location & Territories** | `core/location.py`, `core/territories.py` (picks up `pages/5_Map.py` later) | The hardest, most technical block: matching GPS to a territory, and working out who owns each one. |
| **C. Drink Entries & Scoring** | `core/scoring.py`, `core/checkins.py`, `pages/3_Check_in.py` | The biggest rulebook: how many points a drink is worth, and all the reasons a check-in can be accepted or rejected. |
| **D. Standings & Data layer** | `core/leaderboard.py`, `data/db.py`, `schema.sql`, the real Supabase project, `pages/4_Standings.py` | The season ranking, the one file that talks to the database, and actually setting up the live database. |

**Not assigned yet, on purpose:** `core/minigames.py` and the
Map/Memories/Minigame pages — these come after the four blocks above are
working together.

Everyone should still read `core/models.py` first, since it's the short
file that defines the "things" every other block works with.

## How decisions get made without blocking everyone

Full team approval for every small decision isn't realistic when working
individually. The default is to decide and announce, not decide and ask:

1. Decide it.
2. Build it.
3. Write it into `docs/ontology/`.
4. Post one line in the group chat — a notice, not a request for
   permission: "Decided: invite codes are 6 characters. See `RULES.md`."
5. Open your PR as normal.

**Ask the team first, only when your change does one of these three
things** — otherwise just announce it:
- Changes a field or type on something shared (`Player`, `LobbyMembership`,
  `Season`, `Territory`, etc.)
- Changes the behavior of a function another block already calls
  (`is_in_game_window`, `replay_leader`, `evaluate_location`, etc.)
- Contradicts something already written as *decided* (not just open) in
  the ontology

Your pull request is the real safety net: a teammate sees the code change
and the ontology change together before it reaches the shared `main`
everyone builds on. A short daily or twice-daily check-in call — "here's
what I decided and built since last time" — catches anything that slips
through the one-liners.

## Before starting a new session

A quick checklist before you open Claude Code to work on your block:

- [ ] Pull the latest `main` (or ask Claude Code to do it).
- [ ] Check the group chat for any "Decided: ..." messages since you last
      worked, so you're not building on a stale picture.
- [ ] Create a new branch for today's task, or switch to your existing one
      and make sure it's up to date with `main`.
- [ ] Know the one small task you're tackling this session — not "my
      whole block at once."
- [ ] If you want to see your change actually running against a real
      database (not just passing tests), confirm `.streamlit/secrets.toml`
      exists with real Supabase credentials. If the Supabase project
      hasn't been set up yet, that's Block D's job — check with them first.

## How to do this with Claude Code — no coding needed

If you can't read code, your job is reading Claude's plain-English answers
and checking the real app in the browser — never the code itself. Say
these things to Claude Code, in order, for whatever piece you're working
on (this example uses Identity & Lobbies, but swap the file names for your
own block from the table above):

1. **Setup, once:** "Pull the latest main, then create a new branch for me
   called `identity-lobbies-work`."
2. **Understand the design:** "I want to work on Identity & Lobbies. Read
   `docs/ontology` and tell me in plain English what's already decided for
   this area, and what's still an open question."
3. **Understand what's built:** "Now read the existing code for this —
   [the files for your block] — and explain in plain English what already
   works and what's missing."
4. **Say the rule you want, in plain English, no code:** e.g. "I want
   players to be able to leave a lobby they joined by mistake." If Claude
   says this touches something the team hasn't decided, stop and decide it
   together first, then say "update the ontology to say X" before
   continuing.
5. **Let it build and test:** "Please write this, including a test for it,
   run the full test suite, and tell me in plain English whether
   everything passes."
6. **See it actually work:** "Start the app and let me click through this
   in the browser so I can see it myself." A passing test is not the same
   as a working feature — check it on screen.
7. **Keep the docs honest:** "Now update `docs/ontology` to match what we
   just built, so the rest of the team has the same picture."
8. **Save and share it:** "Commit this with a clear message, push the
   branch, and open a pull request explaining what changed and why."
9. **Get it reviewed:** ask a teammate to look at the pull request before
   it's merged into main.

Repeat from step 4 for the next small piece of your block.

# Page performance and visual cleanup

18 November 2026. This change reduces repeated work while keeping fresh account
and membership checks. It adds no dependencies, saved fields or migrations.

## What changed

- `shared.require_login` handles generic navigation before the old page's
  network reads. A switch still uses native `st.switch_page`; the destination
  validates the account before rendering private content.
- `data.db.membership_context` checks the selected membership, player, lobby
  and season in one joined query. Previously this required two requests.
- Profile reuses the account loaded by its login check. Check-in and Minigames
  reuse the season loaded by their membership check. These values are replaced
  on each full page run, rather than shared or retained using a timed cache.
- Map and Leaderboard replay the season once and reuse its ownership and score
  snapshot. Previously Map replayed twice per territory, and Leaderboard once
  more for season totals. With 24 territories this is 48/49 replays versus one.
  Legacy standings continue using the existing legacy helpers.
- Shared CSS keeps the navy/cream palette and wordmark, with plain heading
  typography, lighter borders and shadows, consistent top spacing, less boxed
  context, and hidden decorative header art/step badges. Minigames has its own
  header label. Native controls and their labels remain in place.

## Measurement

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_page_performance.py
# Optional: requires the existing local Supabase secrets; reads only.
.\.venv\Scripts\python.exe scripts/benchmark_page_performance.py --database
```

The comparison asserts identical outputs before reporting timings. The initial
local sample measured 182.8 ms versus 4.1 ms for 1,000 synthetic entries across
24 territories. Three warm live-Supabase samples of the shared page checks had
medians of 347 ms versus 156 ms (three requests versus two). Network conditions
and season size change these numbers. They are operation timings, not deployed
end-to-end tab-switch benchmarks.

Streamlit still runs the destination page on the server and reads its data.
Browser/server/database latency and a cold hosting process can still delay a
page. Check actual switches on the deployed URL after merging this branch;
these local measurements do not establish the deployed app's total latency.

## Verification and walkthrough

`python -m pytest -q`: 524 tests passed, including fresh credential validation,
rejected membership/season access, avoiding the outgoing page read on navigation,
one replay per map/ranking render, and the existing scoring/team/duel cases.
The existing Streamlit/NumPy timedelta deprecation warnings remain.

Browser QA uses synthetic accounts/data, with the real page renderers at 390 px
and 1280 px. Check Lobby, Check-in and Leaderboard for readable text, no horizontal
overflow, visible navigation and working drink/size controls. The existing Chug
Duel browser suite checks full-viewport Ready/countdown/GO/result behavior and
repeated QA games. No saved data is changed by this optimization; restarting the
app discards the reused render context and performs fresh checks again.

Deployment uses the normal branch/PR/team-review workflow. No new Supabase SQL
is required for this performance change; existing minigame migrations are a
separate prerequisite.

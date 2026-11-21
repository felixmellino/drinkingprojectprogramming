# Verification: what we prove and how to repeat it

The grading criterion asks for accepted actions, rejected actions and edge cases,
with passing tests on `main`. A useful example is one check-in: a valid submission
scores, missing location scores nothing, and retrying a successful submission
must not award points twice. More tests alone do not prove the deployed app works.

## Repeat the automatic checks

From the repository root, use Python 3.12 or 3.14 and Node.js 24 (includes npm).
Use a short checkout/environment path on Windows to avoid its path-length limit:

```bash
python -m pip install -r requirements-verification.txt
npm ci --ignore-scripts
python scripts/verify.py
```

`package-lock.json` fixes the development-only PGlite and Playwright dependencies.
PGlite is an
embedded PostgreSQL engine that executes the real SQL in disposable local
databases. It is not installed in the deployed Python application. The SQL
suites use synthetic players and controlled clocks, never the shared Supabase
database. Supabase Storage tables are stubbed; this does not test the hosted
storage service or its configuration.

Individual groups use the same runner as GitHub Actions:

```bash
python scripts/verify.py --group python
python scripts/verify.py --group components
python scripts/verify.py --group database
python scripts/verify.py --group mutations
python scripts/verify.py --group python --coverage
```

The runner returns a nonzero exit code if any check fails or a dependency is
missing. It continues through the selected checks to show all failures and saves
names, results, durations, the commit hash and whether the working tree has
uncommitted changes to `.venv/verification.json`. This hash identifies the
base commit; local uncommitted edits are also tested. Without Git, the commit
and working-tree fields are null. Provenance is captured before checks start.
The individual assertions and failure tracebacks appear in the terminal/CI log.

## What each layer proves

| Layer | Accepted actions | Rejected actions | Boundaries and recovery |
| --- | --- | --- | --- |
| Python rules and Streamlit forms | Accounts, lobbies, drink selections, standings, team and game flows | Invalid input, unauthorized membership, unavailable services | Timezones, scoring windows, cooldowns, corrections, safe retries |
| Camera/location/reaction JavaScript | Capture, opted-in GPS and reaction taps in a simulated browser | Denied permissions, invalid/early input | Camera cleanup, remembered location choice, reload and missed taps |
| Complete migration chain | Installs every documented fresh-database step | Both `anon` and `authenticated` roles cannot read private tables or execute protected game mutations | Missing migration documentation, missing tables/functions and final access grants |
| Scoring PostgreSQL | Fixed awards, ownership/income, corrections | Wrong member, invalid selection, closed window | Duplicate recovery, exact cutoffs, replay parity and database reopen |
| Chug/Quiz/Time/Reaction PostgreSQL | Invitations, accepted games, results and rewards/stakes | Unauthorized actions, insufficient funds, invalid phases and limits | Retries, expiry, ties and game-specific restart/ledger checks |
| Historical Focus PostgreSQL | Preserved old attempts and current reward combinations | Invalid/stale actions and access | All eight pass/fail combinations, exact boosts, expiry and database reopen |
| Independent scoring oracle | 24 seeded individual/team histories, 2,400 events | Invalid historical entries cannot award points | Conservation, exact fractions, absent owners, stable ordering, outside entries and photo deletion |
| Targeted mutation checks | Clean baseline must pass first | Five deliberately incorrect rule variants must fail assertions | GPS 50 m, tied territory, owner income, weekly close and correction deadline |
| Native PostgreSQL connections | Concurrent check-ins, corrections and duel settlement | Cooldown bypass, double reservations and access revoked while waiting | Transaction rollback, idempotent retries and actual container restart |
| Two browser sessions | Invite, answer, result, one stake transfer | Previously submitted answer stays locked | Mid-round reload, mobile/desktop layout, no uncaught JS errors; screenshots and trace |

See the assertions in `tests/*_postgres.cjs` and the named Python tests for
the precise cases. These checks reuse the existing suites; a green component
test is not a real camera/GPS permission test.

## GitHub evidence

`.github/workflows/tests.yml` runs five jobs on pull requests and `main`:
Python 3.12 and 3.14 with branch coverage, targeted mutations and dependency audits;
JavaScript/PGlite; native PostgreSQL transactions; and a two-player Chromium game.
Each uploads its own verification report for 14 days, including when a
test fails. The job must actually run: a missing report after setup failure is
not a pass. The security audit result is in the Python job log, not the JSON.
Before submission, open the run for the final `main` commit and confirm all
jobs passed. A local or branch run alone does not establish a pass on `main`.

Coverage JSON/HTML and JUnit results are in each Python artifact. Coverage shows
which branches were exercised; it does not prove the assertions are correct or
that every input was tested. We report actual coverage rather than claiming an
arbitrary percentage guarantees the grading outcome. Five targeted mutation
checks demonstrate sensitivity to those five faults only, not every possible bug.
`.coveragerc` measures all application Python, including pages and UI modules,
and excludes tests, verification scripts and development dependencies. It does
not inflate the result by counting executed test code as product coverage.

## What a critical examiner can try

| Attempt | Expected outcome | Automated evidence |
| --- | --- | --- |
| Eight simultaneous retries of the same capture | One entry and one owner-income award | `test_eight_simultaneous_retries_award_one_entry_and_one_owner_income` |
| Eight different captures for one member at the same moment | One accepted; seven cooldown rejections | `test_competing_distinct_captures_cannot_bypass_cooldown` |
| Two equal check-ins arriving together | Stable database order, one owner, matching Python replay | `test_simultaneous_equal_scores_have_one_order_and_python_sql_parity` |
| Two editors submitting revision zero | One revision wins; the other conflicts | `test_two_corrections_with_same_revision_cannot_overwrite_each_other` |
| A failure after inserting an entry | Whole transaction rolls back; retry remains possible | `test_injected_failure_rolls_back_entry_and_replay_then_retry_succeeds` |
| Two duels reserve one person's points | Only one acceptance; no negative available balance | `test_two_acceptances_cannot_reserve_the_same_players_points_twice` |
| Several final taps arrive together | Exactly one ledger transfer | `test_repeated_simultaneous_final_taps_create_one_stake_transfer` |
| Leave while an old request waits for the lobby lock | Waiting submission rechecks membership and is rejected | `test_membership_is_rechecked_after_waiting_for_lobby_lock` |
| Restart the database server | Entries, frozen rules and invitation survive; retry awards once | `test_real_server_restart_preserves_entries_rules_invites_and_retry_identity` |

These native tests are in `tests/postgres_transactions.py`, explicitly selected
so the ordinary Python suite does not silently skip optional integration tests.
GitHub provisions a digest-pinned, disposable PostgreSQL service. To repeat locally,
start the same service using Docker, with user `verification`, database
`wegopub_verification` and the test-only password `verification-only`, then set
`VERIFICATION_DATABASE_URL` to its localhost URL and `VERIFICATION_CONTAINER_ID`
to that container's ID. Run `python scripts/verify.py --group postgres`.
The harness rejects other hosts/users/base databases, creates uniquely named
fixture databases, and removes only the fixture databases it created. It restarts
the specified disposable container for the final persistence check.

For the browser group install Chromium once with
`npx playwright install --with-deps chromium`, then run
`python scripts/verify.py --group browser`. It starts its own localhost Streamlit
fixture and embedded PostgreSQL. It uses synthetic identities and does not test
production login or hosted Supabase. Browser failures save screenshots, a trace
and server logs under `.venv/quiz-browser-qa` for diagnosis.

## Remaining release checks: two phones and the public URL

These are manual checks, not claims that this change has completed them.
Use designated test accounts/lobbies and record the deployed commit, date,
devices, expected outcome and observed result. Exact time boundaries belong
in the controlled-clock automated tests; use real phones for the integration.

- [ ] iPhone Safari and Android Chrome: camera/location consent, denial and recovery.
- [ ] Valid inside/outside check-ins: compare entry, season total, territory total,
      owner income and map; rejected actions must leave points unchanged.
- [ ] Lost reply/reload: recover the same entry; no duplicate points or image record.
- [ ] Two accounts: invite, accept and finish every shipped game; verify both
      histories, standings, cancellation, expiry and normal versus QA limits.
- [ ] Restart: saved identity/lobby selection, photo and ongoing game remain correct.
- [ ] Access: outsider, departed member and revoked session cannot view protected
      content or change scores; photo consent/deletion behaves as documented.
- [ ] Repeat a small two-device concurrency check on the deployed test lobby.
      Native PostgreSQL races cover the isolated SQL transactions; this release
      check adds the deployed server, browser and network path.
- [ ] Record failures as issues, fix them, and repeat the affected checks before
      signing off the final deployed version.

Real Supabase Storage, email delivery, browser permission behaviour, network
loss and deployed performance remain integration checks. A passing automated
suite does not replace these checks or the required live demo.

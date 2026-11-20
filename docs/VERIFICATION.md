# Verification: what we prove and how to repeat it

The grading criterion asks for accepted actions, rejected actions and edge cases,
with passing tests on `main`. A useful example is one check-in: a valid submission
scores, missing location scores nothing, and retrying a successful submission
must not award points twice. More tests alone do not prove the deployed app works.

## Repeat the automatic checks

From the repository root, use Python 3.12 with `requirements.txt` installed
as described in README, plus Node.js 24 (which includes npm):

```bash
npm ci --ignore-scripts
python scripts/verify.py
```

`package-lock.json` fixes the development-only PGlite dependency. It is an
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
```

The runner returns a nonzero exit code if any check fails or a dependency is
missing. It continues through the selected checks to show all failures and saves
names, results, durations, the commit hash and whether the working tree has
uncommitted changes to `.venv/verification.json`. This hash identifies the
base commit; local uncommitted edits are also tested. Without Git, the commit
and working-tree fields are null.
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

See the assertions in `tests/*_postgres.cjs` and the named Python tests for
the precise cases. These checks reuse the existing suites; a green component
test is not a real camera/GPS permission test.

## GitHub evidence

`.github/workflows/tests.yml` has two independent jobs on pull requests and
`main`: Python plus dependency audit, and JavaScript plus database tests.
Each uploads its own verification JSON report for 14 days, including when a
test fails. The job must actually run: a missing report after setup failure is
not a pass. The security audit result is in the Python job log, not the JSON.
Before submission, open the run for the final `main` commit and confirm both
jobs passed. A local or branch run alone does not establish a pass on `main`.

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
- [ ] Two genuinely concurrent database connections/sessions: race duplicate
      submissions and competing game actions. PGlite suites run statements
      sequentially and do not prove multi-connection race safety.
- [ ] Record failures as issues, fix them, and repeat the affected checks before
      signing off the final deployed version.

Real Supabase Storage, email delivery, browser permission behaviour, network
loss and deployed performance remain integration checks. A passing automated
suite does not replace these checks or the required live demo.

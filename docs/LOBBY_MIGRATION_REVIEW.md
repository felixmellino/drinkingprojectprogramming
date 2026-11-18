# Recovered lobby-battles migration: review only

`migrations/007_lobby_battles.sql` restores the original local
`006_lobby_battles.sql` from GitHub Desktop's `Lobbiecreation` stash
(commit `abb1979`). Only its filename and opening comments changed.
The stash is retained; it has not been applied to the current checkout.

Merge the Friends rename (`005_friendships.sql` → `006_friendships.sql`)
first. Keep `005_scoring_v1.sql` unchanged: the team reports it is already
applied to the shared project. Renaming Friends does not mean an installed
Friends migration should be run again.

## Do not apply to the shared database yet

This is publication of the original SQL for teammate review, not approval
to deploy the lobby-battles feature or a claim of scoring-v1 compatibility.

- The recovered `guard_battle_entry` trigger enforces Thursday noon through
  Sunday in Lisbon. Current scoring v1 uses Thursday 18:00 to Sunday 18:00
  in the season timezone. Resolve this conflict against the current ontology
  before applying; do not silently replace the agreed scoring contract.
- The SQL adds `lobby_memberships.is_active`, `lobby_states`, a save RPC and
  a drink-entry trigger. Its companion lobby-state code is still in the
  local stash and is not part of this SQL-only PR. Current main does not
  create a lobby-state row when creating a lobby; the recovered trigger
  would therefore reject check-ins for newly created lobbies.
- Review season creation and the JSON aggregate against the frozen scoring
  fields and transactions introduced by scoring v1. The recovered RPC was
  written before those changes and inserts only the older season columns.
- The migration is once-only. It seeds existing lobbies and aborts if any
  legacy lobby has more than ten members. Review ownership seeding and
  membership history with the team, and back up before any future run.
- The stash also contains a separate `007_lobby_timezones.sql` follow-up.
  It is not included here and must get a new, unused number before release.

Validation for this recovery: executable SQL matches the stashed original;
only comments differ. No SQL was run against Supabase. After resolving the
integration points, validate on a disposable database with current main's
schema and scoring migration, including accepted/rejected check-ins,
existing/new lobbies, concurrent leave/check-in, season creation and restart
persistence, before scheduling a shared-project migration.

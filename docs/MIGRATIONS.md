# Database migrations: install order

The SQL files in `migrations/` have overlapping numbers (for example two `016`,
three `017`) because teammates wrote them in parallel. **The number alone does not
tell you the order. Use this list.** All files run in the Supabase SQL Editor
(**New query → paste → Run**). The app never applies migrations itself.

## Fresh database

Run these once, top to bottom. Step 1 is the base schema at the repository root; it
already contains the account, remembered-device and friendship changes (old
migrations 001, 002, 003 and 006), so those four are not run again.

1. `schema.sql`
2. `004_server_game_tables.sql`
3. `setup_checkin_photo_storage.sql`
4. `005_scoring_v1.sql`
5. `007_lobby_battles.sql`
6. `008_profile_pictures.sql`
7. `009_single_competition_lobbies.sql`
8. `010_team_lobbies.sql`
9. `011_chug_duel.sql`
10. `012_player_lobby_choices.sql`
11. `012_qa_minigames.sql`
12. `013_checkin_photo_privacy.sql`
13. `014_focus_challenge.sql`
14. `015_focus_test_replays.sql`
15. `016_leave_lobby.sql`
16. `016_quiz_duel.sql`
17. `017_delete_lobby.sql`
18. `017_time_duel.sql`
19. `021_focus_three_stage_flow.sql`
20. `021_time_duel_invitations.sql`
21. `022_focus_complete_all_games.sql`
22. `022_quiz_duel_invite_list.sql`
23. `023_minigame_invite_badge.sql`
24. `024_minigame_tile_badges.sql`
25. `025_reaction_duel.sql`
26. `026_lobby_invitations.sql`
27. `027_territory_boosts.sql`
28. `028_profile_medals.sql`
29. `029_season_recap_views.sql`
30. `030_end_test_season.sql`

`tests/migration_chain.cjs` installs exactly this list on an empty PostgreSQL and
fails if a step breaks or if a migration file is missing from this page.

## Existing database (for example the team's Supabase project)

Run only the files you have not applied yet, in the order of the list above.
Most of them are safe to run twice, but do not rely on it.
**Newest migration:** `030_end_test_season.sql` (creator-only early closure for
test seasons). Check that `select to_regprocedure('public.end_test_season(uuid,uuid,uuid)');`
returns a function signature.

**Before that:** `029_season_recap_views.sql` (who has finished a season recap). The quick check

```sql
select count(*) from public.season_recap_views;
```

returns a number once 029 is installed.

**Before that:** `028_profile_medals.sql`. Apply it when rolling out medal
announcements. It records the cutoff used to suppress historical promotions.
The profile cards use existing season data and can display medals before this step.

```sql
select launched_at from public.profile_medal_rollout;
```

The query returns the saved cutoff. Reapplying 028 preserves that timestamp.
Apply 027 before deploying territory boosts for newly created seasons.

## Files that are not part of a fresh install

| File | Why it is skipped |
| --- | --- |
| `001_personal_accounts.sql`, `002_remembered_devices.sql`, `003_text_territory_ids.sql`, `006_friendships.sql` | Already inside `schema.sql`. Only for databases created before the schema had them. Order for those: 001, 002, 003, 004. |
| `017_focus_reaction_flow.sql`, `018_focus_reaction_only.sql`, `019_focus_false_start_three_tries.sql`, `020_focus_wait_time.sql` | Earlier steps of the solo Reaction Test. `021_focus_three_stage_flow.sql` is self-contained and replaces them. Never run them after 021. |

The solo Reaction Test (Focus Challenge) was replaced on the Games tab by the Reaction
Duel (rule R-M11). Its tables and functions (014, 015, 021, 022) stay in the database
because earlier boosts remain part of the scoring history.

## Writing a new migration

Give it the next free number (`030_…`), start the file with one comment line saying what
it needs ("Requires 029"), and add it to the end of the list above. The chain test fails
until you do.

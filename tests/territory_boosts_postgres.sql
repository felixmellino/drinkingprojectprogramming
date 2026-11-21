-- Disposable migration-chain fixture. Only the existing receipt clocks are substituted.
do $$
declare
  fn regprocedure;
begin
  foreach fn in array array[
    'public.accept_scoring_checkin(uuid,uuid,uuid,uuid,text,text,text,text,text,timestamptz)'::regprocedure,
    'public.correct_scoring_checkin(uuid,uuid,text,text,integer)'::regprocedure,
    'public.active_territory_boost(uuid,uuid)'::regprocedure
  ] loop
    execute replace(pg_get_functiondef(fn), 'statement_timestamp()',
      'current_setting(''wegopub.fixture_receipt'')::timestamptz');
  end loop;
end $$;

create function public.fixture_boost_checkin(player uuid, member uuid, lobby uuid, season uuid,
  capture uuid, receipt text, area text default 'boost-fixture')
returns public.drink_entries language plpgsql as $$
declare saved public.drink_entries%rowtype;
begin
  perform set_config('wegopub.fixture_receipt', receipt, true);
  select * into strict saved from public.accept_territory_scoring_checkin(
    player, capture, member, season, 'shot', null, area,
    case when area is null then 'outside' else 'matched' end,
    lobby || '/' || capture || '.jpg', receipt::timestamptz, array['boost-fixture']);
  return saved;
end $$;

do $$
declare
  mina uuid := gen_random_uuid();
  jon uuid := gen_random_uuid();
  li uuid := gen_random_uuid();
  lobby uuid := gen_random_uuid();
  teams uuid := gen_random_uuid();
  season uuid := gen_random_uuid();
  team_season uuid := gen_random_uuid();
  am uuid := gen_random_uuid();
  bm uuid := gen_random_uuid();
  team1 uuid;
  team2 uuid;
  tm1 uuid := gen_random_uuid();
  tm2 uuid := gen_random_uuid();
  tm3 uuid := gen_random_uuid();
  capture uuid := gen_random_uuid();
  trigger_capture uuid := gen_random_uuid();
  saved public.drink_entries%rowtype;
  rules jsonb := '{"version":"v1","territory_boost":true,"points":{"shot":{"standard":4},"wine":{"small":1}},"start_weekday":3,"start_hour":18,"end_weekday":6,"end_hour":18,"cooldown_seconds":120,"correction_seconds":120}';
begin
  insert into territories(id,name,boundary) values('boost-fixture','Boost fixture','{}');
  insert into players(id,display_name,first_name,last_name,pin_hash,email) values
    (mina,'boost-fixture-a','A','Fixture','fixture-only','boost-a@example.com'),
    (jon,'boost-fixture-b','B','Fixture','fixture-only','boost-b@example.com'),
    (li,'boost-fixture-c','C','Fixture','fixture-only','boost-c@example.com');
  insert into lobbies(id,name,invite_code) values(lobby,'Boost fixture','BOOSTFIX');
  insert into lobbies(id,name,invite_code,game_mode,team_count,team_capacity,team_assignment)
    values(teams,'Boost team fixture','BOOSTTEAM','team',2,3,'manual');
  select id into team1 from lobby_teams where lobby_id=teams and number=1;
  select id into team2 from lobby_teams where lobby_id=teams and number=2;
  insert into lobby_memberships(id,player_id,lobby_id,team_id) values
    (am,mina,lobby,null),(bm,jon,lobby,null),
    (tm1,mina,teams,team1),(tm2,jon,teams,team1),(tm3,li,teams,team2);
  insert into seasons(id,lobby_id,starts_at,ends_at,length_choice,scoring_version,scoring_rules) values
    (season,lobby,'2026-11-19 18:00Z','2026-11-26 18:00Z','1_week','v1',rules),
    (team_season,teams,'2026-11-19 18:00Z','2026-11-26 18:00Z','1_week','v1',rules);

  perform fixture_boost_checkin(mina,am,lobby,season,gen_random_uuid(),'2026-11-19 18:00Z');
  perform fixture_boost_checkin(mina,am,lobby,season,gen_random_uuid(),'2026-11-19 18:03Z');
  perform fixture_boost_checkin(jon,bm,lobby,season,gen_random_uuid(),'2026-11-19 18:06Z',null);
  assert not exists(select 1 from territory_boosts where season_id=season);
  saved := fixture_boost_checkin(jon,bm,lobby,season,trigger_capture,'2026-11-19 18:09Z');
  assert saved.points_awarded = 4 and saved.territory_boost_id is null;
  assert (select territory_id from active_territory_boost(mina,season)) = 'boost-fixture';
  assert (select ends_at from active_territory_boost(jon,season)) = '2026-11-19 18:24Z'::timestamptz;
  assert not exists(select 1 from active_territory_boost(jon,team_season));
  begin
    perform active_territory_boost(li,season);
    raise exception 'nonmember could see the boost';
  exception when raise_exception then
    if sqlerrm <> 'permission_denied' then raise; end if;
  end;
  saved := fixture_boost_checkin(jon,bm,lobby,season,trigger_capture,'2026-11-19 18:10Z');
  assert saved.territory_boost_id is null and (select count(*) from territory_boosts where season_id=season) = 1;
  saved := fixture_boost_checkin(jon,bm,lobby,season,capture,'2026-11-19 18:11Z');
  assert saved.points_awarded = 5 and saved.owner_bonus_quarters = 5
    and saved.owner_membership_id = am and saved.territory_boost_id is not null;
  select * into saved from correct_scoring_checkin(jon,capture,'wine','small',0);
  assert saved.points_awarded = 1.25 and saved.owner_bonus_quarters = 1.25 and saved.territory_boost_id is not null;
  saved := fixture_boost_checkin(mina,am,lobby,season,gen_random_uuid(),'2026-11-19 18:24Z');
  assert saved.points_awarded = 4 and saved.territory_boost_id is null;
  assert not exists(select 1 from active_territory_boost(mina,season));

  perform fixture_boost_checkin(jon,bm,lobby,season,gen_random_uuid(),'2026-11-19 20:20Z');
  perform fixture_boost_checkin(mina,am,lobby,season,gen_random_uuid(),'2026-11-19 20:38:59Z');
  assert (select count(*) from territory_boosts where season_id=season) = 1;
  perform fixture_boost_checkin(jon,bm,lobby,season,gen_random_uuid(),'2026-11-19 20:39Z');
  assert (select count(*) from territory_boosts where season_id=season) = 2;

  perform fixture_boost_checkin(mina,am,lobby,season,gen_random_uuid(),'2026-11-22 17:30Z');
  perform fixture_boost_checkin(jon,bm,lobby,season,gen_random_uuid(),'2026-11-22 17:46Z');
  assert (select count(*) from territory_boosts where season_id=season) = 2;

  perform fixture_boost_checkin(mina,tm1,teams,team_season,gen_random_uuid(),'2026-11-19 18:00Z');
  perform fixture_boost_checkin(jon,tm2,teams,team_season,gen_random_uuid(),'2026-11-19 18:29Z');
  assert not exists(select 1 from territory_boosts where season_id=team_season);
  perform fixture_boost_checkin(li,tm3,teams,team_season,gen_random_uuid(),'2026-11-19 18:59:01Z');
  assert not exists(select 1 from territory_boosts where season_id=team_season);
  saved := fixture_boost_checkin(jon,tm2,teams,team_season,gen_random_uuid(),'2026-11-19 19:01Z');
  assert saved.territory_boost_id is null and (select count(*) from territory_boosts where season_id=team_season) = 1;
end $$;

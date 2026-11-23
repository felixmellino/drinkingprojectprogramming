-- Runs after the territory boost fixture, which supplies a controlled receipt clock.
do $$
declare
  creator uuid := gen_random_uuid();
  other_player uuid := gen_random_uuid();
  focus_player uuid := gen_random_uuid();
  creator_member uuid := gen_random_uuid();
  other_member uuid := gen_random_uuid();
  focus_member uuid := gen_random_uuid();
  regular_member uuid := gen_random_uuid();
  lobby uuid := gen_random_uuid();
  regular_lobby uuid := gen_random_uuid();
  test_season uuid := gen_random_uuid();
  regular_season uuid := gen_random_uuid();
  capture uuid := gen_random_uuid();
  chug uuid := gen_random_uuid();
  quiz uuid := gen_random_uuid();
  timing uuid := gen_random_uuid();
  reaction uuid := gen_random_uuid();
  focus uuid := gen_random_uuid();
  -- Monday in a prior week, outside both standard and QA Chug Duel windows.
  receipt timestamptz := (date_trunc('week', statement_timestamp() at time zone 'UTC')
                          - interval '7 days' + interval '12 hours') at time zone 'UTC';
  planned_end timestamptz := statement_timestamp() + interval '1 day';
  deadline timestamptz := statement_timestamp() + interval '15 minutes';
  cutoff timestamptz;
  rejection record;
  rules jsonb := '{"version":"v1","points":{"shot":{"standard":4},"wine":{"small":1}},
    "start_weekday":3,"start_hour":18,"end_weekday":6,"end_hour":18,"cooldown_seconds":120,"correction_seconds":120}';
begin
  insert into players(id,display_name,first_name,last_name,pin_hash) values
    (creator,'Test season creator','Season','Creator','fixture'),
    (other_player,'Test season member','Season','Member','fixture'),
    (focus_player,'Test season solo player','Solo','Player','fixture');
  insert into lobbies(id,name,invite_code) values
    (lobby,'Test closure fixture','ENDTEST'), (regular_lobby,'Regular closure fixture','ENDREGULAR');
  insert into lobby_memberships(id,player_id,lobby_id,joined_at) values
    (creator_member,creator,lobby,receipt-interval '2 hours'),
    (other_member,other_player,lobby,receipt-interval '1 hour'),
    (focus_member,focus_player,lobby,receipt-interval '1 hour'),
    (regular_member,creator,regular_lobby,receipt-interval '2 hours');
  insert into seasons(id,lobby_id,starts_at,ends_at,length_choice,timezone_name,scoring_version,scoring_rules) values
    (test_season,lobby,receipt-interval '1 hour',planned_end,'1_month','UTC','v1',
      rules || '{"test_mode":true,"start_weekday":2,"start_hour":8}'),
    (regular_season,regular_lobby,receipt-interval '1 hour',planned_end,'1_month','UTC','v1',rules);
  perform fixture_boost_checkin(creator,creator_member,lobby,test_season,capture,receipt::text,null);
  perform fixture_boost_checkin(other_player,other_member,lobby,test_season,gen_random_uuid(),receipt::text,null);

  for rejection in select * from (values
    (regular_member,regular_lobby,regular_season,receipt),
    (creator_member,lobby,test_season,receipt-interval '1 hour 1 second'),
    (creator_member,lobby,test_season,planned_end)
  ) closed(member,lid,sid,at_time) loop
    begin
      perform fixture_boost_checkin(creator,rejection.member,rejection.lid,rejection.sid,
        gen_random_uuid(),rejection.at_time::text,null);
      raise exception 'Check-in was accepted outside its permitted times';
    exception when raise_exception then
      if sqlerrm <> 'scoring_closed' then raise; end if;
    end;
  end loop;
  assert (select count(*) from drink_entries where season_id=test_season and points_awarded=4) = 2;
  assert not exists (select 1 from drink_entries where season_id=regular_season);

  for rejection in select * from (values
    (other_player,lobby,test_season,'permission_denied'),
    (creator,lobby,regular_season,'permission_denied'),
    (creator,regular_lobby,regular_season,'test_season_required')
  ) denied(actor,lid,sid,message) loop
    begin
      perform end_test_season(rejection.actor,rejection.lid,rejection.sid);
      raise exception 'Forbidden closure succeeded';
    exception when raise_exception then
      if sqlerrm <> rejection.message then raise; end if;
    end;
  end loop;
  assert (select ends_at from seasons where id=test_season) = planned_end;

  insert into chug_duels(id,season_id,challenger_id,opponent_id,game_night,drink_type,status,created_at,expires_at)
    values(chug,test_season,creator_member,other_member,current_date,'shot','started',statement_timestamp(),deadline);
  insert into quiz_duels(id,season_id,challenger_id,opponent_id,game_night,stake,status,created_at,expires_at,started_at,deadline,questions)
    values(quiz,test_season,creator_member,other_member,current_date,3,'playing',statement_timestamp(),
           deadline,statement_timestamp(),deadline,'[]');
  insert into time_duels(id,season_id,challenger_id,opponent_id,game_night,status,created_at,expires_at,targets)
    values(timing,test_season,creator_member,other_member,current_date,'accepted',statement_timestamp(),deadline,'[1,2,3]');
  insert into reaction_duels(id,season_id,challenger_id,opponent_id,game_night,stake,status,created_at,expires_at,challenger_account,opponent_account)
    values(reaction,test_season,creator_member,other_member,current_date,3,'accepted',statement_timestamp(),
           deadline,creator_member,other_member);
  insert into reaction_runs(duel_id,membership_id,step,times)
    values(reaction,creator_member,1,array[250]), (reaction,other_member,0,'{}');
  insert into focus_attempts(id,membership_id,season_id,game_night,attempt_number,challenge,started_at,expires_at,deadline)
    values(focus,focus_member,test_season,current_date,1,'{}',statement_timestamp(),deadline,deadline);

  set local role service_role;
  perform end_test_season(creator,lobby,test_season);
  reset role;
  select ends_at into cutoff from seasons where id=test_season and ended_early;
  assert cutoff between statement_timestamp() and clock_timestamp() and cutoff < planned_end;
  assert (select ends_at from seasons where id=regular_season) = planned_end;
  assert (select status from chug_duels where id=chug) = 'aborted';
  assert (select status from quiz_duels where id=quiz) = 'draw';
  assert (select status from time_duels where id=timing) = 'expired';
  assert (select status from focus_attempts where id=focus) = 'failed';
  assert (select winner_id from reaction_duels where id=reaction) = creator_member;
  assert (select points from quiz_transfers where id=reaction) = 3;
  assert (select points_awarded from drink_entries where id=capture) = 4;

  perform end_test_season(creator,lobby,test_season);
  assert (select ends_at from seasons where id=test_season) = cutoff;
  assert (select count(*) from quiz_transfers where season_id=test_season) = 1;

  -- A request stamped before the cutoff can arrive at the write after closure.
  begin
    perform fixture_boost_checkin(creator,creator_member,lobby,test_season,gen_random_uuid(),
      (receipt+interval '3 minutes')::text,null);
    raise exception 'Closed season accepted a check-in';
  exception when raise_exception then
    if sqlerrm <> 'scoring_closed' then raise; end if;
  end;
  perform set_config('wegopub.fixture_receipt', (receipt+interval '30 seconds')::text, true);
  begin
    perform correct_scoring_checkin(creator,capture,'wine','small',0);
    raise exception 'Closed season accepted a correction';
  exception when raise_exception then
    if sqlerrm <> 'correction_closed' then raise; end if;
  end;
  assert (select points_awarded from drink_entries where id=capture) = 4;
end $$;

// Portable real-PostgreSQL Time Duel smoke test; synthetic data, never Supabase.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {fixture,uid}=require('./quiz_fixture.cjs');
(async()=>{
 const f=await fixture({modulePath:process.argv[2],disk:path.resolve('.venv','time-sql-'+Date.now())});
 try{
  for(const file of ['012_player_lobby_choices.sql','015_focus_test_replays.sql','016_leave_lobby.sql',
   '017_time_duel.sql','021_time_duel_invitations.sql','022_quiz_duel_invite_list.sql',
   '023_minigame_invite_badge.sql','024_minigame_tile_badges.sql','025_reaction_duel.sql'])
   await f.exec(fs.readFileSync('migrations/'+file,'utf8').replaceAll('statement_timestamp()','(select at_time from test_clock)'));
  const l=await f.lobby(1,{test:true});
  const status=async p=>(await f.rpc('select time_status($1,$2) data',[uid(p),l.sid])).rows[0].data;
  const invite=async id=>(await f.rpc('select invite_time_duel($1,$2,$3,$4) data',[uid(1),l.sid,uid(id),l.mid(2)])).rows[0].data;
  const act=async(p,d,action,elapsed=null)=>(await f.rpc('select time_action($1,$2,$3,$4,$5) data',
   [uid(p),d.id,action,d.round_no,elapsed])).rows[0].data;
  await assert.rejects(status(7),/permission_denied/);
  let d=await invite(8000);
  assert.equal((await invite(8000)).id,d.id,'A lost invite reply does not create another duel');
  assert.equal((await status(2)).duels[0].id,d.id);
  await assert.rejects(act(3,d,'accept'),/permission_denied/);
  d=await act(2,d,'accept');
  await f.reopen();
  assert.equal((await status(1)).duels[0].status,'accepted','Accepted game survives restart');
  for(let round=0;round<3;round++){
   d=await act(1,d,'ready'); d=await act(2,d,'ready');
   const target=d.target_ms;
   assert(target>=5000 && target<=12000);
   await act(1,d,'start');await act(2,d,'start');await f.advance(15000);
   await act(1,d,'stop',target); d=await act(2,d,'stop',target+400);
  }
  assert.equal(d.status,'completed');assert.equal(d.winner_id,l.mid(1));
  const until=(await status(1)).boost_ends_at;
  assert(until);assert.equal((await status(2)).boost_ends_at,null);
  assert.equal((await act(2,d,'stop',8000)).status,'completed','Repeated final action stays idempotent');
  const drink=await l.add(1,9000,'shot',null,'quiz-fixture');
  assert.equal(Number(drink.points_awarded),4);assert.equal(Number(drink.time_bonus),1);
  assert.equal(drink.time_duel_id,d.id);
  await f.advance(120000);
  const normal=await l.add(2,9001,'beer','small','quiz-fixture');
  assert.equal(Number(normal.time_bonus),0);assert.equal(Number(normal.owner_bonus_quarters),1);
  await f.reopen();assert.equal((await status(1)).boost_ends_at,until,'Saved boost survives restart');
  await f.clock(until);
  assert.equal((await status(1)).boost_ends_at,null,'Boost ends at the exact boundary');
  const expired=await l.add(1,9002,'beer','small','quiz-fixture');
  assert.equal(Number(expired.time_bonus),0);
  await f.q('set role anon');
  await assert.rejects(f.q('select time_status($1,$2)',[uid(1),l.sid]),/permission denied/);
  await f.q('reset role');
  console.log('Time Duel PostgreSQL passed: permission denial, invitations, retries, three rounds, boost, owner income, expiry and restart.');
 }finally{await f.close();}
})().catch(error=>{console.error(error);process.exit(1);});

// Migration 022, real isolated PostgreSQL: every result combination and saved rewards.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {fixture,uid}=require('./quiz_fixture.cjs');
(async()=>{
 let f;
 try{
  f=await fixture({modulePath:'.venv/photo-sql-check/package/dist/index.cjs',disk:path.resolve('.venv','focus-complete-'+Date.now())});
  const install=async file=>f.exec(fs.readFileSync('migrations/'+file,'utf8').replaceAll('statement_timestamp()','(select at_time from test_clock)'));
  await install('012_player_lobby_choices.sql');
  await install('015_focus_test_replays.sql');await install('016_leave_lobby.sql');
  await install('017_time_duel.sql');await install('021_time_duel_invitations.sql');
  await install('021_focus_three_stage_flow.sql');
  const status=async(p,l)=>(await f.rpc('select focus_status($1,$2) data',[uid(p),l.sid])).rows[0].data;
  const start=async(p,l,id)=>(await f.rpc('select start_focus_attempt($1,$2,$3) data',[uid(p),l.sid,uid(id)])).rows[0].data;
  const act=async(p,a,action,evidence={})=>(await f.rpc('select focus_attempt_action($1,$2,$3,$4,$5) data',[uid(p),a.id,a.revision,action,evidence])).rows[0].data;
  const l=await f.lobby(1,{test:true});
  let legacy=await start(1,l,8000);assert.equal(legacy.config.flow_version,2);
  await install('022_focus_complete_all_games.sql');
  assert.equal((await status(1,l)).attempt.config.flow_version,2,'Do not rewrite a running attempt');
  legacy=await act(1,legacy,'fail');assert.equal(legacy.status,'failed');
  await install('022_focus_complete_all_games.sql');
  for(let mask=0;mask<8;mask++){
   let a=await start(1,l,8100+mask);
   assert.equal(a.config.flow_version,3);assert.deepEqual(a.stage_results,{});
   await assert.rejects(act(7,a,'fail'),/permission_denied/);
   await assert.rejects(act(1,a,'precision',{taps:[1]}),/focus_invalid_action/);
   a=await act(1,a,'ready');
   await f.clock(new Date(Date.parse(a.signal_at)+(mask&1?220:221)).toISOString());
   const old=a;
   a=await act(1,a,'reaction',{elapsed_ms:mask&1?220:221});
   assert.equal(a.phase,'memory_ready');assert.equal(a.status,'running');
   assert.equal(a.stage_results.reaction,!!(mask&1));assert.equal(a.boost_ends_at,null);
   assert.equal((await act(1,old,'fail')).phase,'memory_ready','Stale failure cannot fail the next task');
   if(mask===2){await f.reopen();assert.deepEqual((await status(1,l)).attempt.stage_results,{reaction:false});}
   a=await act(1,a,'ready');const memory=[...a.memory];await f.clock(a.signal_at);
   if(mask&2){for(const cell of memory)a=await act(1,a,'memory',{cell});}
   else a=await act(1,a,'memory',{cell:(memory[0]+1)%9});
   assert.equal(a.phase,'precision_ready');assert.equal(a.status,'running');
   assert.equal(a.stage_results.memory,!!(mask&2));assert.equal(a.boost_ends_at,null);
   a=await act(1,a,'ready');await f.advance(4000);
   if(mask&4)a=await act(1,a,'precision',{taps:Array.from({length:12},(_,i)=>(i+1)*300)});
   else a=await act(1,a,'fail');
   const wins=[1,2,4].filter(bit=>mask&bit).length,multiplier=wins===3?1.5:wins===2?1.25:1;
   assert.equal(a.status,wins>=2?'passed':'failed');assert.equal(Number(a.boost_multiplier),multiplier);
   assert.deepEqual(a.stage_results,{reaction:!!(mask&1),memory:!!(mask&2),precision:!!(mask&4)});
   assert.equal(a.boost_ends_at!==null,wins>=2);
   assert.deepEqual((await act(1,a,'fail')).stage_results,a.stage_results,'Final result is immutable on retries');
  }
  // A weaker later QA reward must not replace the still-active full reward.
  let weaker=await act(1,await start(1,l,8200),'fail');
  weaker=await act(1,weaker,'ready');let weakSequence=[...weaker.memory];await f.clock(weaker.signal_at);
  for(const cell of weakSequence)weaker=await act(1,weaker,'memory',{cell});
  weaker=await act(1,weaker,'ready');await f.advance(4000);
  weaker=await act(1,weaker,'precision',{taps:Array.from({length:12},(_,i)=>(i+1)*300)});
  assert.equal(Number(weaker.boost_multiplier),1.25);
  assert.equal(Number((await status(1,l)).boost_multiplier),1.5);
  assert.equal(Number((await l.add(1,8201,'beer','small')).points_awarded),1.5);
  const reward=await f.lobby(2,{test:true});
  await reward.add(2,8300,'mixed','large','quiz-fixture');
  let a=await start(1,reward,8301);a=await act(1,a,'fail'); // missed reaction, still play both others
  a=await act(1,a,'ready');const memory=[...a.memory];await f.clock(a.signal_at);
  for(const cell of memory)a=await act(1,a,'memory',{cell});
  a=await act(1,a,'ready');await f.advance(4000);
  a=await act(1,a,'precision',{taps:Array.from({length:12},(_,i)=>(i+1)*300)});
  assert.equal(Number((await status(1,reward)).boost_multiplier),1.25);
  const drink=await reward.add(1,8302,'beer','small','quiz-fixture');
  assert.equal(Number(drink.points_awarded),1.25);assert.equal(Number(drink.focus_multiplier),1.25);
  assert.equal(Number(drink.owner_bonus_quarters)/4,0.3125,'Owner income preserves sixteenth-points');
  const corrected=(await f.rpc('select * from correct_scoring_checkin($1,$2,$3,$4,$5)',[uid(1),drink.id,'beer','large',0])).rows[0];
  assert.equal(Number(corrected.points_awarded),3.75);assert.equal(Number(corrected.owner_bonus_quarters)/4,0.9375);
  await assert.rejects(f.q('update drink_entries set focus_multiplier=1.5 where id=$1',[drink.id]),/entry_identity_frozen/);
  await f.clock(a.boost_ends_at);await f.advance(120000);
  const unboosted=await reward.add(1,8303,'beer','small');assert.equal(Number(unboosted.points_awarded),1);
  await f.q('select _replay_scoring_season($1)',[reward.sid]);
  assert.equal(Number((await f.q('select points_awarded from drink_entries where id=$1',[drink.id])).rows[0].points_awarded),3.75);
  // Timers fail only their task. A refresh or old queued message cannot skip another.
  a=await act(1,await start(1,reward,8400),'ready');await f.clock(new Date(Date.parse(a.deadline)+2001).toISOString());
  let resumed=(await status(1,reward)).attempt;assert.equal(resumed.phase,'memory_ready');assert.equal(resumed.stage_results.reaction,false);
  assert.equal((await act(1,a,'fail')).phase,'memory_ready');
  resumed=await act(1,resumed,'ready');await f.clock(new Date(Date.parse(resumed.deadline)+2001).toISOString());
  resumed=(await status(1,reward)).attempt;assert.equal(resumed.phase,'precision_ready');assert.equal(resumed.stage_results.memory,false);
  resumed=await act(1,resumed,'ready');await f.clock(new Date(Date.parse(resumed.deadline)+2001).toISOString());
  resumed=(await status(1,reward)).attempt;assert.equal(resumed.status,'failed');assert.equal(Number(resumed.boost_multiplier),1);
  // An early reaction also advances. Whole-attempt expiry cannot issue an incomplete reward.
  a=await act(1,await start(1,reward,8401),'ready');a=await act(1,a,'fail');assert.equal(a.phase,'memory_ready');
  await f.clock(a.expires_at);assert.equal((await status(1,reward)).attempt.status,'failed');
  // Both entry points and internal reward mutation stay inaccessible to browser roles.
  for(const role of ['anon','authenticated']){
   await f.q('set role '+role);
   await assert.rejects(f.q('select _focus_finish_stage($1,true,null,now())',[a.id]),/permission denied/);
   await assert.rejects(f.q('select focus_attempt_action($1,$2,0,$3,$4)',[uid(1),a.id,'ready',{}]),/permission denied/);
   await f.q('reset role');
  }
  const saved=(await status(1,reward)).attempt;
  await install('022_focus_complete_all_games.sql');await f.reopen();
  assert.deepEqual((await status(1,reward)).attempt.stage_results,saved.stage_results);
  const normal=await f.lobby(3);
  await assert.rejects(start(1,normal,8500),/focus_locked/);
  for(let i=0;i<5;i++){await f.advance(120000);await normal.add(1,8510+i);}
  let n=await start(1,normal,8500);
  for(let i=0;i<3;i++)n=await act(1,n,'fail');
  assert.equal((await status(1,normal)).threshold,7);
  await assert.rejects(start(1,normal,8501),/focus_locked/);
  for(let i=0;i<2;i++){await f.advance(120000);await normal.add(1,8520+i);}
  n=await act(1,await start(1,normal,8501),'ready');
  await f.clock(new Date(Date.parse(n.signal_at)+220).toISOString());
  n=await act(1,n,'reaction',{elapsed_ms:220});n=await act(1,n,'ready');
  const sequence=[...n.memory];await f.clock(n.signal_at);
  for(const cell of sequence)n=await act(1,n,'memory',{cell});
  n=await act(1,n,'fail');assert.equal(Number(n.boost_multiplier),1.25);
  await assert.rejects(start(1,normal,8502),/focus_won/,'A partial reward consumes the normal nightly win');
  // Departed members cannot read status or submit task evidence.
  await f.q('select leave_lobby($1,$2)',[uid(1),normal.lid]);
  await assert.rejects(status(1,normal),/permission_denied/);
  await assert.rejects(act(1,n,'ready'),/permission_denied/);
  console.log('PASS: all 8 outcome combinations, all-stage continuation, permissions, stale/retried actions, restart, timeouts, exact x1.25 scoring/owner income/corrections/expiry and repeat migration.');
 }finally{if(f)await f.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

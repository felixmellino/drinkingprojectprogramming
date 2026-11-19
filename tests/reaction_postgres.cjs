// Reaction Duel on real PostgreSQL (PGlite): stakes, three tries each, best of three, ledger.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{fixture,uid}=require('./quiz_fixture.cjs');
(async()=>{
 const f=await fixture({modulePath:process.argv[2],disk:path.resolve('.venv','reaction-sql-'+Date.now())});
 const {q,rpc,clock,advance,lobby}=f;
 const load=async file=>f.exec(fs.readFileSync('migrations/'+file,'utf8').replaceAll('statement_timestamp()','(select at_time from test_clock)'));
 for(const file of ['016_leave_lobby.sql','017_delete_lobby.sql','017_time_duel.sql'])await load(file);await load('025_reaction_duel.sql');await load('025_reaction_duel.sql');  // safe to run twice
 const status=async(p,sid)=>(await rpc('select reaction_status($1,$2) data',[uid(p),sid])).rows[0].data;
 const invite=async(p,l,id,opponent=2,stake=3)=>(await rpc('select invite_reaction_duel($1,$2,$3,$4,$5) data',[uid(p),l.sid,uid(id),l.mid(opponent),stake])).rows[0].data;
 const act=async(p,id,action,revision=null,ms=null)=>(await rpc('select reaction_action($1,$2,$3,$4,$5) data',[uid(p),uid(id),action,revision,ms])).rows[0].data;
 const points=async(p,sid)=>Number((await status(p,sid)).available_points);
 const ledger=async()=>Number((await q('select count(*) n from quiz_transfers')).rows[0].n);
 // Plays one try: wait for this player's signal, then tap after `ms` (or miss).
 async function tap(p,id,ms){
  let d=await act(p,id,'ready',(await run(p,id)).revision);  // no-op once a signal is scheduled
  const r=d.run;await clock(r.signal_at);await advance(ms==='miss'?2100:ms);
  return act(p,id,ms==='miss'?'miss':'reaction',r.revision,ms==='miss'?null:ms);
 }
 const run=async(p,id)=>(await status(p,(await q('select season_id from reaction_duels where id=$1',[uid(id)])).rows[0].season_id)).duels.find(d=>d.id===uid(id)).run;

 const l=await lobby(1);for(let p=1;p<=4;p++)await l.add(p,2000+p);   // everyone starts with 5 points
 assert.equal(await points(1,l.sid),5);
 await assert.rejects(status(7,l.sid),/permission_denied/,'Outsiders cannot read the lobby');
 for(const stake of [null,0,11])await assert.rejects(invite(1,l,3000,2,stake),/reaction_stake/,'Stake must be 1-10');
 await assert.rejects(invite(1,l,3000,2,6),/reaction_funds/,'Both need the full stake');
 await assert.rejects(invite(1,l,3000,1),/permission_denied/,'No duel against yourself');
 let d=await invite(1,l,3000,2,3);assert.equal(d.status,'invited');assert.equal(d.run,null);
 assert.equal((await invite(1,l,3000,2,3)).id,d.id,'A retried invite returns the same duel');
 await assert.rejects(invite(1,l,3001,3,1),/reaction_pending/,'Only one open invitation');
 assert.equal(Number((await rpc('select reaction from pending_minigame_invites($1,$2)',[uid(2),l.sid])).rows[0].reaction),1,'Badge counts it');
 await assert.rejects(act(3,3000,'accept'),/permission_denied/,'Only the two players');
 await assert.rejects(act(1,3000,'accept'),/reaction_unavailable/,'The challenger cannot accept');
 d=await act(2,3000,'accept');assert.equal(d.status,'accepted');
 assert.equal(await points(1,l.sid),2,'Stake reserved');assert.equal(await points(2,l.sid),2);
 await assert.rejects(rpc('select * from correct_scoring_checkin($1,$2,$3,$4,$5)',[uid(1),uid(2001),'beer','small',0]),/quiz_reserved_points/,
  'A correction cannot spend reserved points');

 // Player 1: ready -> signal 3.5-6.5 s later; a false start keeps the try and waits again.
 d=await act(1,3000,'ready',0);assert.equal(d.run.phase,'reaction');assert.equal(d.run.step,0);
 const wait=Date.parse(d.run.signal_at)-Date.parse(d.server_now);assert(wait>=3500&&wait<=6500,'Calm wait '+wait);
 await assert.rejects(act(1,3000,'reaction',d.run.revision,200),/reaction_invalid/,'No tap before the signal');
 const before=d.run.signal_at;d=await act(1,3000,'false_start',d.run.revision);
 assert.equal(d.run.step,0,'False start does not count');assert.notEqual(d.run.signal_at,before);
 assert.equal((await act(1,3000,'false_start',d.run.revision-1)).run.revision,d.run.revision,'Stale retry is ignored');
 await clock(d.run.signal_at);await advance(200);
 await assert.rejects(act(1,3000,'reaction',d.run.revision,50),/reaction_invalid/,'Under 100 ms is a guess');
 d=await act(1,3000,'reaction',d.run.revision,200);assert.equal(d.run.step,1);assert.deepEqual(d.run.reaction_ms,[200]);
 assert.equal((await act(1,3000,'reaction',d.run.revision-1,200)).run.step,1,'A repeated tap is saved once');
 assert.equal((await status(2,l.sid)).duels[0].other_step,1,'The opponent sees progress');
 assert.equal((await status(2,l.sid)).duels[0].round_results.length,0,'but not the times');
 await tap(1,3000,300);d=await tap(1,3000,400);assert.equal(d.run.status,'done');assert.equal(d.status,'accepted');
 await f.reopen();assert.deepEqual((await run(1,3000)).reaction_ms,[200,300,400],'Saved tries survive a restart');
 // Player 2: 250, 250, miss -> rounds 1:p1 2:p2 3:p1 -> player 1 wins 2-1 and takes 3 points.
 await tap(2,3000,250);await tap(2,3000,250);d=await tap(2,3000,'miss');
 assert.equal(d.status,'completed');assert.equal(d.winner_id,l.mid(1));
 assert.deepEqual(d.round_results.map(r=>r.winner_id),[l.mid(1),l.mid(2),l.mid(1)]);
 assert.equal(d.round_results[2].opponent_ms,9999,'A miss is slower than any tap');
 assert.equal(await points(1,l.sid),8);assert.equal(await points(2,l.sid),2);assert.equal(await ledger(),1);
 await act(2,3000,'miss',d.run.revision);assert.equal(await ledger(),1,'Paid exactly once');

 // Normal season: one accepted outgoing duel per night; incoming is a separate allowance.
 assert.equal((await status(1,l.sid)).outgoing,false);
 await assert.rejects(invite(1,l,3010,3,1),/reaction_limit/);
 d=await invite(3,l,3020,1,2);d=await act(1,3020,'accept');assert.equal((await status(1,l.sid)).incoming,false);
 // Equal rounds (1-1, one tie) -> lower total wins: 3 has 200+600+300, 1 has 300+400+300.
 await tap(3,3020,200);await tap(3,3020,600);await tap(3,3020,300);
 await tap(1,3020,300);await tap(1,3020,400);d=await tap(1,3020,300);
 assert.equal(d.winner_id,l.mid(1),'1000 ms beats 1100 ms on equal rounds');assert.equal(await points(1,l.sid),10);

 // Test season: no nightly limit; nobody plays -> time runs out -> draw, stake back.
 const qa=await lobby(2,{test:true});for(let p=1;p<=2;p++)await qa.add(p,2100+p);
 d=await invite(1,qa,3100,2,5);d=await act(2,3100,'accept');assert.equal(await points(1,qa.sid),0);
 await clock(d.expires_at);d=(await status(1,qa.sid)).duels[0];
 assert.equal(d.status,'draw');assert.equal(await points(1,qa.sid),5,'Draw returns the stake');
 // One player played, the other walked away -> the player who played wins.
 d=await invite(1,qa,3101,2,1);await act(2,3101,'accept');for(const ms of [300,300,300])await tap(1,3101,ms);
 await clock((await status(1,qa.sid)).duels[0].expires_at);d=(await status(2,qa.sid)).duels[0];
 assert.equal(d.status,'completed');assert.equal(d.winner_id,qa.mid(1));assert.equal(await points(1,qa.sid),6);
 // Declined and cancelled invitations move no points.
 await invite(1,qa,3102,2,1);assert.equal((await act(1,3102,'cancel')).status,'cancelled');
 await invite(2,qa,3103,1,1);assert.equal((await act(1,3103,'decline')).status,'declined');
 assert.equal(await points(1,qa.sid),6);
 // Browser roles have no access.
 await q('set role anon');await assert.rejects(q('select * from reaction_duels'),/permission denied/);
 await assert.rejects(q('select reaction_status($1,$2)',[uid(1),qa.sid]),/permission denied/);await q('reset role');
 await f.close();
 console.log('Reaction Duel Postgres checks passed: stakes 1-10, reservation, calm wait, false start, best of 3, tie-break, timeout, ledger once, limits, access.');
})().catch(e=>{console.error(e);process.exit(1);});

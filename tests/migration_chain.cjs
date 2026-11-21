// Installs a fresh database exactly in the order documented in docs/MIGRATIONS.md
// (real PostgreSQL via PGlite, Supabase's storage schema stubbed) and checks the result.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {PGlite}=require(path.resolve(process.argv[2]));

// Same list as the numbered steps in docs/MIGRATIONS.md; the test fails if the two drift apart.
const order=fs.readFileSync('docs/MIGRATIONS.md','utf8').split('\n')
 .map(line=>line.match(/^\d+\.\s+`([^`]+\.sql)`/)).filter(Boolean).map(m=>m[1]);
assert(order.length>=20,'docs/MIGRATIONS.md lists the install order as numbered steps');
assert.equal(order[0],'schema.sql');

(async()=>{
 const pg=new PGlite();
 await pg.exec(`create role anon;create role authenticated;create role service_role bypassrls;
  grant usage on schema public to anon,authenticated,service_role;
  create schema storage;
  create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
  create table storage.objects(bucket_id text,name text,owner uuid);
  alter table storage.objects enable row level security;`);
 for(const file of order){
  const sql=fs.readFileSync(file==='schema.sql'?file:'migrations/'+file,'utf8').replace('create extension if not exists pgcrypto;','');
  try{await pg.exec(sql);}catch(error){console.error('FAILED at '+file+': '+error.message);process.exit(1);}
 }
 // Every migration file is either in the order or explained as skipped.
 const doc=fs.readFileSync('docs/MIGRATIONS.md','utf8');
 for(const file of fs.readdirSync('migrations').filter(f=>f.endsWith('.sql')))
  assert(doc.includes(file),file+' is not mentioned in docs/MIGRATIONS.md');
 const have=new Set((await pg.query("select proname from pg_proc where pronamespace='public'::regnamespace")).rows.map(r=>r.proname));
 for(const fn of ['accept_scoring_checkin','start_scoring_season','delete_lobby','chug_duel_action','quiz_action','time_action',
  'reaction_status','invite_reaction_duel','reaction_action','pending_minigame_invites','pending_minigame_invite_count','focus_status',
  'issue_lobby_invitation','pending_lobby_invitations','respond_to_lobby_invitation'])
  assert(have.has(fn),'missing function '+fn);
 const tables=new Set((await pg.query("select tablename from pg_tables where schemaname='public'")).rows.map(r=>r.tablename));
 for(const t of ['players','lobbies','seasons','drink_entries','friendships','chug_duels','quiz_duels','quiz_transfers','time_duels','reaction_duels','reaction_runs','season_recap_views'])
  assert(tables.has(t),'missing table '+t);
 // Both public API roles must be denied, even after the complete migration chain.
 const privateTables=['players','remembered_sessions','password_resets','login_attempts',
  'lobbies','lobby_memberships','seasons','drink_entries','friendships',
  'reaction_duels','reaction_runs','quiz_duels','quiz_transfers','time_duels','chug_duels','lobby_invitations',
  'season_recap_views'];
 const privateFunctions=['accept_scoring_checkin','correct_scoring_checkin','start_scoring_season',
  'delete_lobby','leave_lobby','chug_duel_action','quiz_action','time_action','reaction_action',
  'issue_lobby_invitation','pending_lobby_invitations','respond_to_lobby_invitation'];
 for(const fn of privateFunctions)assert(have.has(fn),'missing protected function '+fn);
 for(const role of ['anon','authenticated']){
  for(const t of privateTables){
   const privileges=(await pg.query('select has_table_privilege($1,$2,$3) allowed',
    [role,'public.'+t,'SELECT,INSERT,UPDATE,DELETE'])).rows[0];
   assert.equal(privileges.allowed,false,role+' must have no direct access to '+t);
  }
  const functions=(await pg.query(`select p.oid::regprocedure::text signature,
   has_function_privilege($1,p.oid,'EXECUTE') allowed from pg_proc p
   where p.pronamespace='public'::regnamespace and p.proname=any($2::text[])`,
   [role,privateFunctions])).rows;
  for(const fn of functions)assert.equal(fn.allowed,false,role+' must not execute '+fn.signature);
  await pg.exec('set role '+role);
  for(const t of privateTables)
   await assert.rejects(pg.query('select 1 from public.'+t),/permission denied/,role+': '+t+' must stay private');
  await pg.exec('reset role');
 }
 await pg.exec(fs.readFileSync('tests/lobby_invitations_postgres.sql','utf8'));
 console.log('Migration chain passed: '+order.length+' files in documented order, every migration file accounted for, functions, tables and private access present.');
 await pg.close();
})().catch(e=>{console.error(e);process.exit(1);});

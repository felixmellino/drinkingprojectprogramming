"""Explicit integration suite: real connections to a disposable local PostgreSQL.

Not named test_*.py: run with scripts/verify.py --group postgres. Missing setup
fails rather than silently skipping. Each test gets a new, uniquely named DB.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import subprocess
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from core.scoring_v1 import new_rules, replay_season
from data.db import _row_to_drink_entry

ROOT = Path(__file__).resolve().parents[1]


class Database:
    def __init__(self, url):
        self.url = url
        self.conn = self.connect()
        c = self.conn
        c.execute("create schema storage; create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]); create table storage.objects(bucket_id text,name text,owner uuid); alter table storage.objects enable row level security")
        c.execute("create table test_clock(at_time timestamptz); insert into test_clock values('2026-11-19T20:00:00Z'); grant select on test_clock to service_role")
        order = re.findall(r"^\d+\. `([^`]+\.sql)`", (ROOT / 'docs/MIGRATIONS.md').read_text(), re.M)
        assert len(order) >= 25
        for name in order:
            path = ROOT / name if name == 'schema.sql' else ROOT / 'migrations' / name
            c.execute(path.read_text().replace('statement_timestamp()', '(select at_time from public.test_clock)'))
        self.players, self.members = [uuid4() for _ in range(4)], [uuid4() for _ in range(4)]
        self.lobby = uuid4()
        c.execute("insert into lobbies(id,name,invite_code) values(%s,'Transaction fixture',%s)", (self.lobby, str(self.lobby)))
        for index, (player, member) in enumerate(zip(self.players, self.members)):
            c.execute("insert into players(id,display_name,first_name,last_name,pin_hash) values(%s,%s,'Test','Only','fixture')", (player, 'Test ' + str(index)))
            c.execute('insert into lobby_memberships(id,player_id,lobby_id) values(%s,%s,%s)', (member, player, self.lobby))
        c.execute("insert into territories values('transaction-fixture','Transaction fixture','{}')")
        self.season = self.rpc('select * from start_scoring_season(%s,%s,%s,%s,%s)',
                               (self.players[0], self.lobby, '1_month', 'Europe/Lisbon', Jsonb(new_rules(test_mode=True))))[0]['id']

    def connect(self):
        connection = psycopg.connect(self.url, autocommit=True, row_factory=dict_row)
        connection.execute("set statement_timeout='15s'; set lock_timeout='10s'")
        return connection

    def rpc(self, query, parameters=(), connection=None):
        connection = connection or self.conn
        connection.execute('set role service_role')
        try:
            cursor = connection.execute(query, parameters)
            return cursor.fetchall() if cursor.description else []
        finally:
            connection.execute('reset role')

    def now(self):
        return self.conn.execute('select at_time from test_clock').fetchone()['at_time']

    def advance(self, seconds):
        self.conn.execute('update test_clock set at_time=at_time+%s', (timedelta(seconds=seconds),))

    def checkin(self, player=0, capture=None, connection=None, kind='shot', size=None, territory='transaction-fixture'):
        capture = capture or uuid4()
        return self.rpc('select * from accept_scoring_checkin(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (self.players[player], capture, self.members[player], self.season, kind, size,
                         territory, 'matched' if territory else 'outside', f'{self.lobby}/{capture}.jpg', self.now()), connection)[0]

    def rows(self):
        return self.conn.execute('select * from drink_entries order by event_order').fetchall()

    def race(self, actions):
        barrier = Barrier(len(actions))
        def run(action):
            with self.connect() as connection:
                barrier.wait(timeout=10)
                try:
                    return ('ok', action(connection))
                except psycopg.Error as error:
                    return ('rejected', error.diag.message_primary)
        with ThreadPoolExecutor(max_workers=len(actions)) as pool:
            return list(pool.map(run, actions))

    def reaction(self, first=0, second=1, stake=3):
        return self.rpc('select invite_reaction_duel(%s,%s,%s,%s,%s) data',
                        (self.players[first], self.season, uuid4(), self.members[second], stake))[0]['data']


@pytest.fixture
def db():
    url = os.environ.get('VERIFICATION_DATABASE_URL', '')
    if not url:
        pytest.fail('Set VERIFICATION_DATABASE_URL to the disposable local test service; this suite cannot be skipped.')
    info = conninfo_to_dict(url)
    assert info.get('host') in ('localhost', '127.0.0.1', '::1'), 'Only a local test service is allowed'
    assert info.get('dbname') == 'wegopub_verification' and info.get('user') == 'verification', 'Use the designated test database/user'
    name = 'wegopub_verify_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        for role in ('anon', 'authenticated', 'service_role'):
            if not admin.execute('select 1 from pg_roles where rolname=%s', (role,)).fetchone():
                admin.execute(sql.SQL('create role {} {}').format(sql.Identifier(role), sql.SQL('bypassrls' if role == 'service_role' else 'nobypassrls')))
        admin.execute(sql.SQL('create database {}').format(sql.Identifier(name)))
        fixture = None
        try:
            fixture = Database(make_conninfo(url, dbname=name))
            admin.close()  # A later test deliberately restarts the disposable server.
            yield fixture
        finally:
            if fixture:
                fixture.conn.close()
            # Only the randomly named DB this fixture created can be removed.
            assert name.startswith('wegopub_verify_')
            with psycopg.connect(url, autocommit=True) as cleanup:
                cleanup.execute(sql.SQL('drop database {} with (force)').format(sql.Identifier(name)))


def test_eight_simultaneous_retries_award_one_entry_and_one_owner_income(db):
    db.checkin(0)
    capture = uuid4()
    results = db.race([lambda c: db.checkin(1, capture, c) for _ in range(8)])
    assert all(status == 'ok' and row['id'] == capture for status, row in results)
    rows = db.rows()
    assert len(rows) == 2
    assert rows[-1]['owner_membership_id'] == db.members[0]
    assert rows[-1]['owner_bonus_quarters'] == 4


def test_competing_distinct_captures_cannot_bypass_cooldown(db):
    results = db.race([lambda c: db.checkin(0, connection=c) for _ in range(8)])
    assert sum(status == 'ok' for status, _ in results) == 1
    assert [reason for status, reason in results if status == 'rejected'] == ['cooldown'] * 7
    assert len(db.rows()) == 1


def test_simultaneous_equal_scores_have_one_order_and_python_sql_parity(db):
    results = db.race([lambda c, p=p: db.checkin(p, connection=c) for p in (0, 1)])
    assert all(status == 'ok' for status, _ in results)
    rows = db.rows()
    assert rows[0]['event_order'] < rows[1]['event_order']
    assert rows[0]['owner_membership_id'] is None
    assert rows[1]['owner_membership_id'] == rows[0]['membership_id']
    replay = replay_season([_row_to_drink_entry(row) for row in json.loads(json.dumps(rows, default=str))])
    assert replay.owners['transaction-fixture'] == str(rows[0]['membership_id'])
    assert replay.awards[str(rows[1]['id'])][1] == rows[1]['owner_bonus_quarters']


def test_two_corrections_with_same_revision_cannot_overwrite_each_other(db):
    entry = db.checkin()
    def edit(connection, kind, size):
        return db.rpc('select * from correct_scoring_checkin(%s,%s,%s,%s,%s)',
                      (db.players[0], entry['id'], kind, size, 0), connection)[0]
    results = db.race([lambda c: edit(c, 'beer', 'small'), lambda c: edit(c, 'mixed', 'large')])
    assert sum(status == 'ok' for status, _ in results) == 1
    assert [reason for status, reason in results if status == 'rejected'] == ['correction_conflict']
    assert db.rows()[0]['revision'] == 1


def test_injected_failure_rolls_back_entry_and_replay_then_retry_succeeds(db):
    db.checkin(0)
    before = db.rows()
    db.conn.execute("create function fail_verification_insert() returns trigger language plpgsql as $$ begin raise exception 'injected_verification_failure'; end $$; create trigger fail_verification after insert on drink_entries for each row execute function fail_verification_insert()")
    capture = uuid4()
    with pytest.raises(psycopg.Error, match='injected_verification_failure'):
        db.checkin(1, capture)
    assert db.rows() == before
    db.conn.execute('drop trigger fail_verification on drink_entries')
    assert db.checkin(1, capture)['id'] == capture
    assert len(db.rows()) == 2


def test_two_acceptances_cannot_reserve_the_same_players_points_twice(db):
    for p in range(3):
        db.checkin(p, kind='mixed', size='large', territory=None)
    first, second = db.reaction(0, 1), db.reaction(2, 1)
    results = db.race([lambda c, d=d: db.rpc('select reaction_action(%s,%s,%s,%s,%s) data',
                     (db.players[1], d['id'], 'accept', None, None), c)[0]['data'] for d in (first, second)])
    assert sum(status == 'ok' and row['status'] == 'accepted' for status, row in results) == 1
    assert db.conn.execute("select count(*) n from reaction_duels where status='accepted'").fetchone()['n'] == 1
    status = db.rpc('select reaction_status(%s,%s) data', (db.players[1], db.season))[0]['data']
    assert status['available_points'] == 2


def test_repeated_simultaneous_final_taps_create_one_stake_transfer(db):
    for p in (0, 1):
        db.checkin(p, kind='mixed', size='large', territory=None)
    duel = db.reaction()
    db.rpc('select reaction_action(%s,%s,%s,%s,%s)', (db.players[1], duel['id'], 'accept', None, None))
    # Persist a valid penultimate state; exercise final acceptance/settlement for real.
    db.conn.execute("update reaction_runs set step=3,times=array[200,200,200] where duel_id=%s and membership_id=%s", (duel['id'], db.members[0]))
    db.conn.execute("update reaction_runs set step=2,times=array[400,400],revision=2,signal_at=%s,deadline=%s where duel_id=%s and membership_id=%s", (db.now()-timedelta(seconds=1), db.now()+timedelta(seconds=1), duel['id'], db.members[1]))
    results = db.race([lambda c: db.rpc('select reaction_action(%s,%s,%s,%s,%s) data',
                                      (db.players[1], duel['id'], 'reaction', 2, 400), c)[0]['data'] for _ in range(4)])
    assert all(status == 'ok' and row['status'] == 'completed'
               and row['winner_id'] == str(db.members[0]) for status, row in results)
    transfers = db.conn.execute('select * from quiz_transfers').fetchall()
    assert len(transfers) == 1 and transfers[0]['points'] == 3
    assert transfers[0]['source_id'] == db.members[1] and transfers[0]['target_id'] == db.members[0]


def test_membership_is_rechecked_after_waiting_for_lobby_lock(db):
    waiting = Event()
    pid = []
    def submit():
        with db.connect() as connection:
            pid.append(connection.execute('select pg_backend_pid() pid').fetchone()['pid'])
            waiting.set()
            try:
                db.checkin(1, connection=connection)
            except psycopg.Error as error:
                return error.diag.message_primary
            return 'unexpected success'
    with db.connect() as holder, ThreadPoolExecutor(max_workers=1) as pool:
        holder.execute('begin')
        holder.execute('select pg_advisory_xact_lock(hashtext(%s))', (str(db.lobby),))
        task = pool.submit(submit)
        assert waiting.wait(5)
        until = monotonic() + 5
        while not db.conn.execute("select 1 from pg_locks where pid=%s and locktype='advisory' and not granted", (pid[0],)).fetchone():
            assert monotonic() < until, 'Submission never reached the lobby lock'
            sleep(.01)
        db.rpc('select leave_lobby(%s,%s)', (db.players[1], db.lobby), holder)
        holder.execute('commit')
        assert task.result(timeout=10) == 'permission_denied'
    assert db.rows() == []


def test_real_server_restart_preserves_entries_rules_invites_and_retry_identity(db):
    container = os.environ.get('VERIFICATION_CONTAINER_ID', '')
    assert re.fullmatch(r'[0-9a-f]{12,64}', container), 'Supply the disposable Docker service ID for the restart check'
    first = db.checkin(0, kind='mixed', size='large', territory=None)
    db.checkin(1, kind='mixed', size='large', territory=None)
    duel = db.reaction()
    before = db.rows()
    rules = db.conn.execute('select scoring_rules from seasons where id=%s', (db.season,)).fetchone()['scoring_rules']
    db.conn.close()
    subprocess.run(['docker', 'restart', container], check=True, capture_output=True, text=True, timeout=60)
    until = monotonic() + 30
    while True:
        try:
            db.conn = db.connect()
            break
        except psycopg.OperationalError:
            assert monotonic() < until, 'Disposable PostgreSQL did not restart'
            sleep(.2)
    assert db.rows() == before
    assert db.conn.execute('select scoring_rules from seasons where id=%s', (db.season,)).fetchone()['scoring_rules'] == rules
    assert db.conn.execute('select status from reaction_duels where id=%s', (duel['id'],)).fetchone()['status'] == 'invited'
    assert db.checkin(0, first['id'])['id'] == first['id']
    assert db.rows() == before

"""Reaction Duel: rule helpers, browser-message checks and the Streamlit screen."""
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

import reaction_duel_ui as reaction_ui
from core.reaction_duel import CONFIG, STAKES, component_action, outcome, time_label, validate_stake
from tests.test_chug_duel_ui import service, open_page, button  # noqa: F401  (pytest fixture)
from tests.test_scoring_v1 import START
from tests.feedback_helpers import assert_blocked


def test_python_and_sql_share_the_same_rules():
    sql = Path('migrations/025_reaction_duel.sql').read_text(encoding='utf-8')
    literal = sql.split('create or replace function public._reaction_rules()', 1)[1].split("select '", 1)[1].split("'::jsonb", 1)[0]
    assert json.loads(literal) == CONFIG
    assert STAKES == list(range(1, 11))


@pytest.mark.parametrize('a,b,expected', [
    ([200, 300, 400], [250, 250, 9999], 'challenger'),   # 2 rounds to 1
    ([300, 300, 300], [200, 200, 9999], 'opponent'),
    ([200, 600, 300], [300, 400, 300], 'opponent'),      # 1-1 and a tie: 1000 ms beats 1100 ms
    ([200, 500, 300], [300, 400, 300], None),            # same rounds, same total: draw
    ([300, 300, 300], [], 'challenger'),                 # the other never played
    ([], [], None),
])
def test_best_of_three_with_total_time_tie_break(a, b, expected):
    assert outcome(a, b) == expected


@pytest.mark.parametrize('stake', [1, 10])
def test_stakes_from_one_to_ten(stake):
    assert validate_stake(stake) == stake


@pytest.mark.parametrize('stake', [0, 11, 2.0, True, None, '3'])
def test_invalid_stakes_are_rejected(stake):
    with pytest.raises(ValueError):
        validate_stake(stake)


RUN = {'id': 'duel', 'revision': 4}


@pytest.mark.parametrize('value,expected', [
    ({'attempt_id': 'duel', 'revision': 4, 'action': 'ready'}, ('ready', None)),
    ({'attempt_id': 'duel', 'revision': 4, 'action': 'false_start'}, ('false_start', None)),
    ({'attempt_id': 'duel', 'revision': 4, 'action': 'fail'}, ('miss', None)),
    ({'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': {'elapsed_ms': 100}}, ('reaction', 100)),
    ({'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': {'elapsed_ms': 2000}}, ('reaction', 2000)),
])
def test_current_try_messages_are_accepted(value, expected):
    assert component_action(value, RUN) == expected


@pytest.mark.parametrize('value', [None, [], {'attempt_id': 'other', 'revision': 4, 'action': 'ready'},
    {'attempt_id': 'duel', 'revision': 3, 'action': 'ready'},              # stale
    {'attempt_id': 'duel', 'revision': True, 'action': 'ready'},
    {'attempt_id': 'duel', 'revision': 4, 'action': 'win'},
    {'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': {'elapsed_ms': 99}},   # a guess
    {'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': {'elapsed_ms': 2001}},
    {'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': {'elapsed_ms': 150.0}},
    {'attempt_id': 'duel', 'revision': 4, 'action': 'reaction', 'payload': 'x'}])
def test_untrusted_messages_cannot_supply_a_result(value):
    assert component_action(value, RUN) is None


def test_missed_tries_have_a_readable_label():
    assert time_label(9999) == 'missed' and time_label(231) == '231 ms'


def _duel(status='invited', **extra):
    return dict(id='r1', status=status, challenger_id='a', opponent_id='b', stake=3, winner_id=None,
                reason=None, round_results=[], run=None, other_step=0, **extra)


@pytest.fixture
def reaction(service, monkeypatch):
    state = {'duels': [], 'open': True, 'outgoing': True, 'incoming': True, 'available_points': 5, 'board': None}
    monkeypatch.setattr(reaction_ui.db, 'reaction_status',
                        lambda *args: deepcopy({k: v for k, v in state.items() if k != 'board'}))
    invite = Mock(side_effect=lambda *args: state['duels'].append(_duel()) or _duel())
    act = Mock()
    monkeypatch.setattr(reaction_ui.db, 'invite_reaction_duel', invite)
    monkeypatch.setattr(reaction_ui.db, 'reaction_action', act)
    monkeypatch.setattr(reaction_ui, 'reaction_board', lambda run: state['board'])
    return state, invite, act


def test_tile_opens_the_duel_and_a_challenge_sends_who_and_stake(reaction):
    state, invite, act = reaction
    page = open_page(selected=None)
    button(page, 'Open Reaction Duel').click().run()
    assert not page.exception and any('5 points available' in m.value for m in page.markdown)
    page.radio(key='pill_radio_reaction_stake').set_value(2).run()
    button(page, 'Challenge').click().run()
    assert not page.exception and invite.call_count == 1
    assert invite.call_args.args[3:] == ('b', 2)
    assert button(page, 'Cancel') and not any(b.label == 'Challenge' for b in page.button)


def test_stake_above_the_available_points_cannot_be_sent(reaction):
    state, invite, _ = reaction
    state['available_points'] = 2
    page = open_page(selected='reaction')
    page.radio(key='pill_radio_reaction_stake').set_value(3).run()
    assert_blocked(page, 'Challenge', '3', '2', 'lower stake')
    invite.assert_not_called()


def test_opponent_accepts_and_a_tap_is_sent_with_the_saved_revision(reaction):
    state, _, act = reaction
    state['duels'] = [_duel()]
    page = open_page('pb', 'b', selected='reaction')
    button(page, 'Accept').click().run()
    assert act.call_args.args[1:3] == ('r1', 'accept')
    run = dict(id='r1', revision=2, status='running', phase='reaction', step=0, reaction_ms=[])
    state['duels'] = [_duel('accepted') | {'run': run}]
    state['board'] = {'attempt_id': 'r1', 'revision': 2, 'action': 'reaction', 'payload': {'elapsed_ms': 240}}
    page.run()
    assert not page.exception and button(page, 'Back to games')
    assert act.call_args.args[1:] == ('r1', 'reaction', 2, 240)


def test_finished_tries_wait_for_the_opponent_then_show_rounds_and_points(reaction):
    state, _, _ = reaction
    run = dict(id='r1', revision=5, status='done', phase='reaction', step=3, reaction_ms=[200, 300, 400])
    state['duels'] = [_duel('accepted') | {'run': run, 'other_step': 1}]
    page = open_page(selected='reaction')
    text = ' '.join(m.value for m in page.markdown)
    assert 'Waiting for Bob · try 2 of 3' in text and '200 ms, 300 ms, 400 ms' in text
    rounds = [dict(round_no=1, challenger_ms=200, opponent_ms=250, winner_id='a'),
              dict(round_no=2, challenger_ms=300, opponent_ms=250, winner_id='b'),
              dict(round_no=3, challenger_ms=400, opponent_ms=9999, winner_id='a')]
    state['duels'] = [_duel('completed') | {'run': run, 'winner_id': 'a', 'round_results': rounds, 'reason': 'rounds'}]
    page.run()
    text = ' '.join(m.value for m in page.markdown)
    assert not page.exception and 'game-result-won' in text and '>You won<' in text and '>+3<' in text and 'missed' in text
    loser = open_page('pb', 'b', selected='reaction')
    loser.session_state['reaction_focused_id'] = 'r1'
    loser.run()
    lost = ' '.join(m.value for m in loser.markdown)
    assert 'game-result-lost' in lost and '>You lost<' in lost and '>−3<' in lost
    button(page, 'Done').click().run()
    assert any(b.label == 'Challenge' for b in page.button)


def test_missing_migration_shows_one_clear_message(reaction, monkeypatch):
    def missing(*args):
        raise RuntimeError('Reaction Duel needs database migration 025 before it can open.')
    monkeypatch.setattr(reaction_ui.db, 'reaction_status', missing)
    page = open_page(selected='reaction')
    assert not page.exception and 'migration 025' in page.error[0].value

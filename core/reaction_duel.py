"""Reaction Duel rules (replaces the solo Reaction Test on the Games tab).

Two lobby members play three reaction tries each for a stake of 1-10 season points.
Try n of one player is compared with try n of the other; the faster time wins the
round, more rounds wins the duel, equal rounds go to the lower total, equal totals
are a draw. PostgreSQL (migration 025) decides every result; this module holds the
same constants, the input checks for browser messages and the error texts.
"""
from core.chug_duel import validate_pair  # noqa: F401  (same opponent rule as the other duels)

CONFIG = dict(version=1, min_stake=1, max_stake=10, reaction_trials=3, reaction_response_ms=2000,
              reaction_min_ms=100, reaction_wait_min_ms=3500, reaction_wait_max_ms=6500,
              invitation_seconds=600, game_seconds=900, miss_ms=9999)
STAKES = list(range(CONFIG['min_stake'], CONFIG['max_stake'] + 1))
FINAL = {'completed', 'draw', 'declined', 'cancelled', 'expired'}


def validate_stake(stake):
    if type(stake) is not int or stake not in STAKES:
        raise ValueError('Choose a stake from 1 to 10 points.')
    return stake


def outcome(challenger_ms, opponent_ms):
    """'challenger', 'opponent' or None (draw) for two lists of three times (9999 = missed)."""
    a = list(challenger_ms) + [CONFIG['miss_ms']] * (3 - len(challenger_ms))
    b = list(opponent_ms) + [CONFIG['miss_ms']] * (3 - len(opponent_ms))
    a_wins = sum(x < y for x, y in zip(a, b))
    b_wins = sum(y < x for x, y in zip(a, b))
    if a_wins != b_wins:
        return 'challenger' if a_wins > b_wins else 'opponent'
    if sum(a) != sum(b):
        return 'challenger' if sum(a) < sum(b) else 'opponent'
    return None


def component_action(value, run):
    """Accept only a message about the current try of the viewer's own run."""
    if not isinstance(value, dict) or not run or value.get('attempt_id') != run['id']:
        return None
    if type(value.get('revision')) is not int or value['revision'] != run['revision']:
        return None
    action, payload = value.get('action'), value.get('payload') or {}
    if action in ('ready', 'false_start'):
        return action, None
    if action == 'fail':          # no tap within the response window
        return 'miss', None
    elapsed = payload.get('elapsed_ms') if isinstance(payload, dict) else None
    if (action == 'reaction' and type(elapsed) is int
            and CONFIG['reaction_min_ms'] <= elapsed <= CONFIG['reaction_response_ms']):
        return 'reaction', elapsed
    return None


def time_label(ms):
    return 'missed' if ms is None or ms >= CONFIG['miss_ms'] else f'{ms} ms'


ERRORS = {
    'permission_denied': 'This duel is not available to your account. Reopen your lobby and choose a duel you participate in.',
    'reaction_stake': 'Choose a stake from 1 to 10 points.',
    'reaction_funds': 'Both players need the full stake. Choose a lower stake or earn more points with an accepted check-in. Reserved points cannot be used twice.',
    'reaction_team': 'Choose a player from another team. Both players must join a team on the Lobby page first.',
    'reaction_busy': 'One of you is already in a Reaction Duel. Finish it first.',
    'reaction_pending': 'Cancel your open invitation before sending another.',
    'reaction_limit': 'You already accepted or played a Reaction Duel in this role tonight. Try again after 06:00 in the lobby timezone; finishing the duel does not reset this limit.',
    'reaction_unavailable': 'The duel has changed or expired. Keep this page open for its saved state to reload, then choose a current invitation or start a new duel.',
    'reaction_invalid': 'That tap could not be counted for the current try. Wait for the saved screen to reload, then follow the current prompt; completed tries cannot be changed.',
    'quiz_reserved_points': 'These points are reserved for a duel. Finish it first.',
    'scoring_closed': 'Reaction Duels are closed right now. Open Check in to see the next scoring opening; choose a new lobby if the season ended. Test seasons can play throughout an active season.',
}

"""Focus Challenge's frozen configuration and safe component messages."""
from copy import deepcopy

FOCUS_RULES = {
    'version': 1, 'first_unlock': 5, 'retry_step': 2,
    'reaction_trials': 3, 'reaction_median_ms': 350,
    'reaction_wait_min_ms': 1500, 'reaction_wait_max_ms': 4500,
    'reaction_response_ms': 2000, 'memory_length': 7, 'memory_cells': 9,
    'memory_flash_ms': 650, 'memory_gap_ms': 200, 'memory_input_ms': 15000,
    'precision_targets': 12, 'precision_ms': 12000,
    'ready_seconds': 30, 'attempt_seconds': 180, 'delivery_grace_ms': 2000,
    'boost_seconds': 3600, 'multiplier': 1.5,
}

ERRORS = {
    'focus_disabled': 'Focus Challenge is available in new seasons created with its rules.',
    'focus_locked': 'More accepted check-ins are needed for your next attempt.',
    'focus_won': 'You already earned this evening’s Focus boost.',
    'focus_active_boost': 'Your previous evening’s boost is still active. Wait until it ends.',
    'focus_busy': 'Finish the running minigame before starting another.',
    'focus_invalid_action': 'The game action could not be accepted. Reopen the saved attempt.',
    'permission_denied': 'Choose a lobby you belong to before playing.',
    'scoring_closed': 'Focus Challenge is closed outside this season’s scoring window.',
}


def new_focus_rules():
    return deepcopy(FOCUS_RULES)


def enabled(season):
    return (season.scoring_version == 'v1'
            and (test_mode(season)
                 or (season.scoring_rules or {}).get('focus_challenge', {}).get('version') == 1))


def test_mode(season):
    """Only an explicit frozen JSON boolean enables QA, never a lobby name."""
    return (season.scoring_version == 'v1'
            and (season.scoring_rules or {}).get('test_mode') is True)


def component_action(value, attempt):
    """Only allow bounded evidence for the currently saved attempt/revision."""
    if not isinstance(value, dict) or value.get('attempt_id') != attempt['id']:
        return None
    revision = value.get('revision')
    if type(revision) is not int or revision != attempt['revision']:
        return None
    action, payload = value.get('action'), value.get('payload', {})
    if not isinstance(payload, dict):
        return None
    if action in ('ready', 'fail', 'false_start'):
        return action, {}
    if action == 'reaction':
        ms = payload.get('elapsed_ms')
        if type(ms) is int and 0 <= ms <= 2000:
            return action, {'elapsed_ms': ms}
    return None

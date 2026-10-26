"""Player-centred adaptation of the research-inspired hybrid engine.

Only the focused defender's candidate movement changes. All other authored
player trajectories remain the same in every alternative, so scores are
comparable at a shared information state and time. Uncalibrated heuristics.
"""
from copy import deepcopy

from .engine import ACTIONS
from .hybrid import analyze_hybrid, _validate_scene
from .decision_diagnostics import explain_offside_opportunity
from .explanations import with_explanations


def selectable_defenders(scene: dict) -> list[dict]:
    """Goalkeeper participates in defensive/offside calculations but is not selectable."""
    return [{
        'id': p['id'], 'number': p['number'], 'name': p['name'],
        'marking_target_id': p.get('marking_target_id'),
        'authored_motion': 'direction' if p['id'] == scene['defender_id'] else 'constant_velocity',
    } for p in scene['players'] if p['team'] == 'defense' and not p.get('is_goalkeeper')]


def analyze_player(scene: dict, defender_id: str) -> dict:
    _validate_scene(scene)
    choices = selectable_defenders(scene)
    if defender_id not in {p['id'] for p in choices}:
        raise ValueError('This player is not a selectable outfield defender')
    configured = deepcopy(scene)
    configured['observed_primary_defender_id'] = scene['defender_id']
    configured['observed_primary_action'] = scene['actual_action']
    configured['defender_id'] = defender_id
    configured['player_centric'] = True
    configured['movement_frame'] = 'body'
    result = analyze_hybrid(configured)
    selected = next(p for p in choices if p['id'] == defender_id)
    result['selected_defender'] = selected
    result['offside_opportunity'] = explain_offside_opportunity(configured)
    result['selectable_defenders'] = choices
    result['actual_action'] = 'observed'
    result['model_warning'] += ' Authored background motion is synthetic, not a recorded player decision. Best move is only best among the tested candidate paths.'
    return with_explanations(result)

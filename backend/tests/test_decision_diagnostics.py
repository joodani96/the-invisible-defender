"""Focused defender's offside feasibility must match the actual pre-pass engine."""
from copy import deepcopy

from app.data import SCENARIOS
from app.player_analysis import analyze_player


def test_d2_cannot_step_forward_enough_before_kick():
    res = analyze_player(SCENARIOS[0], 'd2')
    d = res['offside_opportunity']
    assert d['status'] == 'insufficient_time_to_advance'
    assert d['target_id'] == 'a9'
    assert d['can_selected_defender_set_offside_alone_in_principle']
    assert d['minimum_forward_displacement_at_kick_m'] == 3.46
    assert 0 < d['tested_forward_displacement_by_kick_m'] <= 0.75
    assert not d['forward_target_offside']
    assert not next(x for x in res['pre_pass']['options'] if x['action'] == 'forward')['offside']['target_statuses']['a9']['offside_position']


def test_d4_stepping_forward_cannot_overrule_others_at_back():
    d = analyze_player(SCENARIOS[0], 'd4')['offside_opportunity']
    assert d['status'] == 'other_defenders_keep_target_onside'
    assert not d['can_selected_defender_set_offside_alone_in_principle']
    assert d['other_defenders_at_or_behind_receiver'] >= 2


def test_d2_can_make_attacker_offside_if_initially_close_enough():
    scene = deepcopy(SCENARIOS[0])
    next(p for p in scene['players'] if p['id'] == 'd2')['x'] = 92.0
    d = analyze_player(scene, 'd2')['offside_opportunity']
    assert d['status'] == 'offside_trap_feasible_in_tested_move'
    assert not d['hold_target_offside']
    assert d['forward_target_offside']
    assert d['minimum_forward_displacement_at_kick_m'] < d['tested_forward_displacement_by_kick_m']


def test_offside_trap_scene_already_offside_with_hold():
    d = analyze_player(SCENARIOS[3], 'd4')['offside_opportunity']
    assert d['status'] == 'already_offside'


def test_post_pass_alternatives_cannot_change_prior_offside():
    res = analyze_player(SCENARIOS[0], 'd2')
    lines = {o['offside']['offside_line_x'] for o in res['post_pass']['options']}
    assert len(lines) == 1


def test_opportunity_is_unavailable_at_restart_exempt_from_offside():
    scene = deepcopy(SCENARIOS[0]);scene['event_type'] = 'throw_in'
    d = analyze_player(scene, 'd2')['offside_opportunity']
    assert d['status'] == 'exempt_restart'

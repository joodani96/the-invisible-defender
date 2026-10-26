"""Behavioural invariants for the independent v0.3 experimental hybrid engine."""
from copy import deepcopy
from math import isclose

import pytest
from fastapi.testclient import TestClient

from app.data import SCENARIOS
from app.hybrid import analyze_hybrid, defender_position, evaluate_hybrid, pass_coverage, scripted_position, pass_geometry
from app.main import app


def scene():
    return deepcopy(SCENARIOS[0])


def lane(result, target='a9'):
    return next(p for p in result['passes'] if p['target_id'] == target)


def test_two_distinct_phases_are_exposed_with_nine_actions():
    result = analyze_hybrid(scene())
    assert 'uncalibrated' in result['model_warning'].lower()
    for name in ('pre_pass', 'post_pass'):
        phase = result[name]
        assert len(phase['options']) == 9
        assert min(o['score'] for o in phase['options']) == phase['optimal_score']
        assert phase['actual_score'] >= phase['optimal_score']
        assert phase['optimal_score'] >= 0


def test_dynamic_pass_choice_plus_recycle_is_normalized():
    s = scene()
    for action in ('hold', 'up', 'down'):
        r = evaluate_hybrid(s, action, 'pre')
        assert sum(p['pass_choice_index'] for p in r['passes']) + r['recycle_choice_index'] == pytest.approx(1, abs=.00003)
    upper_hold = lane(evaluate_hybrid(s, 'hold', 'pre'))['pass_choice_index']
    upper_closed = lane(evaluate_hybrid(s, 'up', 'pre'))['pass_choice_index']
    assert upper_closed < upper_hold


def test_prepass_upper_move_reduces_the_danger_of_an_open_upper_lane():
    s = scene()
    result = analyze_hybrid(s)['pre_pass']
    assert result['optimal_action'] == 'up'
    assert result['optimal_score'] < result['baseline_score']
    assert lane(evaluate_hybrid(s, 'up', 'pre'))['tracked_min_gap_m'] < lane(evaluate_hybrid(s, 'hold', 'pre'))['tracked_min_gap_m']


def test_selected_postpass_target_cannot_change_when_moving():
    s = scene()
    for action in ('hold', 'up', 'down'):
        result = evaluate_hybrid(s, action, 'post')
        assert lane(result, 'a9')['pass_choice_index'] == 1
        assert lane(result, 'a11')['pass_choice_index'] == 0
        assert lane(result, 'a11')['weighted_threat'] == 0
        assert result['recycle_choice_index'] == 0


def test_change_to_unselected_receiver_does_not_change_postpass_score():
    s = scene()
    changed = deepcopy(s)
    next(p for p in changed['players'] if p['id']=='a11').update(x=66, y=60)
    changed['targets'][1]['weight'] = 1000
    for action in ('hold', 'up', 'down'):
        assert evaluate_hybrid(s, action, 'post')['score'] == evaluate_hybrid(changed, action, 'post')['score']


def test_postpass_candidates_share_exactly_the_same_prelaunch_history():
    s = scene()
    launch = s['pass_launch_delay_s']
    for t in (0, .2, .35, launch, launch+.12):
        pos = [defender_position(s, a, t, 'post') for a in ('up','down','hold','backward')]
        assert pos.count(pos[0]) == len(pos)
    assert defender_position(s, 'up', launch+.6, 'post')['y'] < defender_position(s, 'down', launch+.6, 'post')['y']


def test_teammate_coverage_reduces_tracked_players_marginal_credit():
    s = scene()
    unassisted = lane(evaluate_hybrid(s, 'up', 'pre'))
    supported = scene()
    next(p for p in supported['players'] if p['id'] == 'd5').update(x=76, y=30)
    assisted = lane(evaluate_hybrid(supported, 'up', 'pre'))
    assert assisted['other_defenders_coverage_index'] > unassisted['other_defenders_coverage_index']
    assert assisted['marginal_coverage_index'] < unassisted['marginal_coverage_index']
    # Tracked defender's own raw coverage does not grow when teammate is repositioned.
    assert assisted['tracked_coverage_index'] == pytest.approx(unassisted['tracked_coverage_index'])


def test_lower_lanes_already_covered_by_teammate():
    s = scene()
    top = lane(evaluate_hybrid(s, 'hold', 'pre'), 'a9')
    bottom = lane(evaluate_hybrid(s, 'hold', 'pre'), 'a11')
    assert bottom['other_defenders_coverage_index'] > top['other_defenders_coverage_index']


def test_interception_is_distinct_from_soft_coverage_index():
    s = scene()
    hold = lane(evaluate_hybrid(s, 'hold', 'post'))
    up = lane(evaluate_hybrid(s, 'up', 'post'))
    assert hold['tracked_coverage_index'] > 0   # soft coverage estimate
    assert hold['contact_time_s'] is None       # not a simulated ball contact
    assert hold['tracked_min_gap_m'] > 1.05
    assert up['contact_time_s'] is not None
    assert up['contact_defender_id'] == s['defender_id']
    assert up['tracked_min_gap_m'] <= 1.05


def test_postpass_reaction_lags_precommitted_movement():
    s = scene()
    assert defender_position(s, 'up', .55, 'pre')['y'] < defender_position(s, 'up', .55, 'post')['y']


def test_left_and_right_attack_mirror_with_same_results():
    s = scene()
    mirrored = deepcopy(s)
    mirrored['attack_direction'] = 'left'
    for p in mirrored['players']:
        p['x'] = 105.0 - p['x']
        p['vx'] = -p.get('vx', 0)
    for phase in ('pre','post'):
        for action in ('up', 'hold', 'backward', 'forward-up'):
            l = evaluate_hybrid(s, action, phase)
            r = evaluate_hybrid(mirrored, action, phase)
            assert l['score'] == r['score']
            assert isclose(l['position']['x'] + r['position']['x'], 105, abs_tol=.003)


def test_invalid_missing_observed_target_rejected():
    s = scene()
    del s['observed_pass_target_id']
    with pytest.raises(ValueError, match='Observed pass target'):
        analyze_hybrid(s)


def test_studio_player_api_replaces_legacy_analysis_routes():
    client = TestClient(app)
    assert client.get('/health').json()['version'] == '0.9.16'
    assert client.get('/api/hybrid/central-through-ball').status_code == 404
    assert client.get('/api/analyze/central-through-ball').status_code == 404
    payload = client.get('/api/player-analysis/central-through-ball/d4').json()
    assert payload['post_pass']['options']
    assert 'AFTER THE PASS' in client.get('/studio').text


def test_teammate_scripted_movement_changes_position_over_time():
    s = scene()
    teammate = next(p for p in s['players'] if p['id'] == 'd5')
    assert scripted_position(teammate, 0)['y'] == teammate['y']
    assert scripted_position(teammate, 2)['x'] == pytest.approx(teammate['x'] + 2 * teammate['vx'])
    assert scripted_position(teammate, 100) == scripted_position(teammate, 3)


def test_pass_is_led_to_running_receiver_and_geometry_fixed_across_choices():
    s = scene()
    moving = pass_geometry(s, 'a9')
    receiver = next(p for p in s['players'] if p['id'] == 'a9')
    assert moving['end']['x'] > receiver['x']
    assert moving['end']['y'] < receiver['y']
    for phase in ('pre','post'):
        positions = [lane(evaluate_hybrid(s, action, phase))['pass_end']
                     for action in ('hold','up','down')]
        assert positions.count(positions[0]) == len(positions)


def test_background_positions_identical_for_every_counterfactual_action():
    s = scene()
    for phase in ('pre', 'post'):
        for act in ('hold','up','down'):
            result = evaluate_hybrid(s, act, phase)
            trajectory = result['player_trajectories']['d5']
            for sample in trajectory[::15]:
                expected = scripted_position(next(p for p in s['players'] if p['id']=='d5'), sample['t'])
                assert sample['x'] == pytest.approx(expected['x'], abs=.001)
                assert sample['y'] == pytest.approx(expected['y'], abs=.001)


def test_moving_teammate_changes_team_coverage_and_tracked_marginal_effect():
    s = scene()
    moving = lane(evaluate_hybrid(s, 'up','pre'), 'a11')
    stopped = deepcopy(s)
    teammate = next(p for p in stopped['players'] if p['id']=='d5')
    teammate['vx'] = 0
    teammate['vy'] = 0
    static = lane(evaluate_hybrid(stopped,'up','pre'), 'a11')
    assert moving['other_defenders_coverage_index'] != static['other_defenders_coverage_index']
    assert moving['tracked_min_gap_m'] == pytest.approx(static['tracked_min_gap_m'])


def test_marking_assignment_only_affects_assigned_receiving_route():
    s = scene()
    marked = lane(evaluate_hybrid(s,'hold','pre'), 'a11')
    assert next(x for x in marked['defenders'] if x['defender_id']=='d5')['receiver_pressure_index'] > 0
    unassigned = deepcopy(s)
    next(p for p in unassigned['players'] if p['id']=='d5').pop('marking_target_id')
    unmarked = lane(evaluate_hybrid(unassigned,'hold','pre'),'a11')
    assert marked['other_defenders_coverage_index'] > unmarked['other_defenders_coverage_index']
    a9 = lane(evaluate_hybrid(s,'hold','pre'),'a9')
    assert next(x for x in a9['defenders'] if x['defender_id']=='d5')['receiver_pressure_index'] == 0


def test_role_penalty_is_separate_from_pass_threat_index():
    s = scene()
    hold = evaluate_hybrid(s,'hold','pre')
    down = evaluate_hybrid(s,'down','pre')
    assert hold['role_release_penalty'] == 0
    assert down['role_release_penalty'] > 0
    assert down['score'] == pytest.approx(down['pass_threat_index'] + down['role_release_penalty'], abs=.00002)


def test_ill_formed_velocity_and_marking_assignment_rejected():
    s = scene()
    next(p for p in s['players'] if p['id']=='d5')['vx'] = 20
    with pytest.raises(ValueError, match='velocity'):
        analyze_hybrid(s)
    s = scene()
    next(p for p in s['players'] if p['id']=='d5')['marking_target_id'] = 'missing'
    with pytest.raises(ValueError, match='marking'):
        analyze_hybrid(s)


def test_post_phase_pass_end_remains_same_as_pre_phase():
    s = scene()
    for action in ('up','down','hold'):
        pre = lane(evaluate_hybrid(s, action, 'pre'))
        post = lane(evaluate_hybrid(s, action, 'post'))
        assert pre['pass_start'] == post['pass_start']
        assert pre['pass_end'] == post['pass_end']

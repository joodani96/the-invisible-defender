"""Player selection, model invariants and broadcast-demo contract (v0.6)."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.data import SCENARIOS
from app.engine import ACTIONS
from app.hybrid import defender_position
from app.main import app
from app.player_analysis import analyze_player, selectable_defenders


def scene(sid='central-through-ball'):
    return deepcopy(next(s for s in SCENARIOS if s['id'] == sid))


def selected_path(result, phase='pre_pass'):
    return result[phase]['observed_option']


def test_every_outfield_defender_is_selectable_not_the_goalkeeper():
    for s in SCENARIOS:
        ids = {d['id'] for d in selectable_defenders(s)}
        assert len(ids) >= 3
        assert 'gk' not in ids
        assert ids == {p['id'] for p in s['players'] if p['team']=='defense' and not p.get('is_goalkeeper')}
        for defender_id in ids:
            result = analyze_player(s, defender_id)
            assert result['selected_defender']['id'] == defender_id
            assert result['scene']['defender_id'] == defender_id
            assert result['actual_action'] == 'observed'
            assert len(result['pre_pass']['options']) == 9
            assert len(result['post_pass']['options']) == 9
            assert set(o['action'] for o in result['pre_pass']['options']) == set(ACTIONS)


def test_source_scene_does_not_change_on_selection():
    s = scene()
    original = deepcopy(s)
    analyze_player(s, 'd5')
    assert s == original


def test_selection_does_not_rewrite_authored_match_baseline():
    s = scene()
    d4 = analyze_player(s, 'd4')
    d5 = analyze_player(s, 'd5')
    # The same full synthetic match must be replayed regardless of focus.
    assert selected_path(d4)['pass_threat_index'] == pytest.approx(selected_path(d5)['pass_threat_index'],abs=.00001)
    assert selected_path(d4)['offside'] == selected_path(d5)['offside']
    assert selected_path(d4)['trajectory'] == selected_path(d5)['player_trajectories']['d4']
    assert selected_path(d5)['trajectory'] == selected_path(d4)['player_trajectories']['d5']


def test_tested_choices_do_not_move_teammates_or_unchosen_players():
    r = analyze_player(scene(), 'd5')
    chosen = r['pre_pass']['options']
    for alternative in chosen:
        assert alternative['player_trajectories'] == chosen[0]['player_trajectories']
        assert alternative['player_trajectories']['d4'] == selected_path(r)['player_trajectories']['d4']


def test_original_action_and_counterfactuals_can_be_compared_honestly():
    r = analyze_player(scene(), 'd4')
    for phase in ('pre_pass', 'post_pass'):
        p = r[phase]
        assert p['actual_score'] == p['observed_option']['score']
        assert p['baseline_score'] == next(x['score'] for x in p['options'] if x['action']=='hold')
        assert p['defensive_impact'] == pytest.approx(p['baseline_score']-p['actual_score'],abs=.00002)
        assert p['decision_gap'] == pytest.approx(max(0,p['actual_score']-p['optimal_score']),abs=.00002)
        assert p['optimal_score'] == min(p['observed_option']['score'],*(x['score'] for x in p['options']))
        assert p['relevance'] in ('low_model_influence','meaningful_model_variation')


def test_distant_player_reports_low_model_influence():
    r = analyze_player(scene(), 'd2')['pre_pass']
    assert r['relevance']=='low_model_influence'
    assert r['decision_gap']==0


def test_offside_trap_changes_when_line_setting_defender_drops_back():
    r=analyze_player(scene('offside-trap'),'d4')['pre_pass']
    hold=next(x for x in r['options'] if x['action']=='hold')
    back=next(x for x in r['options'] if x['action']=='backward')
    assert hold['offside']['target_statuses']['a9']['offside_position']
    assert not back['offside']['target_statuses']['a9']['offside_position']
    assert hold['score'] < back['score']


def test_post_pass_counterfactuals_keep_same_offside_snapshot():
    s=scene('offside-trap')
    r=analyze_player(s,'d5')['post_pass']
    baseline=r['observed_option']['offside']
    assert all(o['offside']==baseline for o in r['options'])
    configured=analyze_player(s,'d5')['scene']
    t=s['pass_launch_delay_s']
    fixed=defender_position(configured,'observed',t,'post')
    assert all(defender_position(configured,a,t,'post')['x']==pytest.approx(fixed['x']) for a in ACTIONS)
    assert all(defender_position(configured,a,t,'post')['y']==pytest.approx(fixed['y']) for a in ACTIONS)


def test_api_and_dropdown_contract():
    client=TestClient(app)
    assert client.get('/health').json()['version']=='0.9.16'
    lst=client.get('/api/scenarios').json()
    assert all(s['default_defender_id'] in {d['id'] for d in s['selectable_defenders']} for s in lst)
    assert client.get('/api/player-analysis/central-through-ball/d5').json()['selected_defender']['id']=='d5'
    assert client.get('/api/player-analysis/central-through-ball/gk').status_code == 404
    assert client.get('/api/player-analysis/unknown/d4').status_code == 404
    assert client.get('/api/player-analysis/central-through-ball/nonexistent').status_code == 404
    demo=client.get('/studio').text
    assert 'FOCUS DEFENDER' in demo
    assert 'id="pitch"' in demo
    assert 'id="moves"' in demo

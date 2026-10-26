"""IFAB Law 11-inspired synthetic point-position offside tests."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.data import SCENARIOS
from app.hybrid import analyze_hybrid, evaluate_hybrid, scripted_position
from app.offside import offside_snapshot
from app.main import app


def sample(sid):
    return deepcopy(next(s for s in SCENARIOS if s['id'] == sid))


def lane(o, target='a9'):
    return next(l for l in o['passes'] if l['target_id'] == target)


def test_offside_trap_dropping_back_plays_striker_onside():
    s = sample('offside-trap')
    hold = evaluate_hybrid(s, 'hold', 'pre')
    back = evaluate_hybrid(s, 'backward', 'pre')
    assert hold['offside']['offside_line_x'] == 90
    assert back['offside']['offside_line_x'] > 90.5
    assert lane(hold)['offside_position'] is True
    assert lane(hold)['pass_choice_index'] == 0
    assert lane(hold)['weighted_threat'] == 0
    assert lane(hold)['unfiltered_conditional_threat'] > 0
    assert lane(back)['eligible_target'] is True
    assert lane(back)['pass_choice_index'] > 0
    assert back['score'] > hold['score']


def test_onside_runner_stays_legal_after_crossing_line_in_flight():
    s = sample('onside-run')
    o = evaluate_hybrid(s, 'hold', 'pre')
    l = lane(o)
    assert l['offside_position'] is False
    launch = s['pass_launch_delay_s']
    runner = next(p for p in s['players'] if p['id']=='a9')
    assert scripted_position(runner, launch)['x'] < o['offside']['offside_line_x']
    assert scripted_position(runner, launch + l['flight_time_s'])['x'] > o['offside']['offside_line_x']
    assert l['conditional_threat'] > 0


def test_post_decisions_share_same_offside_snapshot_and_fixed_receiver():
    s = sample('offside-trap')
    base = evaluate_hybrid(s, 'hold', 'post')
    for choice in ('hold', 'forward', 'backward', 'up', 'down'):
        other = evaluate_hybrid(s, choice, 'post')
        assert other['offside'] == base['offside']
        assert lane(other)['offside_position'] is False
        assert lane(other)['pass_choice_index'] == 1


def test_post_illegal_observed_target_has_zero_legal_direct_threat():
    s = sample('offside-trap')
    s['actual_action']='hold'
    o = evaluate_hybrid(s, 'backward', 'post')
    assert lane(o)['offside_position'] is True
    assert lane(o)['unfiltered_conditional_threat'] > 0
    assert lane(o)['conditional_threat'] == 0
    assert o['pass_threat_index'] == 0
    assert o['score'] == 0


def test_second_last_opponent_and_ball_are_both_used():
    d = [{'id':'gk','x':103,'team':'defense'}, {'id':'d','x':85,'team':'defense'}, {'id':'d2','x':60,'team':'defense'}]
    receiver = [{'id':'r','x':90}]
    a = offside_snapshot(defenders=d, ball={'x':70}, targets=receiver, attack_direction='right')
    assert a['second_last_defender_x'] == 85
    assert a['target_statuses']['r']['offside_position']
    b = offside_snapshot(defenders=d, ball={'x':93}, targets=receiver, attack_direction='right')
    assert b['offside_line_x'] == 93
    assert not b['target_statuses']['r']['offside_position']


def test_level_onside_halfway_onside_and_restart_exempt():
    ds = [{'id':'g','team':'defense','x':100},{'id':'d','team':'defense','x':88}]
    targets=[{'id':'atline','x':88},{'id':'ownhalf','x':52.5},{'id':'off','x':90}]
    base=offside_snapshot(defenders=ds, ball={'x':60}, targets=targets, attack_direction='right')
    assert base['target_statuses']['atline']['eligible_target']
    assert base['target_statuses']['ownhalf']['eligible_target']
    assert base['target_statuses']['off']['offside_position']
    for event in ['goal_kick','throw_in','corner_kick']:
        exempt=offside_snapshot(defenders=ds,ball={'x':60},targets=targets,
                                attack_direction='right', event_type=event)
        assert exempt['event_exempt']
        assert all(v['eligible_target'] for v in exempt['target_statuses'].values())


def test_left_attack_and_ball_close_to_goal_are_handled():
    ds=[{'id':'g','team':'defense','x':4},{'id':'d','team':'defense','x':14}]
    r=offside_snapshot(defenders=ds,ball={'x':35},targets=[{'id':'a','x':13}],attack_direction='left')
    assert r['offside_line_x']==14
    assert r['target_statuses']['a']['offside_position']
    r2=offside_snapshot(defenders=ds,ball={'x':10},targets=[{'id':'a','x':13}],attack_direction='left')
    assert r2['offside_line_x']==10
    assert not r2['target_statuses']['a']['offside_position']


def test_mirror_scene_identical_offside_and_scores():
    s=sample('offside-trap')
    mirrored=deepcopy(s)
    mirrored['attack_direction']='left'
    for p in mirrored['players']:
        p['x']=105-p['x']
        p['vx']=-p.get('vx',0)
    for act in ('hold','backward','forward'):
        a=evaluate_hybrid(s,act,'pre'); b=evaluate_hybrid(mirrored,act,'pre')
        assert a['score']==b['score']
        assert a['offside']['offside_line_x']+b['offside']['offside_line_x']==pytest.approx(105)
        assert lane(a)['offside_position']==lane(b)['offside_position']


def test_keeper_required_to_prevent_false_positive_backline():
    s=sample('offside-trap')
    s['players']=[p for p in s['players'] if not p.get('is_goalkeeper')]
    with pytest.raises(ValueError, match='goalkeeper'):
        analyze_hybrid(s)


def test_api_new_scenarios_include_rule_diagnostics():
    client=TestClient(app)
    assert client.get('/health').json()['version']=='0.9.16'
    scene_ids=[s['id'] for s in client.get('/api/scenarios').json()]
    assert 'offside-trap' in scene_ids and 'onside-run' in scene_ids
    result=client.get('/api/player-analysis/offside-trap/d4').json()
    assert result['model'].endswith('v0.7')
    assert result['pre_pass']['options'][0]['offside']['target_statuses']
    demo=client.get('/studio').text
    assert 'Offside line' in demo

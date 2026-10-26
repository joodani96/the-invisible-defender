"""v0.7 explainability contract: never invent numbers or change the model."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.data import SCENARIOS
from app.hybrid import analyze_hybrid
from app.player_analysis import analyze_player


@pytest.mark.parametrize('scene', SCENARIOS, ids=lambda s: s['id'])
def test_every_scene_and_defender_supports_grounded_explanations(scene):
    for d in [p['id'] for p in scene['players'] if p['team']=='defense' and not p.get('is_goalkeeper')]:
        result = analyze_player(scene, d)
        for phase in ('pre_pass', 'post_pass'):
            summary = result[phase]
            baseline = next(o for o in summary['options'] if o['action']=='hold')
            assert set(summary['explanations']) == {*(x['action'] for x in summary['options']), 'observed'}
            for action, evidence in summary['explanations'].items():
                option=next(x for x in [*summary['options'],summary['observed_option']] if x['action']==action)
                assert abs(evidence['selected_score'] - option['score']) < 1e-9
                assert abs(evidence['hold_score'] - baseline['score']) < 1e-9
                assert abs(evidence['reduction_vs_hold']-(baseline['score']-option['score'])) < 1e-9
                assert abs(evidence['reconstructed_score']-option['score']) <= 0.00005
                assert abs(sum(c['reduction_vs_hold'] for c in evidence['components'])-evidence['reduction_vs_hold']) <= 0.00005
                assert 'not xG' in evidence['model_limitations']
                assert 'Defender #' in evidence['commentary']['fan']
                assert 'not a guaranteed match outcome' in evidence['commentary']['fan']
                assert 'MODEL COMPARISON' in evidence['commentary']['analyst']
                assert result['commentary_generator'].startswith('deterministic_')


def test_offside_changed_is_only_reported_if_factual():
    scene=next(s for s in SCENARIOS if s['id']=='offside-trap')
    result=analyze_player(scene,scene['defender_id'])
    summary=result['pre_pass']
    assert summary['explanations']['backward']['offside_status_changed']
    assert not summary['explanations']['hold']['offside_status_changed']
    for e in summary['explanations'].values():
        changed=any(
            x['offside_position'] != next(p for p in next(o for o in summary['options'] if o['action']=='hold')['passes'] if p['target_id']==x['target_id'])['offside_position']
            for x in next(o for o in [*summary['options'],summary['observed_option']] if o['action']==e['action'])['passes']
        )
        assert e['offside_status_changed'] == changed


def test_post_pass_commentary_never_claims_to_change_target():
    scene=SCENARIOS[0]
    r=analyze_player(scene,scene['defender_id'])
    for ev in r['post_pass']['explanations'].values():
        assert 'cannot retroactively choose another passing lane' in ev['commentary']['fan']
        assert not ev['offside_status_changed']


def test_explanations_do_not_mutate_original_scores():
    s=SCENARIOS[0]
    old=analyze_hybrid(deepcopy({**s,'player_centric':True,'movement_frame':'body','observed_primary_defender_id':s['defender_id'],'observed_primary_action':s['actual_action']}))
    new=analyze_player(s,s['defender_id'])
    for phase in ('pre_pass','post_pass'):
        assert [o['score'] for o in old[phase]['options']] == [o['score'] for o in new[phase]['options']]
        assert old[phase]['observed_option']['score'] == new[phase]['observed_option']['score']


def test_http_contract_exposes_all_options_and_health():
    client=TestClient(app)
    assert client.get('/health').json()['version']=='0.9.16'
    for s in SCENARIOS:
        for p in s['players']:
            if p['team']!='defense' or p.get('is_goalkeeper'):continue
            response=client.get(f"/api/player-analysis/{s['id']}/{p['id']}")
            assert response.status_code==200
            body=response.json()
            assert body['pre_pass']['explanations']['observed']['action']=='observed'
            assert body['post_pass']['explanations']['hold']['action']=='hold'
    assert client.get('/studio').status_code==200

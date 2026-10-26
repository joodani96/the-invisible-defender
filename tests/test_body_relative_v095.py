"""Body-relative choices must be REAL resimulations, not relabelled scores."""
from math import hypot, cos, sin, radians
from fastapi.testclient import TestClient
from app.main import app
from app.data import SCENARIOS
from app.player_analysis import analyze_player
from app.hybrid import candidate_direction, defender_position, observed_position

client=TestClient(app)

def close(a,b,eps=.012):
    assert abs(a-b)<eps,(a,b)

def test_local_compass_tracks_synthetic_body_heading():
    for scene in SCENARIOS:
        for p in scene['players']:
            if p['team']!='defense' or p.get('is_goalkeeper'):continue
            result=analyze_player(scene,p['id'])
            assert result['movement_frame']=='body'
            heading=result['decision_facing_deg']['pre']
            configured=result['scene']
            x,y=candidate_direction(configured,'forward','pre')
            close(x,cos(radians(heading)),.0001)
            close(y,sin(radians(heading)),.0001)
            lx,ly=candidate_direction(configured,'up','pre')
            close(x*lx+y*ly,0,.0001)
            close(x*ly-y*lx,-1,.0001)
            rx,ry=candidate_direction(configured,'down','pre')
            close(lx+rx,0,.0001);close(ly+ry,0,.0001)
            for phase in ('pre_pass','post_pass'):
                assert len(result[phase]['options'])==9
                assert result[phase]['observed_option']['label']=='Authored movement'

def test_forward_position_matches_local_vector_after_reaction():
    d=analyze_player(SCENARIOS[0],'d2')
    config=d['scene'];p=next(x for x in config['players'] if x['id']=='d2')
    a=defender_position(config,'forward',.45,'pre')
    vx,vy=candidate_direction(config,'forward','pre')
    close(a['x']-p['x'],vx*.75,1e-6)
    close(a['y']-p['y'],vy*.75,1e-6)

def test_post_choices_start_at_same_original_observed_pose():
    d=analyze_player(SCENARIOS[0],'d4')
    cfg=d['scene'];p=next(x for x in cfg['players'] if x['id']=='d4')
    launch=cfg['pass_launch_delay_s']
    base=observed_position(cfg,p,launch)
    for o in d['post_pass']['options']:
        x=defender_position(cfg,o['action'],launch,'post')
        close(x['x'],base['x'],1e-9);close(x['y'],base['y'],1e-9)
    assert d['decision_facing_deg']['post'] != d['decision_facing_deg']['pre']

def test_original_does_not_depend_on_body_facing_change():
    from copy import deepcopy
    original=SCENARIOS[0]
    variant=deepcopy(original)
    next(p for p in variant['players'] if p['id']=='d4')['body_facing_deg']=72
    a,b=analyze_player(original,'d4'),analyze_player(variant,'d4')
    assert a['pre_pass']['observed_option']['score']==b['pre_pass']['observed_option']['score']
    assert [o['score'] for o in a['pre_pass']['options']] != [o['score'] for o in b['pre_pass']['options']]

def test_3d_2d_endpoints_include_orientation_and_click_targets():
    result=client.get('/api/player-analysis/central-through-ball/d4').json()
    assert result['movement_frame']=='body'
    assert set(result['decision_facing_deg'])=={'pre','post'}
    html=client.get('/static/viewer.html').text
    assert 'id="move-pad"' in html
    assert 'GROUND TILES' in html
    js=client.get('/static/defender3d.js').text
    assert 'metadata={decisionAction:opt.action}' in js
    assert 'drawDecisionMarkers();updatePositions()' in js
    assert 'selected-ring' not in js
    assert 'makeBackNumber' in js
    assert 'D.grid()' in js
    assert 'decision_facing_deg' in client.get('/static/demo.html').text if client.get('/static/demo.html').status_code==200 else True

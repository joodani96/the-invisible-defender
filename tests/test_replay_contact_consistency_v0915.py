"""Regression against the 34:18 first-touch illusion in v0.9.16.

No xG claims: this verifies deterministic *geometric* contact only.
"""
from math import hypot

from fastapi.testclient import TestClient
from app.main import app
from app.hybrid import CONTACT_RADIUS_M, defender_position, pass_geometry
from app.data import SCENARIOS
from app.player_analysis import analyze_player


def test_reported_first_contact_matches_ball_and_defender_geometry():
    scene = next(s for s in SCENARIOS if s['id'] == 'central-through-ball')
    data = analyze_player(scene, 'd4')
    working = data['scene']
    for action in ('down', 'forward-down', 'hold'):
        option = next(o for o in data['post_pass']['options'] if o['action'] == action)
        pass_info = option['observed_pass']
        contact = pass_info['contact_time_s']
        if action in ('hold', 'forward-down'):
            assert contact is None
            assert pass_info['tracked_min_gap_m'] > CONTACT_RADIUS_M
            continue
        assert pass_info['contact_defender_id'] == 'd4'
        frac = pass_info['contact_fraction']
        x = pass_info['pass_start']['x'] + frac * (pass_info['pass_end']['x'] - pass_info['pass_start']['x'])
        y = pass_info['pass_start']['y'] + frac * (pass_info['pass_end']['y'] - pass_info['pass_start']['y'])
        defender = defender_position(working,action,contact,'post')
        assert hypot(x-defender['x'],y-defender['y']) <= CONTACT_RADIUS_M + .01
        assert data['assumptions']['pass_launch_delay_s'] < contact < data['assumptions']['pass_launch_delay_s']+pass_info['flight_time_s']


def test_both_alternatives_contact_and_scores_are_deterministic_but_distinct():
    scene = next(s for s in SCENARIOS if s['id'] == 'central-through-ball')
    one = analyze_player(scene,'d4')['post_pass']['options']
    two = analyze_player(scene,'d4')['post_pass']['options']
    for action in ('down','forward-down'):
        left = next(o for o in one if o['action'] == action)
        right = next(o for o in two if o['action'] == action)
        assert left['score'] == right['score']
        assert left['observed_pass']['contact_time_s'] == right['observed_pass']['contact_time_s']
    plain = next(o for o in one if o['action']=='down')
    diagonal = next(o for o in one if o['action']=='forward-down')
    # The tighter geometric radius no longer mislabels Forward-right near misses as interceptions.
    assert diagonal['observed_pass']['contact_time_s'] is None
    assert plain['observed_pass']['contact_time_s'] is not None
    assert plain['score'] < diagonal['score']
    assert plain['observed_pass']['tracked_min_gap_m'] < diagonal['observed_pass']['tracked_min_gap_m']


def test_contact_metadata_stable_over_http_repeated_requests():
    client=TestClient(app)
    url='/api/player-analysis/central-through-ball/d4'
    a=client.get(url).json()
    b=client.get(url).json()
    for action in ('down','forward-down','hold'):
        def opts(d):return next(o for o in d['post_pass']['options'] if o['action']==action)
        assert opts(a)['observed_pass'] == opts(b)['observed_pass']
        assert opts(a)['score'] == opts(b)['score']

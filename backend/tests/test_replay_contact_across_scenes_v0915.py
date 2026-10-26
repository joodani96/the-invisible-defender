"""Modelled contact is always a same-time proximity event across showcase scenes."""
from math import hypot

import pytest
from app.data import SCENARIOS
from app.player_analysis import analyze_player
from app.hybrid import CONTACT_RADIUS_M


def _sample(traj, t):
    if t <= traj[0]['t']:
        return traj[0]
    for i in range(1,len(traj)):
        b=traj[i]
        if t<=b['t']:
            a=traj[i-1]
            q=(t-a['t'])/max(1e-9,b['t']-a['t'])
            return {'x':a['x']+q*(b['x']-a['x']), 'y':a['y']+q*(b['y']-a['y'])}
    return traj[-1]


@pytest.mark.parametrize('scenario_id',[s['id'] for s in SCENARIOS])
def test_contact_consistent_with_animation_geometry(scenario_id):
    scene=next(s for s in SCENARIOS if s['id']==scenario_id)
    focus=scene['defender_id']
    data=analyze_player(scene,focus)
    launch=data['assumptions']['pass_launch_delay_s']
    for option in data['post_pass']['options']:
        p=option['observed_pass']
        contact=p['contact_time_s']
        if contact is None:
            assert p['contact_defender_id'] is None
            assert p['contact_fraction'] is None
            continue
        assert launch<=contact<=launch+p['flight_time_s']+.00002
        fraction=p['contact_fraction']
        assert 0<=fraction<=1
        ball={'x':p['pass_start']['x']+fraction*(p['pass_end']['x']-p['pass_start']['x']),
              'y':p['pass_start']['y']+fraction*(p['pass_end']['y']-p['pass_start']['y'])}
        contact_id=p['contact_defender_id']
        trajectory=option['trajectory'] if contact_id==focus else option['player_trajectories'][contact_id]
        defender=_sample(trajectory,contact)
        # trajectory is serialized at 61 uniformly spaced samples: allow an
        # interpolation error of 0.10 m relative to continuous physics.
        assert hypot(defender['x']-ball['x'],defender['y']-ball['y'])<=CONTACT_RADIUS_M+.10

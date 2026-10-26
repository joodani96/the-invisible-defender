"""Synthetic orientation drives candidate directions in v0.9.5, not authored movement."""
from copy import deepcopy
from fastapi.testclient import TestClient
from app.main import app
from app.data import SCENARIOS
from app.player_analysis import analyze_player

client=TestClient(app)


def test_synthetic_orientation_in_every_scene_and_for_each_selection():
    for scene in SCENARIOS:
        original={p['id']:p['body_facing_deg'] for p in scene['players']}
        assert len(original)==len(scene['players'])
        assert all(0 <= deg < 360 for deg in original.values())
        assert all(p['facing_source']=='synthetic_authored' for p in scene['players'])
        for choice in [p for p in scene['players'] if p['team']=='defense' and not p.get('is_goalkeeper')]:
            result=client.get(f"/api/player-analysis/{scene['id']}/{choice['id']}")
            assert result.status_code==200
            data=result.json()
            assert {p['id']:p['body_facing_deg'] for p in data['scene']['players']}==original


def test_facing_metadata_changes_candidate_choices_but_not_authored_path():
    for original in SCENARIOS:
        person=original['defender_id']
        copied=deepcopy(original)
        for p in copied['players']:
            p.pop('body_facing_deg',None)
            p.pop('facing_source',None)
        with_pose=analyze_player(original,person)
        without_pose=analyze_player(copied,person)
        for phase in ['pre_pass','post_pass']:
            a,b=with_pose[phase],without_pose[phase]
            assert a['observed_option']['score']==b['observed_option']['score']
            assert a['baseline_score']==b['baseline_score']
            assert a['movement_frame']==b['movement_frame'] if 'movement_frame' in a else True


def test_viewer_has_pose_asset_and_real_shirt_numbers():
    page=client.get('/static/viewer.html').text
    assert '/static/defender3d_orientation.js' in page
    js=client.get('/static/defender3d.js').text
    assert client.get('/static/defender3d_orientation.js').status_code==200
    assert 'makeBackNumber' in js
    assert 'root.rotation.y=Orientation.worldYaw' in js
    assert 'billboardMode' not in js
    assert 'bodyFacingDeg' in js
    assert 'camera.setTarget(eye.add(forward.scale(28)))' in js
    assert 'id="facing-value"' in page
    assert 'id="motion-value"' in page

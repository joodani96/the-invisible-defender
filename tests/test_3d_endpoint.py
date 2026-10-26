"""The 3D viewer is a thin presentation layer over the existing player API."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_3d_route_and_static_resources():
    page = client.get('/static/viewer.html')
    assert page.status_code == 200
    assert 'Babylon.js' in page.text
    assert 'pitch3d' in page.text
    assert '/static/defender3d.js' in page.text
    for path, mime in [('/static/defender3d.css', 'text/css'), ('/static/defender3d.js','javascript')]:
        response = client.get(path)
        assert response.status_code == 200
        assert mime in response.headers['content-type']


def test_3d_uses_same_selectable_defender_data():
    cases = client.get('/api/scenarios').json()
    assert len(cases) >= 3
    for scenario in cases:
        for defender in scenario['selectable_defenders']:
            resp = client.get(f"/api/player-analysis/{scenario['id']}/{defender['id']}")
            assert resp.status_code == 200
            data = resp.json()
            assert defender['id'] == data['scene']['defender_id']
            for phase in ['pre_pass', 'post_pass']:
                option = data[phase]['observed_option']
                assert len(option['trajectory']) > 1
                assert len(option['player_trajectories']) >= 3
                assert option['observed_pass']['flight_time_s'] > 0
                assert 'offside_line_x' in option['offside']


def test_health_version():
    assert client.get('/health').json()['version'] == '0.9.16'

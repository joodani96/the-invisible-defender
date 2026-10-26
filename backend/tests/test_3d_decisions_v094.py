"""v0.9.4 UI integration keeps the same defensive backend and exposes all choices."""
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_nine_valid_actions_across_all_scenarios_and_defenders():
    for scene in client.get('/api/scenarios').json():
        for defender in scene['selectable_defenders']:
            response=client.get(f"/api/player-analysis/{scene['id']}/{defender['id']}")
            assert response.status_code==200
            data=response.json()
            for phase in ('pre_pass','post_pass'):
                result=data[phase]
                options=result['options']
                assert len(options)==9
                assert len(set(item['action'] for item in options))==9
                assert result['best_tested_action'] in {item['action'] for item in options}
                assert all(isinstance(item['score'],float) for item in options)

def test_3d_html_contains_broadcast_decision_pad():
    page=client.get('/static/viewer.html')
    assert page.status_code==200
    assert 'id="move-pad"' in page.text
    assert 'id="show-nine-paths"' in page.text
    assert '/static/defender3d_decisions.js' in page.text
    assert client.get('/static/defender3d_decisions.js').status_code==200

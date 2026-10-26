"""Evidence-driven highlights remain presentation-only and use the same model endpoints."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_highlight_assets_and_controls_are_served():
    page = client.get('/static/viewer.html')
    assert page.status_code == 200
    for ident in ('show-highlights', 'follow-commentary', 'movement-compare',
                  'evidence-buttons', 'freeze', 'generate-3d-commentary', 'highlight-banner'):
        assert f'id="{ident}"' in page.text
    assert '/static/defender3d_highlights.js' in page.text
    response = client.get('/static/defender3d_highlights.js')
    assert response.status_code == 200
    assert 'javascript' in response.headers['content-type']
    assert 'planEvidence' in response.text
    assert client.get('/health').json()['version'] == '0.9.16'


def test_all_scenarios_have_grounded_explanation_components():
    for scenario in client.get('/api/scenarios').json():
        selected = scenario['default_defender_id']
        data = client.get(f"/api/player-analysis/{scenario['id']}/{selected}").json()
        for phase in ('pre_pass', 'post_pass'):
            summary = data[phase]
            for o in [summary['observed_option'], *summary['options']]:
                explanation = summary['explanations'][o['action']]
                ids = {p['target_id'] for p in o['passes']}
                for component in explanation['components']:
                    if component['kind'] == 'pass':
                        assert component['key'].removeprefix('pass:') in ids

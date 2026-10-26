"""Contract checks: a lower-clutter 3D interface does not remove model controls."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_broadcast_and_analyst_controls_exist():
    text = client.get('/static/viewer.html').text
    assert 'id="broadcast-mode"' in text
    assert 'id="analyst-mode"' in text
    assert 'id="watch-authored"' in text
    assert 'id="watch-best"' in text
    assert 'id="broadcast-selected"' in text
    assert 'class="technical-inspector"' in text


def test_ai_commentary_is_optional_and_details_available():
    text = client.get('/static/viewer.html').text
    assert 'id="generate-3d-commentary"' in text
    assert 'id="commentary-excerpt"' in text
    assert 'id="3d-commentary"' in text
    assert 'id="follow-commentary" checked' not in text


def test_3d_broadcast_version_and_assets():
    assert client.get('/health').json()['version']=='0.9.16'
    js = client.get('/static/defender3d.js').text
    assert "cameraMode: 'follow'" in js
    assert "setUiMode('broadcast')" in js
    assert 'broadcast-hold' in js
    assert 'Generated' not in js[:100]  # no fake model results in presentation code

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_only_studio_and_about_are_public_pages():
    for route in ('/studio', '/about'):
        assert client.get(route).status_code == 200
    assert client.get('/').history[0].headers['location'] == '/studio'
    for route in ('/demo', '/3d'):
        assert client.get(route).status_code == 404


def test_icon_navigation_and_research_sources():
    studio = client.get('/studio').text
    about = client.get('/about').text
    assert 'href="/about"' in studio
    assert 'src="/static/shield.svg"' in studio
    assert 'rel="icon"' in studio
    assert 'ID<span>↗' not in studio
    assert 'UNOFFICIAL HACKATHON DEMO' not in studio
    assert 'Both views use the same Python tactical model' not in studio
    assert '/demo' not in studio and '/3d?' not in studio
    assert 'Offside Control' in about
    assert 'DEFCON' in about and 'Cover Shadows' in about
    assert 'not xG' in about
    assert client.get('/static/shield.svg').status_code == 200


def test_internal_viewer_and_all_local_scripts_load():
    viewer = client.get('/static/viewer.html')
    assert viewer.status_code == 200
    assert 'defender3d_stadium.js' in viewer.text
    for asset in ('studio.js', 'studio_core.js', 'defender3d.js', 'defender3d_stadium.js', 'viewer.html'):
        assert client.get('/static/' + asset).status_code == 200

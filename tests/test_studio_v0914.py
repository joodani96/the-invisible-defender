from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)


def test_unified_studio_routes_and_embedded_assets():
    page=client.get('/studio')
    assert page.status_code == 200
    assert 'text/html' in page.headers['content-type']
    for key in ('scenario','defender','pre','post','viewer','timeline','pitch','moves','coverage','generate','commentary'):
        assert f'id="{key}"' in page.text
    assert '/static/viewer.html?embedded=1&amp;studio=1' in page.text
    for asset in ('studio.css','studio.js','studio_core.js','defender3d_stadium.js','defender3d.js'):
        response=client.get('/static/'+asset+'?v=0914')
        assert response.status_code == 200,asset
    assert '03 / EVIDENCE-DRIVEN OVERLAYS' not in page.text
    assert client.get('/',follow_redirects=False).headers['location']=='/studio'
    assert client.get('/studio').status_code==200
    assert client.get('/static/viewer.html').status_code==200


def test_sync_bridge_and_viewer_minimal_studio():
    bridge=client.get('/static/studio.js').text
    assert "tell('time',state.time)" in bridge
    assert "tell('action',action)" in bridge
    assert 'renderCoverage(o)' in bridge and 'drawPitch()' in bridge
    viewer=client.get('/static/defender3d.js').text
    assert "e.data.source==='tid-studio'" in viewer
    assert "notifyParent('ready',true)" in viewer
    assert "notifyParent('loaded'" in viewer
    css=client.get('/static/defender3d.css').text
    assert 'body.studio-embed' in css


def test_studio_player_analysis_same_data_contract():
    scene=client.get('/api/scenarios').json()[0]
    defender=scene['default_defender_id']
    result=client.get(f"/api/player-analysis/{scene['id']}/{defender}")
    assert result.status_code==200
    data=result.json()
    for phase in ('pre_pass','post_pass'):
        r=data[phase]
        assert len(r['options'])==9
        assert r['observed_option']['trajectory']
        assert r['observed_option']['player_trajectories']
        assert 'passes' in r['observed_option']

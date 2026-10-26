import asyncio
from fastapi.testclient import TestClient
import pytest

from app.ai_commentary import (packet_from_analysis, parse_json_object, select_evidence,
    verify_narrative, generate_commentary, provider_status, GroundingError)
from app.data import SCENARIOS
from app.player_analysis import analyze_player
from app.main import app


def setup_packet():
    analysis = analyze_player(SCENARIOS[0], 'd4')
    return analysis, packet_from_analysis(analysis, 'pre', 'observed')


def test_offline_status(monkeypatch):
    monkeypatch.delenv('TID_AI_PROVIDER', raising=False)
    assert provider_status()['mode'] == 'offline'


def test_evidence_package_cites_verified_components():
    analysis, packet = setup_packet()
    facts = {i['id']: i['fact'] for i in packet['evidence']}
    assert len(facts) == len(packet['evidence'])
    assert 'E2' in facts and 'E10' in facts
    assert 'not calibrated xG' in facts['E3']


def test_invalid_phase_action():
    analysis, _ = setup_packet()
    with pytest.raises(ValueError): packet_from_analysis(analysis, 'future', 'observed')
    with pytest.raises(ValueError): packet_from_analysis(analysis, 'pre', 'teleport')


def test_json_parser_fenced_and_bad():
    assert parse_json_object('```json\n{"selected_ids":["E1","E2"]}\n```')['selected_ids'] == ['E1', 'E2']
    with pytest.raises(GroundingError): parse_json_object('{"a":1} extra')


def test_selector_rejects_unknown_or_duplicates():
    _, packet = setup_packet()
    with pytest.raises(GroundingError): select_evidence('{"selected_ids":["E1","E999"]}', packet)
    with pytest.raises(GroundingError): select_evidence('{"selected_ids":["E1","E1"]}', packet)
    valid = select_evidence('{"selected_ids":["E1","E2"]}', packet)
    assert [e['id'] for e in valid] == ['E1', 'E2', 'E10']


def test_narrative_rejects_invented_numbers():
    _, packet = setup_packet()
    facts = select_evidence('{"selected_ids":["E1","E2"]}', packet)
    with pytest.raises(GroundingError):
        verify_narrative('{"commentary":"Defender moved and eliminated 87% of the danger in this situation.","evidence_ids":["E2"]}', facts)


def test_narrative_requires_citation():
    _, packet = setup_packet()
    facts = select_evidence('{"selected_ids":["E1","E2"]}', packet)
    with pytest.raises(GroundingError):
        verify_narrative('{"commentary":"The defender moved, according to the synthetic test analysis.","evidence_ids":["E77"]}', facts)


def test_offline_runner_and_mock_two_agents(monkeypatch):
    analysis, packet = setup_packet()
    monkeypatch.setenv('TID_AI_PROVIDER','offline')
    offline = asyncio.run(generate_commentary(analysis, 'pre', 'hold', 'fan'))
    assert not offline['generated_by_ai'] and offline['provider'] == 'offline'
    async def good_runner(input_packet, audience):
        evidence=select_evidence('{"selected_ids":["E1","E2"]}', input_packet)
        narration=verify_narrative('{"commentary":"This synthetic simulation compares defensive movement with holding position. The reported score is a model index, not a real match probability.","evidence_ids":["E2"]}', evidence)
        return narration, evidence
    result=asyncio.run(generate_commentary(analysis, 'pre', 'hold', 'fan',runner=good_runner))
    assert result['generated_by_ai']
    assert result['agent_steps']==['TacticalEvidenceEditor','TacticalCommentaryWriter']


def test_failed_runner_falls_back():
    analysis, packet = setup_packet()
    async def fail(input_packet, audience):
        raise GroundingError('No valid facts')
    result=asyncio.run(generate_commentary(analysis, 'pre', 'observed', 'fan',runner=fail))
    assert result['provider']=='offline' and result['validation']=='fallback'


def test_api_offline_contract(monkeypatch):
    monkeypatch.setenv('TID_AI_PROVIDER','offline')
    client=TestClient(app)
    assert client.get('/api/ai/status').status_code==200
    result=client.post('/api/commentary/central-through-ball/d4',json={'phase':'pre','action':'hold','audience':'fan'})
    assert result.status_code==200
    assert not result.json()['generated_by_ai']
    assert result.json()['evidence']


def test_api_rejects_arbitrary_input_and_404():
    client=TestClient(app)
    assert client.post('/api/commentary/central-through-ball/d4',json={'phase':'invalid','action':'hold','audience':'fan'}).status_code==422
    assert client.post('/api/commentary/central-through-ball/d4',json={'phase':'pre','action':'teleport','audience':'fan'}).status_code==422
    assert client.post('/api/commentary/missing/d4',json={'phase':'pre','action':'hold','audience':'fan'}).status_code==404


def test_diagonal_action_still_accepts_grounded_commentary(monkeypatch):
    # Directional controls expose diagonal action IDs containing hyphens.
    monkeypatch.setenv('TID_AI_PROVIDER', 'offline')
    client=TestClient(app)
    reply=client.post('/api/commentary/central-through-ball/d4',json={
        'phase':'pre', 'action':'forward-up', 'audience':'fan'})
    assert reply.status_code==200
    assert reply.json()['evidence']

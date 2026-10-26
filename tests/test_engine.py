import math
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from app.data import SCENARIOS
from app.engine import ACTIONS, analyze, distance_to_lane, evaluate, interception_probability, move
from app.main import app


def test_each_scene_has_nine_plausible_options():
    for scene in SCENARIOS:
        result = analyze(scene)
        assert len(result["options"]) == len(ACTIONS) == 9
        assert min(o["score"] for o in result["options"]) == result["optimal_score"]
        assert result["actual_score"] >= result["optimal_score"]
        for option in result["options"]:
            assert 0 <= option["score"] <= 1
            assert 0 <= option["position"]["x"] <= 105
            assert 0 <= option["position"]["y"] <= 68


def test_hold_preserves_position():
    for scene in SCENARIOS:
        p = next(p for p in scene["players"] if p["id"] == scene["defender_id"])
        o = evaluate(scene, "hold")
        assert o["position"] == {"x": p["x"], "y": p["y"]}


def test_lane_blocking_probability_decreases_when_defender_is_far_away():
    a, b = {"x": 0, "y": 0}, {"x": 30, "y": 0}
    near = {"x": 15, "y": 0}
    far = {"x": 15, "y": 10}
    assert interception_probability(near, a, b) > interception_probability(far, a, b)
    assert distance_to_lane(near, a, b)[0] == 0


def test_api_routes():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/", follow_redirects=False).headers["location"] == "/studio"
    assert "The Invisible Defender" in client.get("/", follow_redirects=True).text
    demo = client.get("/studio")
    assert demo.status_code == 200 and "The Invisible Defender" in demo.text
    assert len(client.get("/api/scenarios").json()) == 5
    assert client.get("/api/analyze/central-through-ball").status_code == 404
    assert client.get("/api/analyze/missing").status_code == 404
    demo = client.get("/studio")
    assert demo.status_code == 200
    assert "Invisible Defender" in demo.text


def test_actual_action_not_better_than_best():
    for scene in SCENARIOS:
        r = analyze(scene)
        assert r["actual_score"] >= r["optimal_score"]
        assert math.isfinite(r["baseline_score"])


def test_defender_relative_movements_rightward_attack():
    """Right-hand goal: back toward +x, step forward toward -x."""
    p = {"x": 75.0, "y": 33.0}
    assert move(p, "backward", "right")["x"] > p["x"]
    assert move(p, "forward", "right")["x"] < p["x"]
    assert move(p, "backward-up", "right")["x"] > p["x"]
    assert move(p, "forward-down", "right")["x"] < p["x"]
    assert move(p, "up", "right")["y"] < p["y"]
    assert move(p, "down", "right")["y"] > p["y"]

def test_defender_relative_movements_leftward_attack():
    """Left-hand goal: back toward -x, step forward toward +x."""
    p = {"x": 30.0, "y": 33.0}
    assert move(p, "backward", "left")["x"] < p["x"]
    assert move(p, "forward", "left")["x"] > p["x"]

def test_mirror_symmetry_of_analysis():
    """Mirrored positions and attack direction must give identical danger values."""
    scene = SCENARIOS[0]
    mirror = deepcopy(scene)
    mirror["attack_direction"] = "left"
    for p in mirror["players"]:
        p["x"] = 105.0 - p["x"]
    for action in ACTIONS:
        right = evaluate(scene, action)
        left = evaluate(mirror, action)
        assert right["score"] == left["score"]
        assert math.isclose(right["position"]["x"] + left["position"]["x"], 105.0, abs_tol=0.002)
        assert right["position"]["y"] == left["position"]["y"]

def test_fictional_observed_action_labels_preserve_previous_positions():
    assert SCENARIOS[0]["actual_action"] == "forward"
    assert SCENARIOS[1]["actual_action"] == "backward-down"
    assert evaluate(SCENARIOS[0], "forward")["position"]["x"] == pytest.approx(72.6)

# v0.2 - physical-time modeling tests
from app.engine import (MAX_SPEED_MPS, PLANNING_HORIZON_S, REACTION_DELAY_S,
                        PASS_SPEED_MPS, PASS_LAUNCH_DELAY_S, position_at, _lane_timing)


def test_position_is_unchanged_during_reaction_delay():
    p = {'x': 75.0, 'y': 30.0}
    for t in [0, 0.1, REACTION_DELAY_S]:
        assert position_at(p, 'backward', t)['x'] == 75.0
    assert position_at(p, 'backward', 0.5)['x'] > 75.0


def test_maximum_distance_respects_reaction_and_one_second_clock():
    p = {'x': 75.0, 'y': 30.0}
    max_distance = (PLANNING_HORIZON_S - REACTION_DELAY_S) * MAX_SPEED_MPS
    for direction in ACTIONS:
        at_end = position_at(p, direction, 1.0)
        after_end = position_at(p, direction, 2.7)
        d = math.hypot(at_end['x']-p['x'], at_end['y']-p['y'])
        assert d <= max_distance + 1e-8
        assert at_end == after_end
    assert move(p, 'backward')['x'] == pytest.approx(75 + max_distance)


def test_ball_flight_time_matches_pass_distance_over_speed():
    p = {'x': 15, 'y': 2}
    start = {'x': 0, 'y': 0}
    finish = {'x': 30, 'y': 0}
    info = _lane_timing(p, start, finish, 'hold', 'right', pass_speed_mps=15,
                        launch_delay_s=0.45)
    assert info['flight_time_s'] == pytest.approx(2.0)
    assert 0 <= info['blocked_probability'] < 0.86
    assert 0.45 < info['closest_time_s'] < 2.45


def test_interception_depends_on_simultaneous_ball_defender_positions():
    start, end = {'x': 0, 'y': 0}, {'x': 30, 'y': 0}
    p = {'x': 15, 'y': 3.0}
    static = _lane_timing(p, start, end, 'hold', 'right', pass_speed_mps=18,
                          launch_delay_s=PASS_LAUNCH_DELAY_S)
    move_up = _lane_timing(p, start, end, 'up', 'right', pass_speed_mps=18,
                           launch_delay_s=PASS_LAUNCH_DELAY_S)
    assert move_up['min_separation_m'] < static['min_separation_m']
    assert move_up['blocked_probability'] > static['blocked_probability']


def test_invalid_timing_inputs_fail():
    p, a, b = {'x': 10, 'y': 10}, {'x': 0, 'y': 0}, {'x': 20, 'y': 0}
    with pytest.raises(ValueError):
        _lane_timing(p, a, b, 'hold', 'right', pass_speed_mps=0, launch_delay_s=0)
    with pytest.raises(ValueError):
        position_at(p, 'up', -0.1)


def test_trajectory_matches_initial_and_final_position():
    for scene in SCENARIOS:
        for option in analyze(scene)['options']:
            base = next(p for p in scene['players'] if p['id'] == scene['defender_id'])
            assert option['trajectory'][0]['x'] == base['x']
            assert option['trajectory'][0]['y'] == base['y']
            assert option['trajectory'][5]['x'] == option['position']['x']
            assert option['trajectory'][5]['y'] == option['position']['y']


def test_time_aware_api_diagnostics_returned():
    data = analyze(SCENARIOS[0])
    assert data['model'].endswith('v0.2')
    assert data['assumptions']['pass_speed_mps'] == PASS_SPEED_MPS
    assert len(data['options'][0]['trajectory']) == 16
    details = data['options'][0]['passes'][0]
    assert details['flight_time_s'] > 0
    assert details['tracked_min_separation_m'] >= 0

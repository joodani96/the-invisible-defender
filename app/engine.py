"""Time-aware defensive pass-interception demonstration model (v0.2).

Scientific boundary: all outputs are SYNTHETIC HEURISTIC PROXIES, not calibrated
xG, EPV, xT, observed tracking, or objective player grades. A candidate move
has a finite reaction delay, bounded speed and 1-second movement budget.
The ball travels along a straight segment at a configurable finite speed.
Defender-to-ball separation is evaluated at the SAME time (not by projecting
onto an entire pass line independently of ball arrival).
"""

from __future__ import annotations

from math import exp, hypot, sqrt
from typing import Any

PITCH_LENGTH, PITCH_WIDTH = 105.0, 68.0
PLANNING_HORIZON_S = 1.0
MAX_SPEED_MPS = 3.0
REACTION_DELAY_S = 0.2
PASS_LAUNCH_DELAY_S = 0.45
PASS_SPEED_MPS = 18.0
SAMPLES = 65
MAX_INTERCEPTION_PROXY = 0.86

# x right, y down. 'backward' means toward own goal, not relative to screen.
ACTIONS = {
    "hold": (0.0, 0.0),
    "up": (0.0, -1.0), "down": (0.0, 1.0),
    "forward": (-1.0, 0.0), "backward": (1.0, 0.0),
    "forward-up": (-1/sqrt(2), -1/sqrt(2)),
    "forward-down": (-1/sqrt(2), 1/sqrt(2)),
    "backward-up": (1/sqrt(2), -1/sqrt(2)),
    "backward-down": (1/sqrt(2), 1/sqrt(2)),
}
ACTION_LABELS = {
    "hold": "Hold position", "up": "Shift up", "down": "Shift down",
    "forward": "Step forward", "backward": "Drop back",
    "forward-up": "Forward / up", "forward-down": "Forward / down",
    "backward-up": "Back / up", "backward-down": "Back / down",
}


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _direction(action: str, attack_direction: str) -> tuple[float, float]:
    if attack_direction not in {"right", "left"}:
        raise ValueError("attack_direction must be 'right' or 'left'")
    dx, dy = ACTIONS[action]
    if attack_direction == "left":
        dx = -dx
    return dx, dy


def receiver_value(x: float, y: float, attack_direction: str = "right") -> float:
    """Dimensionless 0–1 *heuristic* value of ball receipt location."""
    if attack_direction not in {"right", "left"}:
        raise ValueError("attack_direction must be 'right' or 'left'")
    attacking_x = x if attack_direction == "right" else PITCH_LENGTH - x
    depth = 1/(1 + exp(-(attacking_x - 76)/11))
    centrality = exp(-((y - PITCH_WIDTH/2)/27)**2)
    return 0.06 + 0.80*depth*(0.45 + 0.55*centrality)


def distance_to_lane(player: dict, a: dict, b: dict) -> tuple[float, float]:
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    length2 = dx*dx + dy*dy
    if length2 < 1e-9:
        return hypot(player["x"]-a["x"], player["y"]-a["y"]), 0.0
    t = _clip(((player["x"]-a["x"])*dx+(player["y"]-a["y"])*dy)/length2, 0, 1)
    return hypot(player["x"]-(a["x"]+t*dx), player["y"]-(a["y"]+t*dy)), t


def position_at(player: dict, action: str, time_s: float, attack_direction: str = "right",
                *, max_speed_mps: float = MAX_SPEED_MPS,
                reaction_delay_s: float = REACTION_DELAY_S,
                horizon_s: float = PLANNING_HORIZON_S) -> dict:
    """Constant-speed after reaction delay; stops at total clock time horizon_s.

    This is a bounded kinematic demo, not real acceleration/body-orientation data.
    """
    if time_s < 0 or max_speed_mps <= 0 or reaction_delay_s < 0 or horizon_s < 0:
        raise ValueError("Invalid movement time or constraints")
    dx, dy = _direction(action, attack_direction)
    moving_time = _clip(time_s - reaction_delay_s, 0.0, max(0.0, horizon_s - reaction_delay_s))
    return {
        **player,
        "x": _clip(player["x"] + dx * moving_time * max_speed_mps, 0, PITCH_LENGTH),
        "y": _clip(player["y"] + dy * moving_time * max_speed_mps, 0, PITCH_WIDTH),
    }


def move(player: dict, action: str, attack_direction: str = "right") -> dict:
    """Position at the *end* of the 1-second planning window."""
    return position_at(player, action, PLANNING_HORIZON_S, attack_direction)


def _lane_timing(defender: dict, carrier: dict, receiver: dict,
                 action: str, attack_direction: str, *, pass_speed_mps: float,
                 launch_delay_s: float) -> dict[str, float | None]:
    """Find simultaneous closest approach between moving defender and moving ball."""
    if pass_speed_mps <= 0 or launch_delay_s < 0:
        raise ValueError("Pass speed must be positive and launch delay nonnegative")
    length = hypot(receiver["x"]-carrier["x"], receiver["y"]-carrier["y"])
    if length < 0.01:
        raise ValueError("Carrier and receiver must not occupy the same location")
    flight_s = length / pass_speed_mps
    closest = float("inf")
    closest_time = None
    closest_u = None
    # interior of pass: exclude possessing player/receiver being close to defender
    for step in range(SAMPLES):
        u = 0.07 + 0.89 * step / (SAMPLES-1)
        t = launch_delay_s + flight_s * u
        ball_x = carrier["x"] + u*(receiver["x"]-carrier["x"])
        ball_y = carrier["y"] + u*(receiver["y"]-carrier["y"])
        pos = position_at(defender, action, t, attack_direction)
        dist = hypot(pos["x"]-ball_x, pos["y"]-ball_y)
        if dist < closest:
            closest, closest_time, closest_u = dist, t, u
    # Smooth radius-of-reach score; an uncalibrated interception proxy.
    proxy = MAX_INTERCEPTION_PROXY/(1 + exp(_clip((closest - 1.7)/0.75, -35, 35)))
    return {
        "blocked_probability": proxy,  # legacy API key; see model warning
        "min_separation_m": closest,
        "closest_time_s": closest_time,
        "closest_pass_fraction": closest_u,
        "flight_time_s": flight_s,
        "pass_length_m": length,
    }


def interception_probability(player: dict, carrier: dict, receiver: dict) -> float:
    """Compatibility helper: stationary defender, standard timing assumptions."""
    return float(_lane_timing(player, carrier, receiver, "hold", "right",
                              pass_speed_mps=PASS_SPEED_MPS,
                              launch_delay_s=PASS_LAUNCH_DELAY_S)["blocked_probability"])


def evaluate(scene: dict, action: str) -> dict[str, Any]:
    direction = scene.get("attack_direction", "right")
    if action not in ACTIONS:
        raise ValueError("Unknown defender action")
    speed = float(scene.get("pass_speed_mps", PASS_SPEED_MPS))
    launch = float(scene.get("pass_launch_delay_s", PASS_LAUNCH_DELAY_S))
    players = {p["id"]: dict(p) for p in scene["players"]}
    tracked = scene["defender_id"]
    position = move(players[tracked], action, direction)
    carrier = players[scene["ball_holder_id"]]
    defenders = [p for p in players.values() if p["team"] == "defense"]
    passes: list[dict] = []
    total = 0.0
    for option in scene["targets"]:
        target = players[option["player_id"]]
        combined_free = 1.0
        tracked_details = None
        for defender in defenders:
            which = action if defender["id"] == tracked else "hold"
            details = _lane_timing(defender, carrier, target, which, direction,
                                   pass_speed_mps=speed, launch_delay_s=launch)
            combined_free *= (1.0 - float(details["blocked_probability"]))
            if defender["id"] == tracked:
                tracked_details = details
        assert tracked_details is not None
        lane_block = 1.0 - combined_free
        pass_completion = (0.89 * exp(-max(float(tracked_details["pass_length_m"])-22, 0)/130)
                           * combined_free)
        danger = receiver_value(target["x"], target["y"], direction)
        contribution = float(option["weight"]) * pass_completion * danger
        total += contribution
        passes.append({
            "target_id": target["id"], "target_name": target["name"],
            "receiver_value": round(danger, 4), "weight": option["weight"],
            "blocked_probability": round(lane_block, 4),
            "completion_probability": round(pass_completion, 4),
            "contribution": round(contribution, 4),
            "length_m": round(float(tracked_details["pass_length_m"]), 2),
            "flight_time_s": round(float(tracked_details["flight_time_s"]), 3),
            "tracked_min_separation_m": round(float(tracked_details["min_separation_m"]), 3),
            "tracked_closest_time_s": round(float(tracked_details["closest_time_s"]), 3),
            "tracked_interception_proxy": round(float(tracked_details["blocked_probability"]), 4),
        })
    return {
        "action": action, "label": ACTION_LABELS[action],
        "score": round(total, 4),
        "position": {"x": round(position["x"], 3), "y": round(position["y"], 3)},
        "trajectory": [
            {"t": round(t*0.2, 2),
             "x": round(position_at(players[tracked], action, t*0.2, direction)["x"], 3),
             "y": round(position_at(players[tracked], action, t*0.2, direction)["y"], 3)}
            for t in range(16)
        ],
        "passes": passes,
    }


def analyze(scene: dict) -> dict[str, Any]:
    if abs(sum(float(t["weight"]) for t in scene["targets"]) - 1) > 1e-8:
        raise ValueError("Pass weights must sum to one")
    if scene["actual_action"] not in ACTIONS:
        raise ValueError("Actual movement is invalid")
    options = [evaluate(scene, action) for action in ACTIONS]
    baseline = next(a for a in options if a["action"] == "hold")
    best = min(options, key=lambda a: a["score"])
    actual = next(a for a in options if a["action"] == scene["actual_action"])
    return {
        "model": "time-aware-synthetic-threat-proxy-v0.2",
        "model_warning": (
            "Uncalibrated heuristic: NOT xG, xT, EPV, actual interception probability "
            "or a validated player performance rating. All scenarios are fictional."
        ),
        "assumptions": {
            "pass_speed_mps": float(scene.get("pass_speed_mps", PASS_SPEED_MPS)),
            "pass_launch_delay_s": float(scene.get("pass_launch_delay_s", PASS_LAUNCH_DELAY_S)),
            "defender_max_speed_mps": MAX_SPEED_MPS,
            "defender_reaction_delay_s": REACTION_DELAY_S,
            "movement_horizon_s": PLANNING_HORIZON_S,
            "other_players_stationary": True,
            "fixed_target_weights": True,
        },
        "scene": scene,
        "baseline_score": baseline["score"],
        "optimal_action": best["action"], "optimal_score": best["score"],
        "actual_action": actual["action"], "actual_score": actual["score"],
        "options": options,
    }

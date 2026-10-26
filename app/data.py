"""Synthetic, fictional scenes created for the hackathon demo."""

SCENARIOS = [
    {
        "id": "central-through-ball",
        "title": "The invisible interception",
        "subtitle": "A high-value passing lane opens above the centre-back, while a teammate covers the lower channel.",
        "minute": "34:18",
        "event_type": "pass_opportunity",
        "pass_speed_mps": 18.0,
        "pass_launch_delay_s": 0.45,
        "attack_direction": "right",
        "defender_id": "d4",
        "ball_holder_id": "a8",
        "actual_action": "forward",
        "observed_pass_target_id": "a9",
        "players": [
            {"id": "a8", "number": 8, "name": "Midfielder", "team": "attack", "x": 59, "y": 35},
            {"id": "a9", "number": 9, "name": "Striker", "team": "attack", "x": 91, "y": 25, "vx": 1.2, "vy": -0.3},
            {"id": "a11", "number": 11, "name": "Winger", "team": "attack", "x": 87, "y": 48, "vx": 0.8, "vy": 0.4},
            {"id": "d4", "number": 4, "name": "Tracked defender", "team": "defense", "x": 75, "y": 33, "marking_target_id": "a9"},
            {"id": "d5", "number": 5, "name": "Covering defender", "team": "defense", "x": 79, "y": 46, "vx": 0.6, "vy": 0.4, "marking_target_id": "a11"},
            {"id": "d2", "number": 2, "name": "Fullback", "team": "defense", "x": 95, "y": 62, "vx": -0.3, "vy": -0.3},
            {"id": "gk", "number": 1, "name": "Goalkeeper", "team": "defense", "is_goalkeeper": True, "x": 102, "y": 34},
        ],
        "targets": [{"player_id": "a9", "weight": 0.74}, {"player_id": "a11", "weight": 0.26}],
    },
    {
        "id": "half-space",
        "title": "Closing the half-space",
        "subtitle": "Two runners force a split-second choice in the right channel.",
        "minute": "52:41",
        "event_type": "pass_opportunity",
        "pass_speed_mps": 18.0,
        "pass_launch_delay_s": 0.45,
        "attack_direction": "right",
        "defender_id": "d4",
        "ball_holder_id": "a8",
        "actual_action": "backward-down",
        "observed_pass_target_id": "a9",
        "players": [
            {"id": "a8", "number": 8, "name": "Playmaker", "team": "attack", "x": 61, "y": 15},
            {"id": "a9", "number": 9, "name": "Inside forward", "team": "attack", "x": 91, "y": 31, "vx": 0.9, "vy": 0.4},
            {"id": "a7", "number": 7, "name": "Wide runner", "team": "attack", "x": 87, "y": 7, "vx": 0.6, "vy": 0.4},
            {"id": "d4", "number": 4, "name": "Tracked defender", "team": "defense", "x": 77, "y": 23, "marking_target_id": "a9"},
            {"id": "d2", "number": 2, "name": "Fullback", "team": "defense", "x": 82, "y": 8, "vx": 0.5, "vy": 0.2, "marking_target_id": "a7"},
            {"id": "d6", "number": 6, "name": "Holding midfielder", "team": "defense", "x": 95, "y": 61, "vx": 0.2, "vy": -0.3},
            {"id": "gk", "number": 1, "name": "Goalkeeper", "team": "defense", "is_goalkeeper": True, "x": 102, "y": 34},
        ],
        "targets": [{"player_id": "a9", "weight": 0.71}, {"player_id": "a7", "weight": 0.29}],
    },
    {
        "id": "transition",
        "title": "Stopping the transition",
        "subtitle": "An advancing runner threatens space between two defenders.",
        "minute": "76:09",
        "event_type": "pass_opportunity",
        "pass_speed_mps": 18.0,
        "pass_launch_delay_s": 0.45,
        "attack_direction": "right",
        "defender_id": "d4",
        "ball_holder_id": "a10",
        "actual_action": "up",
        "observed_pass_target_id": "a9",
        "players": [
            {"id": "a10", "number": 10, "name": "Ball carrier", "team": "attack", "x": 48, "y": 43},
            {"id": "a9", "number": 9, "name": "Central runner", "team": "attack", "x": 85, "y": 37, "vx": 1.6, "vy": -0.3},
            {"id": "a7", "number": 7, "name": "Wide runner", "team": "attack", "x": 93, "y": 55, "vx": 0.5, "vy": 0.2},
            {"id": "d4", "number": 4, "name": "Tracked defender", "team": "defense", "x": 71, "y": 47, "marking_target_id": "a9"},
            {"id": "d5", "number": 5, "name": "Center back", "team": "defense", "x": 79, "y": 31, "vx": 0.8, "vy": 0.4},
            {"id": "d3", "number": 3, "name": "Fullback", "team": "defense", "x": 96, "y": 65, "vx": -0.3, "vy": -0.2, "marking_target_id": "a7"},
            {"id": "gk", "number": 1, "name": "Goalkeeper", "team": "defense", "is_goalkeeper": True, "x": 102, "y": 34},
        ],
        "targets": [{"player_id": "a9", "weight": 0.62}, {"player_id": "a7", "weight": 0.38}],
    },
    {
        "id": "offside-trap",
        "title": "The offside trap",
        "subtitle": "One backward step can make an otherwise offside striker eligible to receive.",
        "minute": "64:12", "event_type": "pass_opportunity",
        "pass_speed_mps": 18.0, "pass_launch_delay_s": 0.45,
        "attack_direction": "right", "defender_id": "d4", "ball_holder_id": "a8",
        "actual_action": "backward", "observed_pass_target_id": "a9",
        "players": [
            {"id": "a8", "number": 8, "name": "Passer", "team": "attack", "x": 64, "y": 31},
            {"id": "a9", "number": 9, "name": "Striker at the line", "team": "attack", "x": 90.5, "y": 29},
            {"id": "a11", "number": 11, "name": "Legal wide option", "team": "attack", "x": 85, "y": 53},
            {"id": "d4", "number": 4, "name": "Line-setting defender", "team": "defense", "x": 90, "y": 35, "marking_target_id": "a9"},
            {"id": "d5", "number": 5, "name": "Wide-cover teammate", "team": "defense", "x": 77, "y": 53, "marking_target_id": "a11"},
            {"id": "d2", "number": 2, "name": "Far-side fullback", "team": "defense", "x": 72, "y": 65, "vx": 0.3, "vy": -0.15},
            {"id": "gk", "number": 1, "name": "Goalkeeper", "team": "defense", "is_goalkeeper": True, "x": 102, "y": 34}
        ],
        "targets": [{"player_id": "a9", "weight": 0.8}, {"player_id": "a11", "weight": 0.2}],
    },
    {
        "id": "onside-run",
        "title": "Timing the onside run",
        "subtitle": "The runner crosses the offside line only after the ball has been played.",
        "minute": "67:26", "event_type": "pass_opportunity",
        "pass_speed_mps": 18.0, "pass_launch_delay_s": 0.45,
        "attack_direction": "right", "defender_id": "d4", "ball_holder_id": "a8",
        "actual_action": "hold", "observed_pass_target_id": "a9",
        "players": [
            {"id": "a8", "number": 8, "name": "Passer", "team": "attack", "x": 64, "y": 31},
            {"id": "a9", "number": 9, "name": "Timed runner", "team": "attack", "x": 87.5, "y": 30, "vx": 3.0},
            {"id": "a11", "number": 11, "name": "Wide option", "team": "attack", "x": 82, "y": 50},
            {"id": "d4", "number": 4, "name": "Line-setting defender", "team": "defense", "x": 90, "y": 40},
            {"id": "d5", "number": 5, "name": "Covering defender", "team": "defense", "x": 78, "y": 51},
            {"id": "d2", "number": 2, "name": "Far-side fullback", "team": "defense", "x": 69, "y": 63, "vx": 0.3, "vy": -0.15},
            {"id": "gk", "number": 1, "name": "Goalkeeper", "team": "defense", "is_goalkeeper": True, "x": 102, "y": 34}
        ],
        "targets": [{"player_id": "a9", "weight": 0.78}, {"player_id": "a11", "weight": 0.22}],
    }
]


# Explicit, hand-authored *synthetic* body directions for the 3D replay.
# Pitch degrees: 0 = right (+X), 90 = lower touchline (+Y), 180 = left.
# These values are not inferred tracking observations and do not affect the
# mathematical defensive model / xT-like heuristic indices.
_SYNTHETIC_FACING = {
    'central-through-ball': {'a8': 344, 'a9': 344, 'a11': 26, 'd4': 170, 'd5': 198, 'd2': 213, 'gk': 180},
    'half-space': {'a8': 28, 'a9': 25, 'a7': 34, 'd4': 201, 'd2': 194, 'd6': 226, 'gk': 184},
    'transition': {'a10': 350, 'a9': 350, 'a7': 24, 'd4': 176, 'd5': 174, 'd3': 211, 'gk': 184},
    'offside-trap': {'a8': 354, 'a9': 183, 'a11': 205, 'd4': 180, 'd5': 198, 'd2': 211, 'gk': 180},
    'onside-run': {'a8': 354, 'a9': 1, 'a11': 215, 'd4': 176, 'd5': 194, 'd2': 213, 'gk': 180},
}
for _scene in SCENARIOS:
    _directions = _SYNTHETIC_FACING[_scene['id']]
    for _player in _scene['players']:
        _player['body_facing_deg'] = _directions[_player['id']]
        _player['facing_source'] = 'synthetic_authored'

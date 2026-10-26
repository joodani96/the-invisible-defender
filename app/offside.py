"""Rule-11-inspired positional offside approximation for synthetic pitch data.

A player being in an offside *position* is NOT itself an offence. Here a
candidate pass to such a receiver is excluded from the modeled successful
attacking options, under the explicitly stated conditional assumption that
the recipient would play or interfere with play.

Player locations are *points*, not official shoulder/head/foot silhouettes;
no video/VAR-grade determination is made. This module intentionally does not
adjudicate rebounds, deliberate plays/saves, obstructing opponents, etc.
"""
from __future__ import annotations

from .engine import PITCH_LENGTH

EXEMPT_RESTARTS = frozenset({'goal_kick', 'throw_in', 'corner_kick'})
OFFSIDE_EPSILON_M = 1e-7


def attacking_progress(x: float, direction: str) -> float:
    if direction == 'right':
        return x
    if direction == 'left':
        return PITCH_LENGTH - x
    raise ValueError('Invalid attacking direction')


def offside_snapshot(*, defenders: list[dict], ball: dict, targets: list[dict],
                     attack_direction: str, event_type: str = 'pass_opportunity') -> dict:
    """Compute point-based offside flags at the *instant of a teammate's touch*.

    defenders: all opponents INCLUDING the goalkeeper, at ball-contact time.
    ball: ball's position at the same time.
    targets: receiver positions at that time (NOT their later reception points).
    """
    if len(defenders) < 2:
        raise ValueError('At least two defending opponents are required for offside')
    if any(p.get('team') != 'defense' for p in defenders):
        raise ValueError('Every defender must be from the opposing team')
    ordered = sorted((attacking_progress(float(d['x']), attack_direction) for d in defenders), reverse=True)
    second_last = ordered[1]
    ball_progress = attacking_progress(float(ball['x']), attack_direction)
    threshold = max(ball_progress, second_last)
    exempt = event_type in EXEMPT_RESTARTS
    statuses = {}
    for p in targets:
        progress = attacking_progress(float(p['x']), attack_direction)
        opponent_half = progress > PITCH_LENGTH / 2 + OFFSIDE_EPSILON_M
        offside_position = (not exempt and opponent_half and progress > threshold + OFFSIDE_EPSILON_M)
        statuses[p['id']] = {
            'offside_position': offside_position,
            'eligible_target': not offside_position,
            'margin_m': round(progress - threshold, 5),
            'attacking_half': opponent_half,
        }
    return {
        'offside_line_x': round(threshold if attack_direction == 'right' else PITCH_LENGTH-threshold, 5),
        'second_last_defender_x': round(second_last if attack_direction == 'right' else PITCH_LENGTH-second_last, 5),
        'ball_x': round(float(ball['x']), 5),
        'event_exempt': exempt,
        'target_statuses': statuses,
        'basis': 'point-center approximation at first teammate ball contact; candidate receiving involvement assumed',
    }

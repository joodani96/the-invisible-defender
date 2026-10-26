"""Explain whether ONE focused defender can change an observed receiver's offside status.

This is a geometric diagnostic at the configured ball-touch instant, not
referee adjudication or a new player-performance score. It deliberately uses
exactly the same scenario assumptions as the hybrid pre-pass model.
"""
from __future__ import annotations

from .engine import MAX_SPEED_MPS, REACTION_DELAY_S, PASS_LAUNCH_DELAY_S, PITCH_LENGTH
from .hybrid import _players, _offside_at_launch, _defender_at, defender_position, scripted_position, decision_facing_deg, candidate_direction
from .offside import attacking_progress


def explain_offside_opportunity(scene: dict) -> dict:
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    direction = scene.get('attack_direction', 'right')
    players = _players(scene)
    target = scene['observed_pass_target_id']
    receiver = scripted_position(players[target], launch)
    holder = scripted_position(players[scene['ball_holder_id']], launch)
    current = defender_position(scene, 'hold', launch, 'pre')
    # Pick the action giving most *pitch-forward* progress for a diagnostic.
    # A body-forward movement might not be the right action to spring a trap.
    actions = ['forward','backward','up','down','forward-up','forward-down','backward-up','backward-down']
    pitch_sign = -1 if direction=='right' else 1
    forward_action=max(actions,key=lambda name:pitch_sign*candidate_direction(scene,name,'pre')[0])
    forward = defender_position(scene, forward_action, launch, 'pre')
    hold_snapshot = _offside_at_launch(scene, 'hold', 'pre')
    forward_snapshot = _offside_at_launch(scene, forward_action, 'pre')
    target_progress = attacking_progress(receiver['x'], direction)
    ball_progress = attacking_progress(holder['x'], direction)
    focused_progress = attacking_progress(current['x'], direction)
    available = max(0.0, focused_progress - attacking_progress(forward['x'], direction))
    # How many OTHER defenders can keep the striker onside even after the
    # selected player advances? One goalkeeper may remain deeper, not two.
    deeper_others = sum(
        attacking_progress(_defender_at(scene, p, 'hold', launch, 'pre')['x'], direction) >= target_progress - 1e-7
        for p in players.values()
        if p['team'] == 'defense' and p['id'] != scene['defender_id']
    )
    # Strictly beyond the attacker: equality is onside. The displayed
    # minimum is rounded to centimetres; comparisons use an epsilon.
    required = max(0.0, focused_progress - target_progress + 0.0001)
    hold_offside = hold_snapshot['target_statuses'][target]['offside_position']
    forward_offside = forward_snapshot['target_statuses'][target]['offside_position']
    can_in_principle = (
        target_progress > ball_progress + 1e-7 and
        target_progress > PITCH_LENGTH / 2 and
        deeper_others <= 1 and
        not hold_snapshot['event_exempt']
    )
    if hold_snapshot['event_exempt']:
        status = 'exempt_restart'
    elif hold_offside:
        status = 'already_offside'
    elif target_progress <= ball_progress + 1e-7 or target_progress <= PITCH_LENGTH / 2:
        status = 'target_not_in_offside_eligible_zone'
    elif deeper_others > 1:
        status = 'other_defenders_keep_target_onside'
    elif forward_offside:
        status = 'offside_trap_feasible_in_tested_move'
    else:
        status = 'insufficient_time_to_advance'
    return {
        'target_id': target,
        'selected_defender_id': scene['defender_id'],
        'status': status,
        'pass_launch_time_s': round(launch, 4),
        'reaction_delay_s': REACTION_DELAY_S,
        'max_speed_mps': MAX_SPEED_MPS,
        'selected_defender_x_at_kick_if_hold': round(current['x'], 4),
        'target_x_at_kick': round(receiver['x'], 4),
        'offside_line_x_if_hold': hold_snapshot['offside_line_x'],
        'offside_line_x_if_step_forward': forward_snapshot['offside_line_x'],
        'best_tested_pitch_forward_action': forward_action,
        'hold_target_offside': hold_offside,
        'forward_target_offside': forward_offside,
        'other_defenders_at_or_behind_receiver': deeper_others,
        'can_selected_defender_set_offside_alone_in_principle': can_in_principle,
        'minimum_forward_displacement_at_kick_m': round(required, 3) if can_in_principle and not hold_offside else None,
        'tested_forward_displacement_by_kick_m': round(available, 3),
        'assumption': 'Point-player positions at the first teammate touch; other defenders keep their authored paths. Does not assess active involvement, body parts, tactical risk or changing the kick time.',
    }


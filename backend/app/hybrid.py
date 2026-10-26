"""Experimental hybrid counterfactual model, version 0.6.

Independent, deliberately simple implementation inspired by (not copied from):
- Cascioli & Wang: off-ball cover shadows, movement-aware lane control.
- Kim et al., DEFCON: team attacking value and defender-level attribution.
- Dick et al.: pass availability as timed interception/arrival.

IMPORTANT: Scores, probabilities and 'credit' are synthetic heuristic INDICES.
No calibration, validation, model weights, learned EPV or observed outcomes.

Two *different decisions* are modeled:
PRE  : at t=0 choose a movement before a pass; attacker may change target;
       commitment continues through the subsequent pass.
POST : at the already fixed pass launch time, choose a reaction; target cannot
       change, and all alternatives begin from the same observed defender pose.
"""
from __future__ import annotations

from math import exp, hypot, log, cos, sin, radians, atan2, degrees, sqrt
from typing import Any

from .offside import offside_snapshot

from .engine import (
    ACTIONS, ACTION_LABELS, MAX_SPEED_MPS, REACTION_DELAY_S,
    PASS_LAUNCH_DELAY_S, PASS_SPEED_MPS, PLANNING_HORIZON_S,
    PITCH_LENGTH, PITCH_WIDTH, _clip, _direction, position_at, receiver_value,
)

BALL_SAMPLES = 121
PLAYER_MOTION_LIMIT_S = 3.0
MAX_SCRIPTED_SPEED_MPS = 4.0
RECEIVER_PRESSURE_RADIUS_M = 5.0
RECEIVER_PRESSURE_WEIGHT = 0.32
ROLE_RELEASE_WEIGHT = 0.055
CONTACT_RADIUS_M = 0.75           # illustrative 2D centre-distance reach, not physical possession
COVER_RADIUS_M = 1.35             # characteristic distance of coverage sigmoid
COVER_SOFTNESS_M = 0.42
MAX_COVER_INDEX = 0.90
BASE_COMPLETION_INDEX = 0.92
RECYCLE_PRIOR = 0.33              # hypothetical low-risk alternative
RECYCLE_VALUE = 0.035
CHOICE_SENSITIVITY = 3.0


def _players(scene: dict) -> dict[str, dict]:
    p = {player['id']: player for player in scene['players']}
    if len(p) != len(scene['players']):
        raise ValueError('Duplicate player IDs')
    return p


def _validate_scene(scene: dict) -> None:
    p = _players(scene)
    if scene.get('attack_direction', 'right') not in ('left', 'right'):
        raise ValueError('Invalid attack direction')
    if sum(bool(v.get('is_goalkeeper')) for v in p.values()) != 1 or any(v.get('is_goalkeeper') and v['team'] != 'defense' for v in p.values()):
        raise ValueError('Exactly one defending goalkeeper must be present')
    if scene.get('event_type', 'pass_opportunity') not in ('pass_opportunity', 'goal_kick', 'throw_in', 'corner_kick'):
        raise ValueError('Unsupported event type for offside modeling')
    if scene['ball_holder_id'] not in p or p[scene['ball_holder_id']]['team'] != 'attack':
        raise ValueError('Missing attacking ball holder')
    if scene['defender_id'] not in p or p[scene['defender_id']]['team'] != 'defense':
        raise ValueError('Missing tracked defender')
    if scene['actual_action'] not in ACTIONS:
        raise ValueError('Invalid observed action')
    if not scene['targets']:
        raise ValueError('A pass target is required')
    ids = {t['player_id'] for t in scene['targets']}
    if len(ids) != len(scene['targets']) or any(i not in p or p[i]['team'] != 'attack' for i in ids):
        raise ValueError('Invalid or duplicate attacking targets')
    observed = scene.get('observed_pass_target_id')
    if observed not in ids:
        raise ValueError('Observed pass target must be a candidate')
    if any(float(t['weight']) <= 0 for t in scene['targets']):
        raise ValueError('Positive prior preferences required')
    if float(scene.get('pass_speed_mps', PASS_SPEED_MPS)) <= 0:
        raise ValueError('Pass speed must be positive')
    if float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S)) < 0:
        raise ValueError('Pass launch delay cannot be negative')
    for player in p.values():
        vx, vy = float(player.get('vx', 0)), float(player.get('vy', 0))
        if hypot(vx, vy) > MAX_SCRIPTED_SPEED_MPS + 1e-9:
            raise ValueError('Scripted velocity exceeds maximum')
        assignment = player.get('marking_target_id')
        if assignment is not None and (player['team'] != 'defense' or assignment not in p or p[assignment]['team'] != 'attack'):
            raise ValueError('Invalid marking assignment')
        if not (0 <= float(player['x']) <= PITCH_LENGTH and 0 <= float(player['y']) <= PITCH_WIDTH):
            raise ValueError('Player outside the football pitch')


def observed_position(scene: dict, player: dict, time_s: float) -> dict:
    """Synthetic authored background trajectory, shared by all counterfactuals.

    The original showcase defender has a scripted direction. Other players
    follow explicitly authored constant velocities. Nothing here is inferred
    from video or represented as a real-life observed action.
    """
    primary_id = scene.get('observed_primary_defender_id', scene['defender_id'])
    primary_action = scene.get('observed_primary_action', scene['actual_action'])
    if player['id'] == primary_id:
        return position_at(player, primary_action, time_s, scene.get('attack_direction', 'right'))
    return scripted_position(player, time_s)


# v0.9.5: player-local tactical alternatives. 0deg = +pitch X, 90deg = +pitch Y.
# These headings are synthetic; they are NOT observed tracking or a calibrated
# biomechanical turning model. The 9 alternatives use fixed heading at the
# decision instant so their interpretation never changes mid-action.
_LOCAL_COMPONENTS = {
    'hold': (0., 0.), 'forward': (1., 0.), 'backward': (-1., 0.),
    'up': (0., -1.), 'down': (0., 1.),
    'forward-up': (1/sqrt(2), -1/sqrt(2)),
    'forward-down': (1/sqrt(2), 1/sqrt(2)),
    'backward-up': (-1/sqrt(2), -1/sqrt(2)),
    'backward-down': (-1/sqrt(2), 1/sqrt(2)),
}
_LOCAL_LABELS = {
    'hold':'Hold position', 'forward':'Forward', 'backward':'Back',
    'up':'Left', 'down':'Right',
    'forward-up':'Forward-left', 'forward-down':'Forward-right',
    'backward-up':'Back-left', 'backward-down':'Back-right',
}

def decision_facing_deg(scene: dict, phase: str) -> float:
    """Frozen heading at decision: authored pose at t=0, or at pass release.

    Post uses the SAME non-counterfactual history for all candidates; the
    interpolation approximates the already rendered 3D rotation heuristic.
    """
    defender = _players(scene)[scene['defender_id']]
    initial = float(defender.get('body_facing_deg', 180)) % 360
    if phase == 'pre':
        return initial
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    t0, t1 = max(0, launch-.06), launch+.06
    a=observed_position(scene, defender, t0)
    b=observed_position(scene, defender, t1)
    speed=hypot(b['x']-a['x'], b['y']-a['y'])/(t1-t0)
    if speed < .65:
        return initial
    desired=degrees(atan2(b['y']-a['y'], b['x']-a['x'])) % 360
    shortest=(desired-initial+540)%360-180
    max_turn=launch*165
    return (initial+max(-max_turn,min(max_turn,shortest)))%360

def candidate_direction(scene:dict, action:str, phase:str)->tuple[float,float]:
    """Model displacement in pitch metres per metre of intended travel."""
    if not scene.get('player_centric') or scene.get('movement_frame') != 'body':
        return _direction(action, scene.get('attack_direction', 'right'))
    forward,left_right = _LOCAL_COMPONENTS[action]  # negative = left
    theta=radians(decision_facing_deg(scene,phase))
    return (forward*cos(theta)-left_right*sin(theta),
            forward*sin(theta)+left_right*cos(theta))

def candidate_position(scene:dict, player:dict, action:str, t:float, phase:str='pre')->dict:
    if not scene.get('player_centric') or scene.get('movement_frame') != 'body':
        return position_at(player,action,t,scene.get('attack_direction','right'))
    dx,dy=candidate_direction(scene,action,phase)
    moving=_clip(t-REACTION_DELAY_S,0,max(0,PLANNING_HORIZON_S-REACTION_DELAY_S))
    return {**player,
            'x':_clip(player['x']+dx*MAX_SPEED_MPS*moving,0,PITCH_LENGTH),
            'y':_clip(player['y']+dy*MAX_SPEED_MPS*moving,0,PITCH_WIDTH)}


def defender_position(scene: dict, action: str, time_s: float, phase: str) -> dict:
    """Where the tracked defender can physically be at a common absolute time.

    POST candidates react only after launch, from their *shared* observed
    position at launch. No counterfactual post decision changes history.
    """
    if (action not in ACTIONS and not (action == 'observed' and scene.get('player_centric'))) or phase not in {'pre', 'post'} or time_s < 0:
        raise ValueError('Invalid decision or phase')
    player = _players(scene)[scene['defender_id']]
    if action == 'observed':
        return observed_position(scene, player, time_s)
    direction = scene.get('attack_direction', 'right')
    if phase == 'pre':
        return candidate_position(scene, player, action, time_s, 'pre')
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    fixed = observed_position(scene, player, min(time_s, launch)) if scene.get('player_centric') else position_at(player, scene['actual_action'], min(time_s, launch), direction)
    if time_s <= launch:
        return fixed
    dx, dy = candidate_direction(scene, action, phase)
    effective_time = _clip(time_s - launch - REACTION_DELAY_S, 0, PLANNING_HORIZON_S - REACTION_DELAY_S)
    return {**fixed,
            'x': _clip(fixed['x'] + dx * MAX_SPEED_MPS * effective_time, 0, PITCH_LENGTH),
            'y': _clip(fixed['y'] + dy * MAX_SPEED_MPS * effective_time, 0, PITCH_WIDTH)}


def scripted_position(player: dict, t: float) -> dict:
    """Deterministic (fictional) background player trajectory shared across all alternatives.

    x/y are metres, vx/vy metres per second; a small constant-velocity
    approximation, clamped to the pitch and 3-second scene window.
    """
    if t < 0:
        raise ValueError('Negative simulation time')
    moving_time = min(t, PLAYER_MOTION_LIMIT_S)
    return {**player,
            'x': _clip(player['x'] + float(player.get('vx', 0)) * moving_time, 0, PITCH_LENGTH),
            'y': _clip(player['y'] + float(player.get('vy', 0)) * moving_time, 0, PITCH_WIDTH)}


def pass_geometry(scene: dict, target_id: str) -> dict:
    """Fixed pass geometry determined at launch, independent of defender option.

    Receiver can run; the ball is sent toward a simple predicted receiving
    location based on the receiver's authored, deterministic velocity.
    """
    players = _players(scene)
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    speed = float(scene.get('pass_speed_mps', PASS_SPEED_MPS))
    holder = scripted_position(players[scene['ball_holder_id']], launch)
    receiver = players[target_id]
    flight = hypot(receiver['x'] - holder['x'], receiver['y'] - holder['y']) / speed
    for _ in range(6):
        end = scripted_position(receiver, launch + flight)
        flight = hypot(end['x'] - holder['x'], end['y'] - holder['y']) / speed
    end = scripted_position(receiver, launch + flight)
    if flight <= .001:
        raise ValueError('Zero-length pass is not supported')
    return {'start': {'x': holder['x'], 'y': holder['y']},
            'end': {'x': end['x'], 'y': end['y']}, 'flight': flight,
            'length': flight * speed}


def _defender_at(scene: dict, defender: dict, action: str, t: float, phase: str) -> dict:
    if defender['id'] == scene['defender_id']:
        return defender_position(scene, action, t, phase)
    return observed_position(scene, defender, t) if scene.get('player_centric') else scripted_position(defender, t)


def pass_coverage(scene: dict, target_id: str, action: str, phase: str) -> dict[str, Any]:
    """Time-coincident ball/defender coverage for *all* defending players.

    The soft coverage score is not a probability or an observed tackle.
    Geometric first contact is separately computed and can drive animation.
    """
    players = _players(scene)
    geo = pass_geometry(scene, target_id)
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    flight = geo['flight']
    start, end = geo['start'], geo['end']
    receiver_at_arrival = scripted_position(players[target_id], launch + flight)
    defenders = [p for p in players.values() if p['team'] == 'defense']
    records: list[dict] = []
    for defender in defenders:
        closest = float('inf')
        nearest_t = launch
        first_contact = None
        first_contact_fraction = None
        # Ball travels on a low straight pass, sampled through the full flight.
        for k in range(BALL_SAMPLES):
            u = k / (BALL_SAMPLES - 1)
            t = launch + flight * u
            ballx = start['x'] + u * (end['x'] - start['x'])
            bally = start['y'] + u * (end['y'] - start['y'])
            pos = _defender_at(scene, defender, action, t, phase)
            gap = hypot(ballx - pos['x'], bally - pos['y'])
            if gap < closest:
                closest, nearest_t = gap, t
            # Stop the animated ball only when it physically enters the defined
            # contact radius -- *not* when an uncalibrated coverage index is high.
            if first_contact is None and gap <= CONTACT_RADIUS_M:
                first_contact = t
                first_contact_fraction = u
        cover = MAX_COVER_INDEX / (1 + exp(_clip((closest - COVER_RADIUS_M)/COVER_SOFTNESS_M, -40, 40)))
        # Assignment-aware control *at reception*; only the assigned defender
        # gets marking credit. This is not the same as an interception.
        assignment = defender.get('marking_target_id')
        reception_gap = hypot(_defender_at(scene, defender, action, launch + flight, phase)['x'] - receiver_at_arrival['x'],
                              _defender_at(scene, defender, action, launch + flight, phase)['y'] - receiver_at_arrival['y'])
        marking = RECEIVER_PRESSURE_WEIGHT * exp(-.5 * (reception_gap / RECEIVER_PRESSURE_RADIUS_M) ** 2) if assignment == target_id else 0.0
        combined = 1 - (1-cover) * (1-marking)
        records.append({
            'marking_target_id': assignment,
            'reception_gap_m': reception_gap,
            'receiver_pressure_index': marking,
            'effective_coverage_index': combined,
            'defender_id': defender['id'],
            'min_gap_m': closest,
            'closest_time_s': nearest_t,
            'coverage_index': cover,
            'contact_time_s': first_contact,
            'contact_fraction': first_contact_fraction,
        })
    other_free = 1.0
    for r in records:
        if r['defender_id'] != scene['defender_id']:
            other_free *= 1 - r['effective_coverage_index']
    tracked = next(r for r in records if r['defender_id'] == scene['defender_id'])
    team_free = other_free * (1 - tracked['effective_coverage_index'])
    first = min((r for r in records if r['contact_time_s'] is not None),
                key=lambda r: r['contact_time_s'], default=None)
    # A positive marginal index is smaller when a teammate already covers the lane.
    marginal = other_free * tracked['effective_coverage_index']
    length = geo['length']
    # Ball delivery accuracy is an arbitrary pass-length heuristic, NOT a learned model.
    ball_delivery = BASE_COMPLETION_INDEX * exp(-max(length - 22, 0)/130)
    return {
        'target_id': target_id,
        'flight_time_s': flight,
        'length_m': length,
        'pass_start': start,
        'pass_end': end,
        'other_defenders_coverage_index': 1 - other_free,
        'tracked_coverage_index': tracked['effective_coverage_index'],
        'tracked_lane_coverage_index': tracked['coverage_index'],
        'tracked_receiver_pressure_index': tracked['receiver_pressure_index'],
        'team_coverage_index': 1 - team_free,
        'marginal_coverage_index': marginal,
        'completion_index': ball_delivery * team_free,
        'tracked_min_gap_m': tracked['min_gap_m'],
        'tracked_closest_time_s': tracked['closest_time_s'],
        'contact_time_s': first['contact_time_s'] if first else None,
        'contact_fraction': first['contact_fraction'] if first else None,
        'contact_defender_id': first['defender_id'] if first else None,
        'defenders': records,
    }


def _offside_at_launch(scene: dict, action: str, phase: str) -> dict:
    """Offside is checked AT THE PASS TOUCH, before ball flight begins.

    PRE may modify the line through the tracked defender's possible motion.
    POST uses the same previously observed line for every reaction.
    """
    players = _players(scene)
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    defs = [_defender_at(scene, p, action, launch, phase)
            for p in players.values() if p['team'] == 'defense']
    ball = scripted_position(players[scene['ball_holder_id']], launch)
    targets = [scripted_position(players[t['player_id']], launch)
               for t in scene['targets']]
    return offside_snapshot(defenders=defs, ball=ball, targets=targets,
                            attack_direction=scene.get('attack_direction', 'right'),
                            event_type=scene.get('event_type', 'pass_opportunity'))


def _decision_value(scene: dict, action: str, phase: str) -> dict:
    players = _players(scene)
    offside = _offside_at_launch(scene, action, phase)
    passing = []
    for t in scene['targets']:
        receiver = players[t['player_id']]
        lane = pass_coverage(scene, t['player_id'], action, phase)
        value = receiver_value(lane['pass_end']['x'], lane['pass_end']['y'], scene.get('attack_direction', 'right'))
        flag = offside['target_statuses'][t['player_id']]
        # Potential offside receiver cannot yield a successful *legal* direct pass
        # IF they become involved; keep raw physics as diagnostics.
        raw_benefit = lane['completion_index'] * value
        benefit = 0.0 if flag['offside_position'] else raw_benefit
        passing.append({**lane, **flag, 'offside_line_x': offside['offside_line_x'],
                        'conditional_offside_exclusion': flag['offside_position'],
                        'unfiltered_conditional_threat': raw_benefit,
                        'target_name': receiver['name'],
                        'prior_weight': float(t['weight']), 'receiver_value': value,
                        'conditional_threat': benefit})
    if phase == 'pre':
        logits = [(log(item['prior_weight']) + CHOICE_SENSITIVITY*item['conditional_threat'])
                  if item['eligible_target'] else float('-inf') for item in passing]
        logits.append(log(RECYCLE_PRIOR) + CHOICE_SENSITIVITY*RECYCLE_VALUE)
        pivot = max(logits)
        e = [exp(a - pivot) for a in logits]
        probabilities = [n/sum(e) for n in e]
        for entry, prob in zip(passing, probabilities[:-1]):
            entry['pass_choice_index'] = prob
            entry['weighted_threat'] = prob * entry['conditional_threat']
        recycle_share = probabilities[-1]
        score = sum(p['weighted_threat'] for p in passing) + recycle_share*RECYCLE_VALUE
    else:
        target = scene['observed_pass_target_id']
        for entry in passing:
            entry['pass_choice_index'] = 1.0 if entry['target_id'] == target else 0.0
            entry['weighted_threat'] = entry['conditional_threat'] if entry['target_id'] == target else 0.0
        recycle_share = 0.0
        score = next(p['conditional_threat'] for p in passing if p['target_id'] == target)
    # Optional tactical guardrail: releasing one's authored marking assignment
    # can worsen a team shape without changing the single modelled pass route.
    # Penalty is relative to the SAME phase's hold path and explicitly exposed.
    tracked = players[scene['defender_id']]
    assigned = tracked.get('marking_target_id')
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    decision_time = launch if phase == 'pre' else launch + 0.7
    role_release = 0.0
    if assigned is not None and offside['target_statuses'].get(assigned, {'eligible_target': True})['eligible_target']:
        receiver_here = scripted_position(players[assigned], decision_time)
        def dist(action_name: str) -> float:
            pose = defender_position(scene, action_name, decision_time, phase)
            return hypot(pose['x'] - receiver_here['x'], pose['y'] - receiver_here['y'])
        # Penalize increased separation; moving closer is not rewarded twice.
        role_release = ROLE_RELEASE_WEIGHT * max(0.0, dist(action) - dist('hold')) / 5.0
        score += role_release
    return {'score': score, 'pass_threat_index': score - role_release,
            'role_release_penalty': role_release,
            'assigned_target_id': assigned, 'passes': passing,
            'offside': offside,
            'recycle_choice_index': recycle_share}


def _round_lane(p: dict) -> dict:
    """Round only serialized diagnostics, never intermediate calculations."""
    result = {key: (round(value, 5) if isinstance(value, float) else value)
              for key, value in p.items() if key != 'defenders'}
    result['defenders'] = [
        {key: round(value, 5) if isinstance(value, float) else value
         for key, value in defender.items()}
        for defender in p['defenders']
    ]
    # Compatibility field names to let the old React app remain functional;
    # their 'probability' naming is historical only (see model_warning).
    result.update({
        'weight': result['pass_choice_index'],
        'blocked_probability': result['team_coverage_index'],
        'completion_probability': result['completion_index'],
        'contribution': result['weighted_threat'],
        'tracked_min_separation_m': result['tracked_min_gap_m'],
        'tracked_closest_time_s': result['tracked_closest_time_s'],
        'tracked_interception_proxy': result['tracked_coverage_index'],
    })
    return result


def evaluate_hybrid(scene: dict, action: str, phase: str = 'pre') -> dict:
    _validate_scene(scene)
    if (action not in ACTIONS and not (action == 'observed' and scene.get('player_centric'))) or phase not in ('pre', 'post'):
        raise ValueError('Invalid action or decision phase')
    calc = _decision_value(scene, action, phase)
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    observed = next(p for p in calc['passes'] if p['target_id'] == scene['observed_pass_target_id'])
    final_time = max(PLANNING_HORIZON_S, launch + observed['flight_time_s'])
    return {
        'action': action, 'label': ('Authored movement' if action == 'observed' else (_LOCAL_LABELS[action] if scene.get('movement_frame')=='body' and scene.get('player_centric') else ACTION_LABELS[action])),
        'score': round(calc['score'], 5),
        'pass_threat_index': round(calc['pass_threat_index'], 5),
        'role_release_penalty': round(calc['role_release_penalty'], 5),
        'assigned_target_id': calc['assigned_target_id'],
        'offside': calc['offside'],
        'position': {key: round(defender_position(scene, action, PLANNING_HORIZON_S if phase == 'pre' else launch + 1.0, phase)[key], 3)
                     for key in ('x', 'y')},
        'trajectory': [
            {'t': round(i*final_time/60, 4),
             'x': round(defender_position(scene, action, i*final_time/60, phase)['x'], 3),
             'y': round(defender_position(scene, action, i*final_time/60, phase)['y'], 3)}
            for i in range(61)
        ],
        'passes': [_round_lane(p) for p in calc['passes']],
        'player_trajectories': {
            player['id']: [
                {'t': round(i * final_time / 60, 4),
                 'x': round((observed_position(scene, player, i * final_time / 60) if scene.get('player_centric') else scripted_position(player, i * final_time / 60))['x'], 3),
                 'y': round((observed_position(scene, player, i * final_time / 60) if scene.get('player_centric') else scripted_position(player, i * final_time / 60))['y'], 3)}
                for i in range(61)]
            for player in scene['players'] if player['id'] != scene['defender_id']
        },
        'recycle_choice_index': round(calc['recycle_choice_index'], 5),
        'observed_pass': _round_lane(observed),
    }


def _phase_summary(scene: dict, phase: str) -> dict:
    opts = [evaluate_hybrid(scene, action, phase) for action in ACTIONS]
    hold = next(item for item in opts if item['action'] == 'hold')
    if scene.get('player_centric'):
        authored = evaluate_hybrid(scene, 'observed', phase)
        all_paths = [*opts, authored]
        best = min(all_paths, key=lambda item: item['score'])
        best_nine = min(opts, key=lambda item: item['score'])
        # Attributions compare SAME selected player, same time and background.
        impact = hold['score'] - authored['score']
        gap = max(0.0, authored['score'] - best['score'])
        candidate_spread = max(x['score'] for x in all_paths) - min(x['score'] for x in all_paths)
        return {
            'options': opts, 'observed_option': authored,
            'baseline_score': hold['score'],
            'actual_action': 'observed', 'actual_score': authored['score'],
            'optimal_action': best['action'], 'optimal_score': best['score'],
            'best_tested_action': best_nine['action'], 'best_tested_score': best_nine['score'],
            'defensive_impact': round(impact, 5),
            'decision_gap': round(gap, 5),
            'gap_actual_vs_best': round(gap, 5),
            'influence_range': round(candidate_spread, 5),
            'relevance': 'low_model_influence' if candidate_spread < .008 else 'meaningful_model_variation',
        }
    actual = next(item for item in opts if item['action'] == scene['actual_action'])
    best = min(opts, key=lambda item: item['score'])
    return {
        'options': opts, 'baseline_score': hold['score'],
        'actual_action': actual['action'], 'actual_score': actual['score'],
        'optimal_action': best['action'], 'optimal_score': best['score'],
        'gap_actual_vs_best': round(max(0, actual['score']-best['score']), 5),
    }


def analyze_hybrid(scene: dict) -> dict[str, Any]:
    _validate_scene(scene)
    pre = _phase_summary(scene, 'pre')
    post = _phase_summary(scene, 'post')
    launch = float(scene.get('pass_launch_delay_s', PASS_LAUNCH_DELAY_S))
    return {
        'model': 'synthetic-hybrid-counterfactual-v0.6' if scene.get('player_centric') else 'synthetic-hybrid-counterfactual-v0.5',
        'model_warning': (
            'Uncalibrated synthetic heuristics: coverage and choice indices are NOT '
            'probabilities, xG, xT, EPV or player ratings; no learned model or real match data. '
            'Offside flags are point-based approximations, not referee decisions.'
        ),
        'scene': scene,
        'movement_frame': 'body' if scene.get('player_centric') and scene.get('movement_frame')=='body' else 'pitch',
        'decision_facing_deg': {'pre': round(decision_facing_deg(scene,'pre'),4), 'post': round(decision_facing_deg(scene,'post'),4)},
        'observed_pass_target_id': scene['observed_pass_target_id'],
        'assumptions': {
            'pass_speed_mps': float(scene.get('pass_speed_mps', PASS_SPEED_MPS)),
            'pass_launch_delay_s': launch,
            'defender_max_speed_mps': MAX_SPEED_MPS,
            'defender_reaction_delay_s': REACTION_DELAY_S,
            'movement_horizon_s': PLANNING_HORIZON_S,
            'scripted_background_motion': True,
            'background_motion_limit_s': PLAYER_MOTION_LIMIT_S,
            'assignment_aware_receiver_pressure': True,
            'optional_role_release_guardrail': True,
            'adaptive_pre_pass_choice': True,
            'post_pass_target_fixed': True,
            'conditional_post_moves_start_at_launch': True,
            'contact_radius_m': CONTACT_RADIUS_M,
            'recycle_option_prior': RECYCLE_PRIOR,
            'offside_evaluated_at_pass_touch': True,
            'offside_point_position_only': True,
            'candidate_direction_reference': 'synthetic player body at decision instant, fixed throughout candidate',
            'offside_conditional_involvement_assumed': True,
            'offside_exempt_restarts': ['goal_kick', 'throw_in', 'corner_kick'],
        },
        'pre_pass': pre, 'post_pass': post,
        # Backward-compatible summary fields for existing React Vite application:
        **pre,
    }

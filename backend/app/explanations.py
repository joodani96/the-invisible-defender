"""Grounded, deterministic decision explanations for the fictional hybrid model.

The narrative is assembled ONLY from the numeric components published by the
engine. It is intentionally not an LLM or a trained xG/xT/EPV model.
"""
from __future__ import annotations

from .hybrid import RECYCLE_VALUE


def _f(n: float) -> str:
    return f"{n:.3f}"


def _word(n: float) -> str:
    if n > .002:
        return 'reduces'
    if n < -.002:
        return 'increases'
    return 'barely changes'


def _score_parts(option: dict, phase: str) -> list[dict]:
    parts = [{
        'key': f"pass:{p['target_id']}", 'label': f"Pass toward {p['target_name']}",
        'value': float(p['weighted_threat']), 'kind': 'pass',
        'description': 'Attack choice share × conditional attacking value (both heuristic indices).',
    } for p in option['passes']]
    if phase == 'pre':
        parts.append({'key': 'recycle', 'label': 'Recycle possession',
                      'value': float(option['recycle_choice_index']) * RECYCLE_VALUE,
                      'kind': 'recycle',
                      'description': 'Modelled alternative to either direct pass; not an observed event.'})
    parts.append({'key': 'role', 'label': 'Marking responsibility',
                  'value': float(option['role_release_penalty']), 'kind': 'role',
                  'description': 'Extra penalty for increasing separation from the assigned attacker.'})
    return parts


def explain_option(scene: dict, phase: str, baseline: dict, option: dict,
                   phase_summary: dict) -> dict:
    """Compare one feasible candidate to hold; all options share a baseline.

    The additive differences reconcile to the reported score except for engine
    output rounding. This is NOT a causal decomposition of football outcomes.
    """
    old = {p['key']: p for p in _score_parts(baseline, phase)}
    now = _score_parts(option, phase)
    contribution = []
    for part in now:
        old_value = old[part['key']]['value']
        effect = old_value - part['value']
        contribution.append({**part,
            'value': round(part['value'], 5),
            'hold_value': round(old_value, 5),
            'reduction_vs_hold': round(effect, 5),
        })
    contribution.sort(key=lambda p: abs(p['reduction_vs_hold']), reverse=True)
    score = float(option['score'])
    hold = float(baseline['score'])
    reduction = hold - score
    lead = contribution[0] if contribution else None
    selected_number = next(p['number'] for p in scene['players'] if p['id'] == scene['defender_id'])
    target_id = scene['observed_pass_target_id']
    selected_pass = next(p for p in option['passes'] if p['target_id'] == target_id)
    base_pass = next(p for p in baseline['passes'] if p['target_id'] == target_id)
    changed_offside = [
        p['target_name'] for p in option['passes']
        if p['offside_position'] != next(x for x in baseline['passes'] if x['target_id'] == p['target_id'])['offside_position']
    ]
    if abs(reduction) <= .002:
        summary = f"Defender #{selected_number}: {option['label']} makes little difference to the modelled attack value compared with holding position."
    else:
        summary = (f"Defender #{selected_number}: {option['label']} {_word(reduction)} the modelled attack value "
                   f"by {_f(abs(reduction))} index units versus holding position "
                   f"({_f(hold)} → {_f(score)}).")
    if lead and abs(lead['reduction_vs_hold']) > .001:
        verb = 'decreases' if lead['reduction_vs_hold'] > 0 else 'increases'
        reason = (f"The biggest numerical contribution is {lead['label'].lower()}: "
                  f"its weighted component {verb} by {_f(abs(lead['reduction_vs_hold']))} index units.")
    else:
        reason = 'None of the model components changes substantially in this comparison.'
    if phase == 'pre':
        context = ('Before the pass, the attacker can choose among eligible targets or recycle possession. '
                   'The selected movement may affect which option the model favours.')
        if changed_offside:
            context += ' Changed offside-position status at the kick: ' + ', '.join(changed_offside) + '.'
        else:
            context += ' The modelled offside-position status of available targets does not change.'
    else:
        context = (f"After the pass, the target stays {selected_pass['target_name']}. "
                   'The attacker cannot retroactively choose another passing lane.')
        if selected_pass['contact_time_s'] is not None:
            who = selected_pass['contact_defender_id']
            person = next((p for p in scene['players'] if p['id'] == who), None)
            marker = f"#{person['number']}" if person else str(who)
            context += (f" This simplified replay shows geometric ball contact by defender {marker} "
                        f"at {selected_pass['contact_time_s']:.2f}s; that is not a proven real-world interception probability.")
        else:
            context += (f" No defender enters the model's geometric ball-contact radius. "
                        f"Closest approach of the focused defender is {selected_pass['tracked_min_gap_m']:.2f}m.")
    relevance = phase_summary['relevance']
    comparison_gap = float(phase_summary['decision_gap'])
    comparison = (f"The authored movement is {_f(comparison_gap)} index units above "
                  f"the lowest tested counterfactual, conditional on the scripted teammates.")
    if relevance == 'low_model_influence':
        comparison += ' This defender has low influence in the modelled situation; differences should not be overinterpreted.' 
    caveat = ('These are uncalibrated, synthetic index units; not xG, goal odds, a player grade or a referee offside verdict. '
              'Other players follow fixed scripted trajectories, so the result does not model adaptive teamwork.')
    fan = ' '.join([summary, reason, context, comparison, 'This is a simulated estimate, not a guaranteed match outcome.'])
    analyst = ' '.join([
        f"MODEL COMPARISON | defender #{selected_number}, hold={_f(hold)}, selected={_f(score)}, reduction={_f(reduction)}.",
        f"Pass threat={_f(option['pass_threat_index'])}; role-release penalty={_f(option['role_release_penalty'])}.",
        reason, context,
        (f"Authored defensive impact={_f(phase_summary['defensive_impact'])}; "
         f"decision gap={_f(phase_summary['decision_gap'])}."),
        caveat,
    ])
    return {
        'action': option['action'], 'label': option['label'],
        'phase': phase, 'selected_defender_id': scene['defender_id'],
        'hold_score': round(hold, 5), 'selected_score': round(score, 5),
        'reduction_vs_hold': round(reduction, 5),
        'components': contribution,
        'reconstructed_score': round(sum(p['value'] for p in now), 5),
        'primary_reason_key': lead['key'] if lead else None,
        'offside_status_changed': bool(changed_offside),
        'observed_pass_status': {
            'offside_position': selected_pass['offside_position'],
            'baseline_offside_position': base_pass['offside_position'],
            'target_id': target_id,
        },
        'relevance': relevance, 'commentary': {'fan': fan, 'analyst': analyst},
        'model_limitations': caveat,
    }


def with_explanations(analysis: dict) -> dict:
    """Attach per-option explanations without changing original model scores."""
    scene = analysis['scene']
    for phase_name, phase in (('pre_pass', 'pre'), ('post_pass', 'post')):
        summary = analysis[phase_name]
        hold = next(o for o in summary['options'] if o['action'] == 'hold')
        paths = [*summary['options'], summary['observed_option']]
        summary['explanations'] = {
            o['action']: explain_option(scene, phase, hold, o, summary)
            for o in paths
        }
        summary['explainability_note'] = (
            'An additive model-component audit, not causal feature attribution. '
            'Time window comes from the authored scenario; it cannot be extended independently of player and ball trajectories.'
        )
    analysis['model'] = 'synthetic-explainable-counterfactual-v0.7'
    analysis['commentary_generator'] = 'deterministic_grounded_templates_v1 (NOT AI/Foundry)'
    return analysis

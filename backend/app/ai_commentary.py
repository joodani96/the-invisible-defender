"""Grounded optional Microsoft Foundry multi-agent commentary.

The hybrid engine is the ONLY source of numeric facts. Two real Agent
Framework agents operate sequentially only when Foundry is configured:
  1) TacticalEditor selects approved evidence IDs.
  2) CommentaryWriter creates a short audience-specific narrative.
The output is checked against an evidence allowlist and the model's numbers.
No credentials or external LLM are required for offline/fallback mode.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Callable, Awaitable

from .player_analysis import analyze_player

VALID_PHASES = {'pre': 'pre_pass', 'post': 'post_pass'}
NUMBER = re.compile(r'(?<![\w])[-+]?\d+(?:\.\d+)?%?')


class GroundingError(ValueError):
    pass


@dataclass(frozen=True)
class Evidence:
    id: str
    label: str
    fact: str

    def as_dict(self) -> dict:
        return {'id': self.id, 'label': self.label, 'fact': self.fact}


def packet_from_analysis(analysis: dict, phase: str, action: str) -> dict:
    if phase not in VALID_PHASES:
        raise ValueError('Invalid phase')
    summary = analysis[VALID_PHASES[phase]]
    explanation = summary['explanations'].get(action)
    if explanation is None:
        raise ValueError('Unknown action')
    option = (summary['observed_option'] if action == 'observed'
              else next(item for item in summary['options'] if item['action'] == action))
    player = analysis['selected_defender']
    items: list[Evidence] = [
        Evidence('E1', 'Decision', f"Defender #{player['number']}, {option['label']}, "
                 f"{('before' if phase == 'pre' else 'after')} the pass."),
        Evidence('E2', 'Modelled attacking index',
                 f"Holding position: {explanation['hold_score']:.3f}. "
                 f"Selected movement: {explanation['selected_score']:.3f}. "
                 f"Reduction versus holding: {explanation['reduction_vs_hold']:+.3f} index units."),
        Evidence('E3', 'Decision quality context',
                 f"Authored defensive impact: {summary['defensive_impact']:+.3f} index units. "
                 f"Authored-versus-best-tested decision gap: {summary['decision_gap']:.3f} index units. "
                 'These indices are not calibrated xG values or player ratings.'),
    ]
    components = explanation['components']
    for i, component in enumerate(components[:3], start=4):
        items.append(Evidence(f'E{i}', component['label'],
                     f"{component['label']} contributes {component['reduction_vs_hold']:+.3f} index units "
                     'to the change versus holding; this is model-component accounting, not causal proof.'))
    items.append(Evidence('E7', 'Offside and pass timing',
                          ('Before the pass: potential targets and offside positioning are evaluated at ball release.'
                           if phase == 'pre' else
                           'After the pass: target selection and offside status are fixed at ball release.')))
    if explanation['offside_status_changed']:
        items.append(Evidence('E8', 'Offside change',
                              'The tested defender movement changes at least one target’s offside-position status at ball release. '
                              'Offside position alone is not an offence.'))
    else:
        items.append(Evidence('E8', 'Offside unchanged',
                              'The tested defender movement does not change the modelled offside-position status of the targets.'))
    observed = option['observed_pass']
    if phase == 'post':
        if observed['contact_time_s'] is not None:
            items.append(Evidence('E9', 'Ball-contact simulation',
                         f"A defender reaches the ball's simplified contact radius at {observed['contact_time_s']:.2f} s. "
                         'This is geometric simulated contact, not a validated interception probability.'))
        else:
            items.append(Evidence('E9', 'Ball-contact simulation',
                                  'No defender reaches the ball-contact radius in the simulated replay.'))
    else:
        items.append(Evidence('E9', 'Decision window',
                     f"The ball is released {analysis['assumptions']['pass_launch_delay_s']:.2f} s "
                     'after the starting frame; not all desired moves are reachable in that window.'))
    items.append(Evidence('E10', 'Model limitations',
                          'The match is synthetic. Teammate trajectories and tactical roles are scripted. '
                          'Scores are heuristic threat-index units, NOT xG or goal probabilities.'))
    return {
        'scenario_id': analysis['scene']['id'], 'defender_id': player['id'],
        'phase': phase, 'action': action, 'audience': None,
        'evidence': [e.as_dict() for e in items],
        'fallback_commentary': explanation['commentary'],
    }


def parse_json_object(text: str) -> dict:
    """Accept plain JSON or a fenced JSON block, reject extra material."""
    trimmed = text.strip()
    if trimmed.startswith('```'):
        match = re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```', trimmed)
        if not match:
            raise GroundingError('Unexpected content around JSON')
        trimmed = match.group(1)
    try:
        parsed = json.loads(trimmed)
    except (ValueError, TypeError) as exc:
        raise GroundingError('Agent returned invalid JSON') from exc
    if not isinstance(parsed, dict):
        raise GroundingError('Agent JSON must be an object')
    return parsed


def select_evidence(text: str, packet: dict) -> list[dict]:
    parsed = parse_json_object(text)
    ids = parsed.get('selected_ids')
    permitted = {e['id']: e for e in packet['evidence']}
    if not isinstance(ids, list) or not 2 <= len(ids) <= 4 or any(not isinstance(x, str) for x in ids):
        raise GroundingError('Expected 2–4 evidence IDs')
    if len(ids) != len(set(ids)) or any(i not in permitted for i in ids):
        raise GroundingError('Agent referenced unsupported evidence')
    # Always present the model's important limitation, even if an agent omits it.
    if 'E10' not in ids:
        ids.append('E10')
    return [permitted[i] for i in ids]


def verify_narrative(text: str, chosen: list[dict]) -> str:
    parsed = parse_json_object(text)
    narrative = parsed.get('commentary')
    cited = parsed.get('evidence_ids')
    if not isinstance(narrative, str) or not 30 <= len(narrative) <= 680:
        raise GroundingError('Commentary is missing or too long')
    allowed = {e['id'] for e in chosen}
    if not isinstance(cited, list) or not cited or any(i not in allowed for i in cited):
        raise GroundingError('Narrative lacks valid evidence references')
    # No invented numeric data: all numeric tokens must appear VERBATIM in
    # the evidence facts provided to this agent, including #shirt numbers.
    number_allowlist = set(NUMBER.findall(' '.join(e['fact'] for e in chosen)))
    unsupported = set(NUMBER.findall(narrative)) - number_allowlist
    if unsupported:
        raise GroundingError('Narrative contains unsupported numbers: ' + ', '.join(sorted(unsupported)))
    if any(mark in narrative for mark in ('```', '<script', '</', '{', '}')):
        raise GroundingError('Unsupported markup in narrative')
    return narrative.strip()


async def _real_foundry_run(packet: dict, audience: str) -> tuple[str, list[dict]]:
    """Actual MAF agents with Microsoft Foundry; never invoked offline.

    Uses the published 2026 FoundryChatClient + Agent API. The project's
    Locally the Azure CLI credential is used; on Azure choose Managed Identity
    via TID_AZURE_CREDENTIAL. No secret is embedded or exposed to the browser.
    """
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import AzureCliCredential, ManagedIdentityCredential

    credential_mode = os.getenv('TID_AZURE_CREDENTIAL', 'azure_cli').strip().lower()
    if credential_mode == 'azure_cli':
        credential = AzureCliCredential()
    elif credential_mode == 'managed_identity':
        credential = ManagedIdentityCredential()
    else:
        raise ValueError('TID_AZURE_CREDENTIAL must be azure_cli or managed_identity')
    client = FoundryChatClient(
        credential=credential,
        project_endpoint=os.environ['FOUNDRY_PROJECT_ENDPOINT'],
        model=os.environ['FOUNDRY_MODEL'],
    )
    selector = Agent(
        client=client,
        name='TacticalEvidenceEditor',
        instructions=(
            'You are a football tactics evidence editor. From the supplied numbered evidence facts, '
            'select the 2–4 most explanatory evidence IDs for the chosen defensive action. '
            'Prioritize decision impact, meaningful team coverage and offside/time constraints. '
            'Do not invent facts. Respond ONLY JSON: {"selected_ids":["E2","E4"]}. '
            'Do not speculate about real-world player skill or call threat indices xG.'
        ),
    )
    editor_result = await selector.run(json.dumps({
        'audience': audience, 'phase': packet['phase'],
        'evidence': packet['evidence']}, ensure_ascii=False))
    chosen = select_evidence(getattr(editor_result, 'text', str(editor_result)), packet)
    writer = Agent(
        client=client,
        name='TacticalCommentaryWriter',
        instructions=(
            'Write a clear football tactical commentary using ONLY the supplied evidence facts. '
            'Do not invent scores, player intentions, successful interceptions or goal probabilities. '
            'Do not convert threat indices into percentages or xG. '
            'Audience fan: 2–3 accessible sentences; audience analyst: 3–4 detailed sentences. '
            'Any numeric quantity MUST use exactly the formatting given in the evidence facts. '
            'Return ONLY JSON: {"commentary":"...", "evidence_ids":["E2","E4"]}. '
            'evidence_ids must refer to provided facts that support your commentary. '
            'Describe uncertainty and that the scene is synthetic.'
        ),
    )
    writer_result = await writer.run(json.dumps({'audience': audience, 'evidence': chosen}, ensure_ascii=False))
    narration = verify_narrative(getattr(writer_result, 'text', str(writer_result)), chosen)
    return narration, chosen


def provider_status() -> dict:
    configured = bool(os.getenv('FOUNDRY_PROJECT_ENDPOINT') and os.getenv('FOUNDRY_MODEL'))
    enabled = os.getenv('TID_AI_PROVIDER', 'offline').lower() == 'foundry'
    return {
        'mode': 'foundry' if enabled and configured else 'offline',
        'foundry_configured': configured,
        'foundry_enabled': enabled,
        'description': ('Foundry agents enabled; Azure credentials must also be available.'
                        if enabled and configured else
                        'Offline evidence-grounded commentary; set TID_AI_PROVIDER=foundry and Foundry variables to enable agents.'),
    }


async def generate_commentary(analysis: dict, phase: str, action: str, audience: str,
                              runner: Callable[[dict, str], Awaitable[tuple[str, list[dict]]]] | None = None) -> dict:
    if audience not in {'fan', 'analyst'}:
        raise ValueError('Invalid audience')
    packet = packet_from_analysis(analysis, phase, action)
    packet['audience'] = audience
    result = {
        'commentary': packet['fallback_commentary'][audience],
        'provider': 'offline', 'generated_by_ai': False,
        'evidence': packet['evidence'], 'phase': phase,
        'audience': audience, 'defender_id': packet['defender_id'],
        'action': action, 'validation': 'deterministic',
        'warning': 'No AI was used. Commentary assembled from the model’s existing deterministic explanation.',
        'agent_steps': [],
    }
    if runner is None and provider_status()['mode'] != 'foundry':
        return result
    try:
        if runner is None:
            runner = _real_foundry_run
        narration, chosen = await asyncio.wait_for(runner(packet, audience), timeout=35.0)
        # Even injected runners must pass the post-check; do not trust tests/providers.
        allowed_ids = {item['id'] for item in packet['evidence']}
        if any(item['id'] not in allowed_ids for item in chosen):
            raise GroundingError('Selected facts not present in source analysis')
        # The online runner validates its original JSON. Recheck numbers independently.
        whitelist = set(NUMBER.findall(' '.join(e['fact'] for e in chosen)))
        if set(NUMBER.findall(narration)) - whitelist:
            raise GroundingError('Unapproved numeric claims')
        result.update({
            'commentary': narration, 'provider': 'microsoft_foundry_agent_framework',
            'generated_by_ai': True, 'evidence': chosen,
            'validation': 'numeric_and_evidence_ids_checked',
            'warning': 'AI prose is grounded in selected evidence, but semantic accuracy still requires editorial review.',
            'agent_steps': ['TacticalEvidenceEditor', 'TacticalCommentaryWriter'],
        })
    except Exception as exc:
        # Fail closed: never present unsuccessful or ungrounded LLM output as evidence.
        result['warning'] = f'AI unavailable or failed grounding validation ({type(exc).__name__}); showing deterministic explanation.'
        result['validation'] = 'fallback'
    return result

/* Model-grounded evidence to 3D presentation mapping; no AI inference or new football metrics.
 * Pure helpers so the mapping is tested independently of Babylon/WebGL. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TIDHighlights = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const valid = new Set(['E1','E2','E3','E4','E5','E6','E7','E8','E9','E10']);
  const byId = (packet, id) => (packet?.evidence || []).find(e => e.id === id);
  function mapEvidence(e, option, phase) {
    if (!e || !valid.has(e.id)) return null;
    const id = e.id, label = String(e.label || 'Evidence');
    if (/^E[456]$/.test(id)) {
      const pass = (option?.passes || []).find(p => label === `Pass toward ${p.target_name}`);
      // Other accounting factors are text-only: do not point at arbitrary geometry.
      if (pass) return {id, type:'lane', targetId:pass.target_id, label, fact:e.fact};
      return {id,type:'context',label,fact:e.fact};
    }
    if (id==='E8' || id==='E7') return {id,type:'offside',label,fact:e.fact};
    if (id==='E3') return {id,type:'movements',label,fact:e.fact};
    if (id==='E9') return {id,type:phase==='post'?'contact':'timing',label,fact:e.fact};
    return {id,type:'context',label,fact:e.fact};
  }
  function planEvidence(packet, option, phase) {
    if (!packet || !Array.isArray(packet.evidence)) return [];
    return packet.evidence.map(e=>mapEvidence(e,option,phase)).filter(Boolean);
  }
  function leadLane(explanation, option) {
    const lead=(explanation?.components||[]).find(c=>c.kind==='pass' && Math.abs(c.reduction_vs_hold)>0.001);
    if (!lead) return null;
    const p=(option?.passes||[]).find(p=>lead.key===`pass:${p.target_id}`);
    return p ? p.target_id : null;
  }
  function bestOption(summary) {
    if (!summary) return null;
    return (summary.options||[]).find(o=>o.action===(summary.best_tested_action || summary.optimal_action)) || summary.observed_option;
  }
  // Movement arrows use common physical time, never infer trajectory from score.
  function movementComparison(summary, time, sample) {
    const authored = summary?.observed_option;
    const best = bestOption(summary);
    if (!authored||!best) return null;
    return {actualStart:sample(authored.trajectory,0),actualEnd:sample(authored.trajectory,time),
      bestStart:sample(best.trajectory,0),bestEnd:sample(best.trajectory,time),
      samePath:best===authored, bestAction:summary.best_tested_action || summary.optimal_action};
  }
  return {mapEvidence,planEvidence,leadLane,bestOption,movementComparison};
});

/* Pure, shared replay adapter for the unified 2D/3D studio. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TIDStudioCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function summary(data, phase) { return data[phase === 'post' ? 'post_pass' : 'pre_pass']; }
  function option(data, phase, action) {
    const s = summary(data, phase);
    return action === 'observed' ? s.observed_option : s.options.find(o => o.action === action) || s.observed_option;
  }
  function replayEvent(data, phase, action) {
    const launch = data.assumptions.pass_launch_delay_s;
    if (phase === 'pre') return {type:'kick', time:launch};
    const pass = option(data,phase,action).observed_pass;
    const arrival = launch + pass.flight_time_s;
    const contact = pass.contact_time_s;
    if (Number.isFinite(contact) && contact >= launch - 1e-8 && contact <= arrival + 1e-8) {
      return {type:'contact', time:contact, defenderId:pass.contact_defender_id};
    }
    return {type:'arrival', time:arrival};
  }
  function endTime(data, phase, action) {
    // Never show players continuing to run after the ball has been frozen at
    // first geometric contact. The two views must stop on the SAME event.
    return replayEvent(data,phase,action).time;
  }
  function positionFor(p, data, opt, time, replayMath) {
    const path = p.id === data.scene.defender_id ? opt.trajectory : opt.player_trajectories[p.id];
    return replayMath.sample(path, time) || {x:p.x,y:p.y};
  }
  function ballFor(data, opt, phase, time, replayMath) {
    const passer = data.scene.players.find(p=>p.id===data.scene.ball_holder_id);
    return replayMath.ballPosition({phase, time, launch:data.assumptions.pass_launch_delay_s,
      passer:positionFor(passer,data,opt,time,replayMath), pass:opt.observed_pass});
  }
  function delta(hold, chosen) { return hold - chosen; }
  return {summary, option, replayEvent, endTime, positionFor, ballFor, delta};
});

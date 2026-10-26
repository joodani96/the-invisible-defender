/* v0.9.3: deterministic, render-only player orientation.
   Pitch degrees: 0 => +X (right goal), 90 => +Y (lower touchline).
   This is synthetic, not optical head tracking or an interception-model input. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TIDOrientation = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const normalize = angle => ((angle % 360) + 360) % 360;
  const shortestTurn = (from, to) => ((normalize(to) - normalize(from) + 540) % 360) - 180;
  const turnTowards = (from, to, maxDegrees) => normalize(from + Math.max(-maxDegrees, Math.min(maxDegrees, shortestTurn(from, to))));
  const heading = (dx, dy) => normalize(Math.atan2(dy, dx) * 180 / Math.PI);
  const pitchForward = degrees => ({x: Math.cos(degrees * Math.PI / 180), y: Math.sin(degrees * Math.PI / 180)});
  const worldYaw = degrees => (degrees - 90) * Math.PI / 180;
  const samplePoint = (points, t) => {
    if (!points?.length) return null;
    if (t <= points[0].t) return points[0];
    for (let i=1; i<points.length; i++) {
      if (t <= points[i].t) {
        const a=points[i-1],b=points[i],span=b.t-a.t;
        const f=span>0?(t-a.t)/span:0;
        return {x:a.x+(b.x-a.x)*f,y:a.y+(b.y-a.y)*f};
      }
    }
    return points[points.length-1];
  };
  function movementAt(path, time, windowSeconds=.12) {
    if (!path || path.length<2) return {speedMps:0, headingDeg:null};
    const first=path[0].t,last=path[path.length-1].t;
    if(last-first<1e-7) return {speedMps:0,headingDeg:null};
    // One-sided sampling at clip boundaries prevents wraparound/seek artifacts.
    const a=Math.max(first, Math.min(time-windowSeconds/2,last));
    const b=Math.min(last, Math.max(time+windowSeconds/2,first));
    const low=b-a<.001?Math.max(first,last-windowSeconds):a;
    const high=b-a<.001?last:b;
    const p=samplePoint(path,low),q=samplePoint(path,high),dt=high-low;
    if(!p||!q||dt<=0) return {speedMps:0,headingDeg:null};
    const dx=q.x-p.x,dy=q.y-p.y,velocity=Math.hypot(dx,dy)/dt;
    return {speedMps:velocity,headingDeg:velocity>0.0001?heading(dx,dy):null};
  }
  function playerPose(player, path, time) {
    const initial = normalize(Number.isFinite(player.body_facing_deg) ? player.body_facing_deg : 0);
    const move=movementAt(path,time);
    // Orientation follows travel only if there is material displacement.
    // This heuristic does NOT change movement reachability or threat scores.
    const preferred=move.speedMps>=0.65 && move.headingDeg!==null ? move.headingDeg : initial;
    const turnBudget=Math.max(0,time)*165; // deg/s, stylized rotation for presentation
    const facing=turnTowards(initial,preferred,turnBudget);
    return {bodyFacingDeg:facing, movementHeadingDeg:move.headingDeg,
      speedMps:move.speedMps, facingSource:player.facing_source || 'synthetic'};
  }
  return {normalize,shortestTurn,turnTowards,heading,pitchForward,worldYaw,movementAt,playerPose};
});

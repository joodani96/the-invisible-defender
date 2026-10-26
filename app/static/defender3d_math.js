/* Pure 3D replay math, shared by the viewer and node:test checks. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TIDReplayMath = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const clamp = (x, low, high) => Math.min(high, Math.max(low, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  function sample(points, time) {
    if (!points || !points.length) return null;
    if (time <= points[0].t) return { x: points[0].x, y: points[0].y };
    for (let i = 1; i < points.length; i++) {
      if (time <= points[i].t) {
        const a = points[i - 1], b = points[i];
        const f = clamp((time - a.t) / (b.t - a.t || 1), 0, 1);
        return { x: lerp(a.x, b.x, f), y: lerp(a.y, b.y, f) };
      }
    }
    return {x: points[points.length - 1].x, y: points[points.length - 1].y};
  }
  function ballPosition({ phase, time, launch, passer, pass }) {
    if (phase === 'pre' || time < launch) return {x: passer.x, y: passer.y};
    const flightFraction = clamp((time - launch) / Math.max(pass.flight_time_s, .001), 0, 1);
    const contactFraction = pass.contact_time_s != null && time >= pass.contact_time_s && pass.contact_fraction != null
      ? pass.contact_fraction : flightFraction;
    return { x: lerp(pass.pass_start.x, pass.pass_end.x, contactFraction),
             y: lerp(pass.pass_start.y, pass.pass_end.y, contactFraction) };
  }
  function toWorld(p, height=0) { return {x:p.x-52.5, y:height, z:34-p.y}; }
  return { sample, ballPosition, toWorld };
});

/* v0.9.10 – Player-relative decision geometry and stable, readable graphics.
   Python remains authoritative for all movement trajectories and scores. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TIDDecisions = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  // Grid is local to the player: top = where the BODY faces, left =
  // player's own left. The backend computes the same movement vectors.
  const localSlots = [
    ['forward-up','forward','forward-down'],
    ['up','hold','down'],
    ['backward-up','backward','backward-down']
  ];
  function grid() { return localSlots.map(row=>[...row]); }
  const arrows = { 'forward-up':'↖','forward':'↑','forward-down':'↗',
    'up':'←','hold':'●','down':'→',
    'backward-up':'↙','backward':'↓','backward-down':'↘' };
  function arrowFor(action) { return arrows[action] || '·'; }
  function groundArrowGlyph(action) { return action==='hold' ? '●' : '↑'; }
  const localCoords={
    'forward-up':[-1,1], 'forward':[0,1], 'forward-down':[1,1],
    'up':[-1,0], 'hold':[0,0], 'down':[1,0],
    'backward-up':[-1,-1], 'backward':[0,-1], 'backward-down':[1,-1]
  };
  function candidateVector(action,bodyFacingDeg) {
    if(!(action in localCoords)||!Number.isFinite(bodyFacingDeg))throw Error('Invalid local movement');
    const [right,forward]=localCoords[action];
    const scale=Math.hypot(right,forward)||1, f=forward/scale, r=right/scale;
    const angle=bodyFacingDeg*Math.PI/180;
    return {x:f*Math.cos(angle)-r*Math.sin(angle),y:f*Math.sin(angle)+r*Math.cos(angle)};
  }
  // PITCH X,Y: passer's attacking X horizontal, positive Y downward.
  // This constructs a SYMBOLIC ground decision selector, not a predicted
  // displacement magnitude. Real trajectory arrows use API positions.
  function groundMarkerPosition(origin,action,bodyFacingDeg,radius=4.2) {
    const direction=candidateVector(action,bodyFacingDeg);
    return {x:origin.x+direction.x*radius,y:origin.y+direction.y*radius};
  }
  // Rotate the ground tile so a generic upward arrow points in the actual
  // player-relative movement direction on the pitch. The underlying tile
  // position is already body-relative; this only fixes the arrow icon.
  function groundMarkerYaw(action,bodyFacingDeg) {
    if(action==='hold') return 0;
    const direction=candidateVector(action,bodyFacingDeg);
    return Math.atan2(direction.x,-direction.y);
  }
  // Pitch +Y is screen-down, while Babylon world Z increases screen-up.
  // A physical arrow in world coordinates cannot be accidentally mirrored by UVs.
  function groundArrowWorldDirection(action,bodyFacingDeg) {
    const d=candidateVector(action,bodyFacingDeg);
    return {x:d.x,z:-d.y};
  }
  // Presentation-only semantic colours, never modify a threat index.
  function tilePalette(kind) {
    return kind==='selected' ? {fill:'#f6fdff', border:'#78edff', ink:'#072d38', badge:'#10b8dc', arrow:'#88f3ff'}
      : kind==='best' ? {fill:'#f3ffe9', border:'#aff483', ink:'#15361d', badge:'#70bb39', arrow:'#b8ff86'}
      : {fill:'#f8fbfb', border:'#d8e7e7', ink:'#14343d', badge:'#7f99a0', arrow:'#e9f8fb'};
  }
  function decisionOrientation(data,phase) {
    const value=data?.decision_facing_deg?.[phase];
    if(!Number.isFinite(value))throw Error('Missing decision orientation');
    return value;
  }
  function deltaVsHold(hold, score) { return hold - score; }
  function bestTested(summary) {
    if(!summary)return null;
    return summary.best_tested_action || summary.options.reduce((best,x)=>x.score<best.score?x:best,summary.options[0]).action;
  }
  // Explicit outward-facing mesh. From a spectator standing behind the player's
  // back (+local Z), vertices and UV run left-to-right together. No backface UV mirroring.
  function shirtBackQuad(width=.58,height=.58) {
    const w=width/2,h=height/2;
    return {
      positions:[-w,-h,0,w,-h,0,w,h,0,-w,h,0],
      indices:[0,1,2,0,2,3],
      normals:[0,0,1,0,0,1,0,0,1,0,0,1],
      // Fix upside-down numbers by flipping V only. U stays left-to-right.
      uvs:[0,0,1,0,1,1,0,1]
    };
  }
  // External cameras retain a PITCH-FIXED viewpoint regardless of body yaw.
  // World coordinates: x along pitch, z toward the upper touchline (minus pitch y).
  function followCameraPose(worldPosition, attackDirection) {
    const sign=attackDirection==='left'?-1:1;
    return {
      position:{x:worldPosition.x+sign*11.5,y:8.0,z:worldPosition.z+8.0},
      target:{x:worldPosition.x-sign*2.5,y:1.45,z:worldPosition.z}
    };
  }
  function broadcastCameraPose() {
    return {position:{x:0,y:32,z:84},target:{x:0,y:0.4,z:0}};
  }
  return {grid,arrowFor,groundArrowGlyph,candidateVector,groundMarkerPosition,groundMarkerYaw,groundArrowWorldDirection,tilePalette,decisionOrientation,deltaVsHold,bestTested,shirtBackQuad,followCameraPose,broadcastCameraPose};
});

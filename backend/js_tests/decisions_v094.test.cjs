const assert = require('node:assert/strict');
const {test} = require('node:test');
const D = require('../app/static/defender3d_decisions.js');

test('3 by 3 local directions: front is top, own left on left',()=>{
  const expected=[
    ['forward-up','forward','forward-down'],
    ['up','hold','down'],
    ['backward-up','backward','backward-down']
  ];
  assert.deepEqual(D.grid(),expected);
  assert.equal(new Set(D.grid().flat()).size,9);
  assert.equal(D.arrowFor('forward'),'↑');
  assert.equal(D.arrowFor('up'),'←');
  assert.equal(D.arrowFor('down'),'→');
});

test('player-local vectors rotate with heading independent of attack direction',()=>{
  const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} vs ${b}`);
  const forward=D.candidateVector('forward',90);
  close(forward.x,0);close(forward.y,1);
  const left=D.candidateVector('up',90);
  close(left.x,1);close(left.y,0);
  const right=D.candidateVector('down',0);
  close(right.x,0);close(right.y,1);
  const back=D.candidateVector('backward',180);
  close(back.x,1);close(back.y,0);
  const diag=D.candidateVector('forward-up',0);
  close(Math.hypot(diag.x,diag.y),1);
  const loc=D.groundMarkerPosition({x:50,y:40},'forward',180,4);
  close(loc.x,46);close(loc.y,40);
  assert.deepEqual(D.decisionOrientation({decision_facing_deg:{pre:170,post:145}},'post'),145);
});
test('defender score differences are relative to hold and best among nine',()=>{
  assert.equal(D.deltaVsHold(.478,.431), .478-.431);
  const summary={best_tested_action:'up',options:[{action:'hold',score:.4},{action:'up',score:.2}]};
  assert.equal(D.bestTested(summary),'up');
});
test('front of the back-number print is +local Z, unmirrored UV with positive winding',()=>{
  const m=D.shirtBackQuad();
  assert.deepEqual(m.uvs,[0,0,1,0,1,1,0,1]);
  // U is still strictly left-to-right, V has been flipped only once.
  assert.equal(m.uvs[0],0); assert.equal(m.uvs[2],1);
  assert.equal(m.uvs[1],0); assert.equal(m.uvs[5],1);
  const p=m.positions;
  const a=[p[3]-p[0],p[4]-p[1]],b=[p[6]-p[0],p[7]-p[1]];
  assert.ok(a[0]*b[1]-a[1]*b[0]>0,'normal is +local Z (viewer behind shirt)');
  assert.equal(m.normals[2],1);
});
test('following camera is independent of heading; broadcast is pitch-fixed',()=>{
  const a=D.followCameraPose({x:12,y:0,z:-6},'right');
  const b=D.followCameraPose({x:12,y:0,z:-6},'right');
  assert.deepEqual(a,b);
  const shifted=D.followCameraPose({x:15,y:0,z:-6},'right');
  assert.equal(shifted.position.x-a.position.x,3);
  assert.equal(shifted.target.x-a.target.x,3);
  const flipped=D.followCameraPose({x:12,y:0,z:-6},'left');
  assert.notEqual(flipped.position.x,a.position.x);
  assert.deepEqual(D.broadcastCameraPose(),D.broadcastCameraPose());
});
test('nine options and camera helpers appear on standalone browser page',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const html=fs.readFileSync(path.join(__dirname,'../app/static/viewer.html'),'utf8');
  const js=fs.readFileSync(path.join(__dirname,'../app/static/defender3d.js'),'utf8');
  assert.match(html, /id="move-pad"/);
  assert.match(html, /id="show-nine-paths"/);
  assert.match(html, /defender3d_decisions\.js/);
  assert.match(js, /renderMovePad\(summary\)/);
  assert.match(js, /drawNineDecisionPaths\(\)/);
  assert.match(js, /makeBackNumber\(p\)/);
});

// v0.9.7: visual annotations must not alter the football-model directions.
test('world-space tile arrows agree with every player-relative candidate',()=>{
  const D=require('../app/static/defender3d_decisions.js');
  const near=(x,y)=>assert.ok(Math.abs(x-y)<1e-9,`${x} vs ${y}`);
  for(const heading of [0,35,90,137,180,270,359]){
    for(const choice of D.grid().flat()){
      const local=D.candidateVector(choice,heading);
      const arrow=D.groundArrowWorldDirection(choice,heading);
      near(arrow.x,local.x);near(arrow.z,-local.y);
      if(choice!=='hold')near(Math.hypot(arrow.x,arrow.z),1);
    }
  }
});
test('ground tiles have high contrast semantic palettes and use fixed printed heading',()=>{
  const D=require('../app/static/defender3d_decisions.js');
  const selected=D.tilePalette('selected'), best=D.tilePalette('best');
  const base=D.tilePalette('default');
  for(const p of [selected,best,base]){
    const rgb=(key)=>[1,3,5].map(i=>parseInt(p[key].slice(i,i+2),16));
    const luminance=(vals)=>vals.reduce((sum,v)=>sum+v,0)/3;
    assert.ok(luminance(rgb('fill'))-luminance(rgb('ink'))>=110);
  }
  const fs=require('node:fs'), path=require('node:path');
  const viewer=fs.readFileSync(path.join(__dirname,'../app/static/defender3d.js'),'utf8');
  assert.match(viewer,/plate\.metadata=\{decisionAction:opt\.action\}/);
  assert.match(viewer,/D\.groundArrowWorldDirection\(action,reference\)/);
  assert.doesNotMatch(viewer,/marker\.rotation\.y=D\.groundMarkerYaw/);
  assert.match(viewer,/CreateBox\(`select-\$\{opt\.action\}`/);
});

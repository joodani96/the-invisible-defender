const assert=require('node:assert/strict');
const {test}=require('node:test');
const o=require('../app/static/defender3d_orientation.js');
function near(a,b,eps=1e-7){assert.ok(Math.abs(a-b)<eps,`${a} != ${b}`)}

test('pitch heading matches world yaw: +X, +Y, -X',()=>{
  near(o.heading(1,0),0);near(o.heading(0,1),90);near(o.heading(-1,0),180);
  near(o.worldYaw(0),-Math.PI/2);near(o.worldYaw(90),0);
  const right=o.pitchForward(0),lower=o.pitchForward(90);
  near(right.x,1);near(right.y,0);near(lower.x,0);near(lower.y,1);
});

test('shortest-angle turn uses wraparound and fixed turn budget',()=>{
  near(o.shortestTurn(350,10),20);
  near(o.shortestTurn(10,350),-20);
  near(o.turnTowards(350,10,5),355);
  near(o.turnTowards(350,10,30),10);
  near(o.turnTowards(10,350,5),5);
});

test('held defender retains authored facing, not motion',()=>{
  const p={body_facing_deg:170,facing_source:'synthetic_authored'};
  const path=[{t:0,x:75,y:33},{t:1,x:75,y:33}];
  const face=o.playerPose(p,path,.5);
  near(face.bodyFacingDeg,170);near(face.speedMps,0);
  assert.equal(face.movementHeadingDeg,null);
  assert.equal(face.facingSource,'synthetic_authored');
});

test('body can lag behind movement and turns toward it over time',()=>{
  const p={body_facing_deg:180};
  const path=[{t:0,x:75,y:33},{t:1,x:78,y:33}];
  const first=o.playerPose(p,path,0);near(first.bodyFacingDeg,180);
  near(first.movementHeadingDeg,0);
  const later=o.playerPose(p,path,.3);
  // 180 -> 0 is the signed shortest path (-180), bounded to 49.5 deg.
  near(later.bodyFacingDeg,130.5);
  const end=o.playerPose(p,path,1);near(end.bodyFacingDeg,15);
});

test('seeking replay is deterministic and sample movement works for both sides',()=>{
  const p={body_facing_deg:15};
  const path=[{t:0,x:30,y:45},{t:.5,x:29,y:44},{t:1,x:28,y:43}];
  const left=o.playerPose(p,path,.65);
  near(left.movementHeadingDeg,225);
  assert.deepEqual(o.playerPose(p,path,.65),left);
  const a=o.playerPose(p,path,.2);
  assert.deepEqual(o.playerPose(p,path,.65),left);
  assert.notDeepEqual(a,left);
});

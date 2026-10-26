const test = require('node:test');
const assert = require('node:assert/strict');
const {sample,ballPosition,toWorld} = require('../app/static/defender3d_math.js');
test('trajectory interpolates without teleporting',()=>{
 const points=[{t:0,x:10,y:20},{t:.5,x:13,y:20},{t:1,x:15,y:22}];
 assert.deepEqual(sample(points,.25),{x:11.5,y:20});
 assert.deepEqual(sample(points,-1),{x:10,y:20});
 assert.deepEqual(sample(points,9),{x:15,y:22});
});
test('before pass, ball remains with passer',()=>{
 const pass={pass_start:{x:30,y:20},pass_end:{x:60,y:40},flight_time_s:2,contact_time_s:null,contact_fraction:null};
 const model={phase:'post',time:.2,launch:.45,passer:{x:30,y:20},pass};
 assert.deepEqual(ballPosition(model),{x:30,y:20});
 assert.deepEqual(ballPosition({...model,time:1.45}),{x:45,y:30});
 assert.deepEqual(ballPosition({...model,phase:'pre',time:1.45}),{x:30,y:20});
});
test('modeled contact arrests ball on the pass line',()=>{
 const pass={pass_start:{x:30,y:20},pass_end:{x:60,y:40},flight_time_s:2,contact_time_s:1.1,contact_fraction:.3};
 const opts={phase:'post',time:2.5,launch:.45,passer:{x:30,y:20},pass};
 assert.deepEqual(ballPosition(opts),{x:39,y:26});
});
test('pitch coordinates map consistently to world X-Z',()=>{
 assert.deepEqual(toWorld({x:52.5,y:34},1.76),{x:0,y:1.76,z:0});
 assert.deepEqual(toWorld({x:105,y:0}),{x:52.5,y:0,z:34});
});

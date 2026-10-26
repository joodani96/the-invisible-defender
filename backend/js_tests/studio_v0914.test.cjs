const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const C=require('../app/static/studio_core.js');
const R=require('../app/static/defender3d_math.js');
const root=path.join(__dirname,'../app/static');

test('shared studio time is derived from one API summary, not from 2D UI clock',()=>{
 const observed={action:'observed',score:.43,observed_pass:{flight_time_s:1.9}};
 const after={observed_option:observed,options:[{action:'forward',score:.4,observed_pass:{flight_time_s:2.4}}]};
 const data={assumptions:{pass_launch_delay_s:.45},pre_pass:after,post_pass:after};
 assert.equal(C.endTime(data,'pre','observed'),.45);
 assert.equal(C.endTime(data,'post','observed'),.45+1.9);
 assert.equal(C.endTime(data,'post','forward'),.45+2.4);
 assert.equal(C.option(data,'post','forward').score,.4);
 assert.equal(C.delta(.5,.3),.2);
});
test('2D position and 3D position share interpolation and ball launch timing',()=>{
 const path=[{t:0,x:50,y:20},{t:.5,x:52,y:22},{t:1,x:54,y:24}];
 const p={id:'d4',x:50,y:20};
 const data={scene:{defender_id:'d4',ball_holder_id:'a8',players:[p,{id:'a8',x:35,y:29}]},
   assumptions:{pass_launch_delay_s:.45}};
 const opt={trajectory:path,player_trajectories:{a8:[{t:0,x:35,y:29},{t:1,x:36,y:30}]},
   observed_pass:{flight_time_s:1.8,pass_start:{x:36,y:30},pass_end:{x:70,y:35},contact_time_s:null,contact_fraction:null}};
 assert.deepEqual(C.positionFor(p,data,opt,.25,R),R.sample(path,.25));
 assert.deepEqual(C.ballFor(data,opt,'pre',.7,R),C.positionFor(data.scene.players[1],data,opt,.7,R));
 const after=C.ballFor(data,opt,'post',.6,R);
 assert.ok(after.x>36 && after.x<70);
});
test('studio app uses one synced clock and only the four camera buttons',()=>{
 const js=fs.readFileSync(path.join(root,'studio.js'),'utf8');
 const html=fs.readFileSync(path.join(root,'studio.html'),'utf8');
 assert.match(js,/tell\('time',state\.time\)/);
 assert.match(js,/requestAnimationFrame\(animate\)/);
 assert.match(html,/id="viewer"/);
 assert.match(html,/id="pitch"/);
 assert.equal((html.match(/data-camera=/g)||[]).length,4);
 assert.doesNotMatch(html,/id="evidence-buttons"/);
});

test('the synchronized replay stops on first geometric touch, before defenders run away',()=>{
 const make = (contactTime,contactDefender) => ({flight_time_s:2.02,contact_time_s:contactTime,contact_fraction:contactTime==null?null:(contactTime-.45)/2.02,contact_defender_id:contactDefender,
 pass_start:{x:54,y:35},pass_end:{x:83,y:29}});
 const right={action:'down',score:.132,observed_pass:make(1.31399,'d4')};
 const diagonal={action:'forward-down',score:.212,observed_pass:make(null,null)};
 const hold={action:'hold',score:.536,observed_pass:make(null,null)};
 const data={assumptions:{pass_launch_delay_s:.45},pre_pass:{options:[right,diagonal,hold],observed_option:hold},post_pass:{options:[right,diagonal,hold],observed_option:hold}};
 assert.equal(C.replayEvent(data,'post','down').defenderId,'d4');
 assert.equal(C.replayEvent(data,'post','down').type,'contact');
 assert.equal(C.endTime(data,'post','down'),1.31399);
 assert.equal(C.endTime(data,'post','forward-down'),2.47);
 assert.equal(C.replayEvent(data,'post','hold').type,'arrival');
 assert.equal(C.endTime(data,'post','hold'),2.47);
 const atEvent=R.ballPosition({phase:'post',time:C.endTime(data,'post','down'),launch:.45,pass:right.observed_pass,passer:{x:54,y:35}});
 assert.ok(atEvent.x>54 && atEvent.x<83);
 assert.equal(C.endTime(data,'pre','down'),.45);
});

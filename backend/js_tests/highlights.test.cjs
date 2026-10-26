const test = require('node:test');
const assert = require('node:assert/strict');
const {mapEvidence,planEvidence,leadLane,movementComparison,bestOption} = require('../app/static/defender3d_highlights.js');
const {sample}=require('../app/static/defender3d_math.js');
const lane={target_id:'a9',target_name:'Striker',pass_start:{x:42,y:34},pass_end:{x:85,y:20}};
const other={target_id:'a11',target_name:'Winger'};
const option={passes:[lane,other]};
test('only grounded evidence may point to a specific lane',()=>{
  assert.equal(mapEvidence({id:'E4',label:'Pass toward Striker'},option,'pre').targetId,'a9');
  assert.equal(mapEvidence({id:'E5',label:'Marking responsibility'},option,'pre').type,'context');
  assert.equal(mapEvidence({id:'E4',label:'Pass toward Invented Player'},option,'pre').type,'context');
  assert.equal(mapEvidence({id:'E99',label:'Pass toward Striker'},option,'pre'),null);
});
test('offside and time highlights are phase-aware',()=>{
  const packet={evidence:[{id:'E8',label:'Offside unchanged'},{id:'E9',label:'Decision window'},{id:'E3',label:'Decision quality'}]};
  assert.deepEqual(planEvidence(packet,option,'pre').map(p=>p.type),['offside','timing','movements']);
  assert.equal(mapEvidence({id:'E9',label:'Ball contact'},option,'post').type,'contact');
});
test('largest significant pass component uses exact target id, not substring parsing',()=>{
  const ex={components:[{kind:'role',key:'role',reduction_vs_hold:.7},{kind:'pass',key:'pass:a9',reduction_vs_hold:.23}]};
  assert.equal(leadLane(ex,option),'a9');
  assert.equal(leadLane({components:[{kind:'pass',key:'pass:a9',reduction_vs_hold:.0001}]},option),null);
});
test('actual and best comparisons use same timestamp',()=>{
  const actual={trajectory:[{t:0,x:1,y:2},{t:1,x:3,y:2}]};
  const best={trajectory:[{t:0,x:1,y:2},{t:1,x:1,y:4}]};
  const summary={observed_option:actual,options:[{...best,action:'up'}],optimal_action:'up'};
  const paths=movementComparison(summary,.5,sample);
  assert.deepEqual(paths.actualEnd,{x:2,y:2});assert.deepEqual(paths.bestEnd,{x:1,y:3});
  assert.equal(paths.samePath,false);
  summary.optimal_action='observed';
  assert.equal(bestOption(summary),actual);
  assert.equal(movementComparison(summary,.5,sample).samePath,true);
});

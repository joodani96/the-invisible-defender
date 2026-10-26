(() => {
'use strict';
const $ = id => document.getElementById(id);
const Core=window.TIDStudioCore, Replay=window.TIDReplayMath, Decisions=window.TIDDecisions, Orientation=window.TIDOrientation;
const state={scenarios:[],scenario:'central-through-ball',defender:'d4',phase:'pre',action:'observed',camera:'follow',time:0,
  max:1,playing:false,childReady:false,data:null,requestId:0,lastTick:0,aiRequest:0};
const movements=Decisions.grid().flat();
const arrows=movements.map(x=>Decisions.arrowFor(x));
const names={'forward-up':'Forward-left','forward':'Forward','forward-down':'Forward-right','up':'Left','hold':'Hold position','down':'Right',
  'backward-up':'Back-left','backward':'Back','backward-down':'Back-right'};
const fmt=x=>Number.isFinite(x)?x.toFixed(3):'—';
const safe=s=>String(s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const current=()=>state.data && Core.option(state.data,state.phase,state.action);
const summary=()=>state.data&&Core.summary(state.data,state.phase);
function tell(type,value){if(state.childReady)$('viewer').contentWindow?.postMessage({source:'tid-studio',type,value},location.origin);}
function pause(){state.playing=false;$('play').textContent='▶ Play both views';$('play').setAttribute('aria-pressed','false');}
function setTime(t){state.time=Math.max(0,Math.min(Number(t)||0,state.max));$('timeline').value=String(state.time);
  $('clock').innerHTML=`${state.time.toFixed(2)} <small>s</small>`;drawPitch();tell('time',state.time);}
function renderCamera(){document.querySelectorAll('[data-camera]').forEach(b=>b.classList.toggle('selected',b.dataset.camera===state.camera));}
function phaseChanged(phase){if(phase!=='pre'&&phase!=='post')return;pause();state.phase=phase;state.action='observed';
  for(const p of ['pre','post']){$(p).classList.toggle('active',p===phase);$(p).setAttribute('aria-pressed',String(p===phase));}
  refresh();tell('context',{scenario:state.scenario,defender:state.defender,phase:state.phase,action:state.action});}
function selectAction(action){if(!state.data)return;const acts=new Set(summary().options.map(o=>o.action));
  if(action!=='observed'&&!acts.has(action))return;pause();state.action=action;refresh();tell('action',action);}
function chooseDefender(id){if(!state.scenarios.find(s=>s.id===state.scenario)?.selectable_defenders.some(d=>d.id===id))return;
  if(id===state.defender)return;state.defender=id;$('defender').value=id;fetchData();}
function fillDefenders(){const scenario=state.scenarios.find(x=>x.id===state.scenario);$('defender').replaceChildren();
  scenario.selectable_defenders.forEach(d=>{const opt=document.createElement('option');opt.value=d.id;opt.textContent=`#${d.number} · ${d.name}`;$('defender').append(opt);});
  if(!scenario.selectable_defenders.some(d=>d.id===state.defender))state.defender=scenario.default_defender_id;
  $('defender').value=state.defender;}
async function fetchData(){const token=++state.requestId;pause();state.time=0;state.action='observed';state.data=null;clearAi();
  $('connection').textContent='';$('connection').hidden=true;
  try{const r=await fetch(`/api/player-analysis/${encodeURIComponent(state.scenario)}/${encodeURIComponent(state.defender)}`);
    if(!r.ok)throw new Error(`Analysis HTTP ${r.status}`);
    const result=await r.json();if(token!==state.requestId)return;state.data=result;
    $('frame-minute').textContent=`MATCH MOMENT ${result.scene.minute}`;refresh();tell('context',{scenario:state.scenario,defender:state.defender,phase:state.phase,action:state.action});
    $('connection').textContent='';$('connection').hidden=true;
  }catch(e){if(token!==state.requestId)return;$('connection').textContent=`Error: ${e.message}`;$('connection').className='connection bad';$('connection').hidden=false;$('pitch').replaceChildren();}
}
function clearAi(){state.aiRequest++;$('commentary').textContent='Choose a defender and a movement, then generate the tactical explanation.';
 $('sources').replaceChildren();$('provider').textContent='The commentary will describe the selected movement.';}
function refresh(){if(!state.data)return;const s=summary(),o=current();pause();state.max=Core.endTime(state.data,state.phase,state.action);
  const event=Core.replayEvent(state.data,state.phase,state.action);
  const player=state.data.scene.players.find(p=>p.id===event.defenderId);
  const name=event.defenderId===state.data.scene.defender_id ? 'Focus defender' : `Defender #${player?.number ?? event.defenderId}`;
  $('replay-event').textContent=event.type==='contact'
    ? `MODELED FIRST CONTACT · ${name} · ${event.time.toFixed(2)} s · proximity threshold ${state.data.assumptions.contact_radius_m.toFixed(2)} m (not proven possession)`
    : event.type==='arrival'
      ? `NO MODELED DEFENDER CONTACT · ball reaches the receiver at ${event.time.toFixed(2)} s`
      : `BEFORE PASS · first kick at ${event.time.toFixed(2)} s; this phase does not simulate a completed interception`;
  $('replay-event').dataset.kind=event.type;
  $('timeline').max=String(state.max);$('kick-label').textContent=`KICK ${state.data.assumptions.pass_launch_delay_s.toFixed(2)}s`;$('end-label').textContent=`${event.type==='contact'?'CONTACT':event.type==='arrival'?'ARRIVAL':'KICK'} ${state.max.toFixed(2)}s`;
  renderMoves(s,o);renderCoverage(o);renderSummary(s,o);clearAi();setTime(0);}
function renderSummary(s,o){const hold=s.options.find(x=>x.action==='hold');const reduction=hold.score-o.score;
 $('hold-index').textContent=fmt(hold.score);$('chosen-index').textContent=fmt(o.score);$('reduction').textContent=`${reduction>=0?'+':''}${fmt(reduction)}`;
 $('reduction').classList.toggle('bad',reduction<0);$('authored').classList.toggle('active',state.action==='observed');
 const best=s.options.find(x=>x.action===s.best_tested_action)||s.options.reduce((a,b)=>a.score<b.score?a:b);
 const explanation=s.explanations?.[state.action];
 const contact=o.observed_pass.contact_time_s;
 const gap=o.observed_pass.tracked_min_gap_m;
 const geometry=contact==null?'No modeled contact on this pass.':`Contact at ${contact.toFixed(2)} s (${o.observed_pass.contact_defender_id===state.data.scene.defender_id?'focus defender':'teammate'}).`;
 $('reason').textContent=`${o.label}: ${fmt(o.score)} attacking threat index versus ${fmt(hold.score)} when holding. ${reduction>=0?'Lower threat for the attack.':'Higher threat for the attack.'} ${state.phase==='post'?geometry+' ':''}The score also considers coverage and distance (focus defender minimum gap ${gap.toFixed(2)} m); a contact is not proven possession. Best tested: ${best.label} (${fmt(best.score)}). Not xG.`;
}
function renderMoves(s,o){const best=s.best_tested_action;
 const box=$('moves');box.replaceChildren(); movements.forEach((action,i)=>{
   const option=s.options.find(x=>x.action===action);if(!option)return;
   const button=document.createElement('button');button.type='button';button.className='move'+(state.action===action?' chosen':'')+(best===action?' best':'');
   button.setAttribute('aria-pressed',String(state.action===action));button.setAttribute('aria-label',`${names[action]}, threat index ${fmt(option.score)}`);
   const arrow=document.createElement('span');arrow.className='arrow';arrow.textContent=arrows[i];
   const details=document.createElement('span');details.className='details';
   const label=document.createElement('span');label.textContent=names[action];const val=document.createElement('b');val.textContent=fmt(option.score);details.append(label,val);button.append(arrow,details);
   if(action===best){const flag=document.createElement('small');flag.textContent='LOWEST';button.append(flag);}
   button.addEventListener('click',()=>selectAction(action));box.append(button);
 });}
function renderCoverage(o){const box=$('coverage');box.replaceChildren();
 const lanes=state.phase==='post'?o.passes.filter(p=>p.target_id===state.data.scene.observed_pass_target_id):o.passes;
 lanes.forEach(l=>{const card=document.createElement('div');card.className='coverage-lane';
   const head=document.createElement('div');head.className='lane-top';const t=document.createElement('b');t.textContent=`Pass to ${l.target_name}`;
   const status=document.createElement('small');status.textContent=l.offside_position?'OFFSIDE POSITION':'ONSIDE';head.append(t,status);card.append(head);
   const stats=document.createElement('div');stats.className='lane-stats';
   [['Teammates already cover',l.other_defenders_coverage_index],['Focus defender adds',l.marginal_coverage_index],['Team coverage index',l.team_coverage_index]].forEach(([name,num])=>{
      const cell=document.createElement('div');const label=document.createElement('span');label.textContent=name;const value=document.createElement('b');value.textContent=fmt(num);cell.append(label,value);stats.append(cell);
   });card.append(stats);box.append(card);
 });if(!lanes.length)box.textContent='No pass targets in this phase.';}
function drawPitch(){if(!state.data)return;const d=state.data,o=current(),scene=d.scene,t=state.time,defender=scene.defender_id;
 const launch=d.assumptions.pass_launch_delay_s;
 const positions=new Map(scene.players.map(p=>[p.id,Core.positionFor(p,d,o,t,Replay)]));
 const ball=Core.ballFor(d,o,state.phase,t,Replay);
 const offside=o.offside.offside_line_x;
 const pitch=`<defs><pattern id="turf" width="17.5" height="68" patternUnits="userSpaceOnUse"><rect width="17.5" height="68" fill="#397e51"/><rect width="8.75" height="68" fill="#45885b"/></pattern></defs>
 <rect x="0" y="0" width="105" height="68" fill="url(#turf)"/>
 <g stroke="#f1f8ef" stroke-width=".32" opacity=".8" fill="none"><rect x=".7" y=".7" width="103.6" height="66.6"/><path d="M52.5 .7 V67.3"/><circle cx="52.5" cy="34" r="9.15"/><path d="M .7 13.84 H16.9 V54.16 H.7 M104.3 13.84 H88.1 V54.16 H104.3 M.7 24.84 H5.9 V43.16 H.7 M104.3 24.84 H99.1 V43.16 H104.3"/></g>
 <line x1="${offside}" y1=".7" x2="${offside}" y2="67.3" stroke="#f9a4de" stroke-width=".48" stroke-dasharray="1.3 1"/>
 <text x="${Math.max(3,Math.min(95,offside))}" y="5" fill="#fde2f7" text-anchor="middle" font-size="1.7" font-weight="bold">OFFSIDE</text>`;
 let paths='';for(const pass of o.passes){if(state.phase==='post'&&pass.target_id!==scene.observed_pass_target_id)continue;
 paths+=`<line x1="${pass.pass_start.x}" y1="${pass.pass_start.y}" x2="${pass.pass_end.x}" y2="${pass.pass_end.y}" stroke="${pass.offside_position?'#ff9be3':'#e9cc76'}" stroke-width=".5" stroke-dasharray="1.1 1.2" opacity=".9"/>`;
 }
 let players='';for(const p of scene.players){const pos=positions.get(p.id),isFocus=p.id===defender,def=p.team==='defense';
 const trajectory=isFocus?o.trajectory:o.player_trajectories[p.id];
 const facing=Orientation.playerPose(p,trajectory,t).bodyFacingDeg;
 const r=facing*Math.PI/180;
 const tipx=pos.x+Math.cos(r)*(isFocus?3.4:2.8),tipy=pos.y+Math.sin(r)*(isFocus?3.4:2.8);
 const clickable=def&&!p.is_goalkeeper;
 players+=`<g ${clickable?`data-defender="${safe(p.id)}" style="cursor:pointer"`:''}><circle cx="${pos.x}" cy="${pos.y}" r="${isFocus?3.0:2.1}" fill="${isFocus?'#dfffc8':def?'#ff967d':'#75cbfa'}" stroke="${isFocus?'#bdff45':'white'}" stroke-width="${isFocus?'.7':'.3'}"/><text x="${pos.x}" y="${pos.y+.7}" fill="#210b2c" font-size="2.1" text-anchor="middle" font-weight="bold">${Number(p.number)}</text><line x1="${pos.x}" y1="${pos.y}" x2="${tipx}" y2="${tipy}" stroke="${isFocus?'#c8ff4d':'#e9f3ee'}" stroke-linecap="round" stroke-width="${isFocus?.95:.55}"/></g>`;
 }
 const graphics=`<circle cx="${ball.x}" cy="${ball.y}" r="1.13" fill="white" stroke="#240029" stroke-width=".35"/>`;
 $('pitch').innerHTML=pitch+paths+players+graphics;
 $('pitch').querySelectorAll('[data-defender]').forEach(el=>el.addEventListener('click',()=>chooseDefender(el.dataset.defender)));
}
async function generate(){if(!state.data)return;const context=[state.scenario,state.defender,state.phase,state.action].join('|');const token=++state.aiRequest;
 $('generate').disabled=true;$('commentary').textContent='Generating evidence-grounded tactical commentary…';$('sources').replaceChildren();
 try{const r=await fetch(`/api/commentary/${encodeURIComponent(state.scenario)}/${encodeURIComponent(state.defender)}`,
  {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phase:state.phase,action:state.action,audience:'fan'})});
  if(!r.ok)throw Error(`HTTP ${r.status}`);const answer=await r.json();if(token!==state.aiRequest||context!==[state.scenario,state.defender,state.phase,state.action].join('|'))return;
  $('commentary').textContent=answer.commentary;
  $('provider').textContent=answer.generated_by_ai?'● Microsoft Foundry agents · evidence-grounded':`● Deterministic fallback · ${answer.warning||'AI unavailable'}`;
  const sources=$('sources');for(const item of answer.evidence||[]){const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent=`${item.id} · ${item.label}`;
   const p=document.createElement('p');p.textContent=item.fact;detail.append(summary,p);sources.append(detail);}
 }catch(e){if(token===state.aiRequest){$('commentary').textContent=`Could not generate commentary: ${e.message}`;$('provider').textContent='Commentary endpoint unavailable';}}
 finally{if(token===state.aiRequest)$('generate').disabled=false;}}
function onMsg(e){if(e.origin!==location.origin ||e.source!==$('viewer').contentWindow||e.data?.source!=='tid3d')return;
 const {type,value}=e.data;
 if(type==='error'){state.childReady=false;$('three-status').textContent='3D viewer unavailable: '+String(value);$('three-status').classList.remove('hidden');return;}
 if(type==='ready'){state.childReady=true;$('three-status').classList.add('hidden');
    tell('context',{scenario:state.scenario,defender:state.defender,phase:state.phase,action:state.action});tell('camera',state.camera);tell('time',state.time);}
 if(type==='loaded'){if(value?.scenario===state.scenario&&value?.defender===state.defender){tell('camera',state.camera);tell('phase',state.phase);tell('action',state.action);tell('time',state.time);}}
 if(type==='action'&&typeof value==='string'&&state.data)selectAction(value);
 if(type==='defender'&&typeof value==='string')chooseDefender(value);
}
function animate(now){if(!state.lastTick)state.lastTick=now;const dt=Math.min(.08,Math.max(0,(now-state.lastTick)/1000));state.lastTick=now;
 if(state.playing&&state.data){setTime(state.time+dt);if(state.time>=state.max)pause();}
 requestAnimationFrame(animate);}
async function init(){window.addEventListener('message',onMsg);
 for(const p of ['pre','post'])$(p).addEventListener('click',()=>phaseChanged(p));
 $('scenario').addEventListener('change',()=>{state.scenario=$('scenario').value;state.defender=state.scenarios.find(s=>s.id===state.scenario).default_defender_id;fillDefenders();fetchData();});
 $('defender').addEventListener('change',()=>chooseDefender($('defender').value));
 document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>{state.camera=b.dataset.camera;renderCamera();tell('camera',state.camera);}));
 $('authored').addEventListener('click',()=>selectAction('observed'));
 $('timeline').addEventListener('input',()=>{pause();setTime($('timeline').value);});
 $('play').addEventListener('click',()=>{if(!state.data)return;if(state.time>=state.max)setTime(0);state.playing=!state.playing;
  $('play').textContent=state.playing?'❚❚ Pause both views':'▶ Play both views';$('play').setAttribute('aria-pressed',String(state.playing));});
 $('reset').addEventListener('click',()=>{pause();setTime(0);});
 $('freeze').addEventListener('click',()=>{if(!state.data)return;pause();setTime(state.data.assumptions.pass_launch_delay_s);});
 $('generate').addEventListener('click',generate);
 requestAnimationFrame(animate);
 try{const res=await fetch('/api/scenarios');if(!res.ok)throw Error(`HTTP ${res.status}`);
  state.scenarios=await res.json();if(!state.scenarios.length)throw Error('No scenarios configured');
  state.scenario=state.scenarios[0].id;state.defender=state.scenarios[0].default_defender_id;
  fetch('/api/ai/status').then(r=>r.ok?r.json():null).then(provider=>{
    if(provider && ['Checking AI provider…','The commentary will describe the selected movement.'].includes($('provider').textContent)) $('provider').textContent=provider.mode==='foundry'?'● Microsoft Foundry configured · generate on demand':'● Offline deterministic commentary available';
  }).catch(()=>{});
  for(const s of state.scenarios){const o=document.createElement('option');o.value=s.id;o.textContent=`${s.minute} · ${s.title}`;$('scenario').append(o);}
  $('scenario').value=state.scenario;fillDefenders();await fetchData();
 }catch(e){$('connection').textContent=e.message;$('connection').className='connection bad';$('connection').hidden=false;}}
init();
})();

/* The Invisible Defender v0.9.13 — Babylon.js viewer.
   Geometry and view direction are illustrative. Positions, timestamps, pass and
   threat scores always come from /api/player-analysis, never recomputed here. */
(() => {
  'use strict';
  const el = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const embedded = params.get('embedded') === '1';
  const studioEmbed = embedded && params.get('studio') === '1';
  if (embedded) document.body.classList.add('embedded');
  if (studioEmbed) document.body.classList.add('studio-embed');
  const state = {
    scenarioId: params.get('scenario') || 'central-through-ball',
    defenderId: params.get('defender') || 'd4',
    phase: params.get('phase') === 'post' ? 'post' : 'pre',
    action: params.get('action') || 'observed',
    time: 0, playing: false, maxTime: 1, cameraMode: 'follow', uiMode: 'broadcast',
    data: null, scenarios: [], serial: 0, engine: null, scene: null,
    cameras: {}, meshes: new Map(), lines: [], pitchBuilt: false,
    ball: null, offsideLine: null, lastFrame: 0,
    highlightsEnabled: !studioEmbed, followCommentary: false, comparison: 'both', showNinePaths: false, decisionMarkers: [],
    highlightMeshes: [], activeEvidence: null, evidenceItems: [],
    commentaryToken: 0, evidenceCycle: null,
    materials: {}, shadow: null,

  };
  const color = (name) => BABYLON.Color3.FromHexString(name);
  const coords = (p, height=0) => new BABYLON.Vector3(p.x - 52.5, height, 34 - p.y);
  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const chosen = () => {
    const summary = state.data && state.data[state.phase === 'pre' ? 'pre_pass' : 'post_pass'];
    if (!summary) return null;
    return state.action === 'observed' ? summary.observed_option :
      (summary.options.find(o => o.action === state.action) || summary.observed_option);
  };
  const sample = window.TIDReplayMath.sample;
  const Orientation = window.TIDOrientation;
  const D = window.TIDDecisions;
  const H = window.TIDHighlights;
  const playerPos = (id, option, time) => {
    const path = id === state.data.scene.defender_id ? option.trajectory : option.player_trajectories[id];
    return sample(path, time) || state.data.scene.players.find(p=>p.id===id);
  };
  const notifyParent = (type, value) => {
    if (embedded && window.parent !== window) window.parent.postMessage({source:'tid3d', type, value}, location.origin);
  };
  function setError(message) {
    const r = el('render-status'); r.textContent = message; r.classList.remove('hidden');
    if(studioEmbed) notifyParent('error',message);
    el('connection').textContent = '3D renderer unavailable'; el('connection').className = 'connection bad';
  }
  function makeMat(name, hex, emissive=false) {
    const mat = new BABYLON.StandardMaterial(name, state.scene);
    mat.diffuseColor = color(hex);
    mat.specularColor = color('#18312f');
    if (emissive) mat.emissiveColor = color(hex).scale(.4);
    return mat;
  }
  function segment(name, a, b, col, width=1) {
    const line = BABYLON.MeshBuilder.CreateLines(name, {points:[a,b]}, state.scene);
    line.color = color(col); line.isPickable = false; return line;
  }
  function tube(name, a, b, hex, radius=.13) {
    const mesh=BABYLON.MeshBuilder.CreateTube(name,{path:[a,b],radius,tessellation:8,cap:BABYLON.Mesh.CAP_ALL},state.scene);
    const mat=makeMat(`${name}-mat`,hex,true); mat.emissiveColor=color(hex).scale(.7);
    mesh.material=mat;mesh.isPickable=false;return mesh;
  }
  function arrow(name, a, b, hex) {
    const v=b.subtract(a),len=v.length();if(len<.07)return [];
    const tip=len>.55?.42:len*.4;
    const shaft=tube(name,a,b.subtract(v.normalizeToNew().scale(tip*.55)),hex,.095);
    const head=BABYLON.MeshBuilder.CreateCylinder(name+'-tip',{diameterTop:0,diameterBottom:.42,height:tip,tessellation:16},state.scene);
    head.material=makeMat(name+'-head',hex,true);head.isPickable=false;
    head.position.copyFrom(b.subtract(v.normalizeToNew().scale(tip*.5)));
    const direction=v.normalizeToNew();
    const axis=BABYLON.Vector3.Cross(BABYLON.Axis.Y,direction);
    const dot=Math.min(1,Math.max(-1,BABYLON.Vector3.Dot(BABYLON.Axis.Y,direction)));
    head.rotationQuaternion=axis.lengthSquared()<1e-8
      ? BABYLON.Quaternion.RotationAxis(BABYLON.Axis.X,dot<0?Math.PI:0)
      : BABYLON.Quaternion.RotationAxis(axis.normalize(),Math.acos(dot));
    return [shaft,head];
  }
  function fieldLine(name, xy, hex='#f1ffef') {
    const pts = xy.map(([x,y])=>coords({x,y},.04));
    const l = BABYLON.MeshBuilder.CreateLines(name,{points:pts},state.scene);
    l.color = color(hex); l.isPickable=false; return l;
  }
  function rectPoints(x1,y1,x2,y2) { return [[x1,y1],[x2,y1],[x2,y2],[x1,y2],[x1,y1]]; }
  function buildPitch() {
    const scene = state.scene;
    const bowl = BABYLON.MeshBuilder.CreateGround('stadium bowl',{width:236,height:190},scene);
    bowl.position.y=-.46;
    const bowlMat=makeMat('stadium-bowl','#07181d'); bowlMat.specularColor=color('#051015');
    bowl.material=bowlMat; bowl.isPickable=false;

    const outfield=BABYLON.MeshBuilder.CreateGround('outfield',{width:220,height:176},scene);
    outfield.position.y=-.26;
    const outfieldMat=makeMat('outfield-mat','#11292b'); outfieldMat.specularColor=color('#0d1b1d');
    outfield.material=outfieldMat; outfield.isPickable=false;

    const runoff=BABYLON.MeshBuilder.CreateGround('runoff',{width:118,height:81},scene);
    runoff.position.y=-.018;
    const runoffMat=makeMat('runoff-mat','#153134'); runoffMat.specularColor=color('#0e1f21');
    runoff.material=runoffMat; runoff.isPickable=false;

    const pitchBase=BABYLON.MeshBuilder.CreateBox('pitch-base',{width:106.5,height:.16,depth:69.5},scene);
    pitchBase.position.y=-.08;
    const pitchBaseMat=makeMat('pitch-base-mat','#2d6d41'); pitchBaseMat.specularColor=color('#15261b');
    pitchBase.material=pitchBaseMat; pitchBase.isPickable=false;

    const grassMat = makeMat('grass','#4a8550');
    grassMat.specularColor=color('#1a2c1b');
    grassMat.emissiveColor=color('#020603').scale(.025);
    const grass = BABYLON.MeshBuilder.CreateGround('pitch', {width:105,height:68}, scene);
    grass.material = grassMat; grass.isPickable=false;

    const stripColors=['#528b58','#467a4c','#5a955f','#4b8151','#629a65','#4a7c50'];
    for (let i=0; i<12; i++) {
      const s=BABYLON.MeshBuilder.CreateGround(`grass-stripe-${i}`,{width:8.75,height:68},scene);
      s.position.set(-52.5+i*8.75+4.375,.0035,0);
      const mat=makeMat(`grass-stripe-mat-${i}`,stripColors[i%stripColors.length]);
      mat.specularColor=color('#203624'); mat.alpha=.46;
      s.material=mat; s.isPickable=false;
    }
    for(let i=0;i<24;i++){
      const band=BABYLON.MeshBuilder.CreateGround(`fine-mow-${i}`,{width:1.25,height:67.8},scene);
      band.position.set(-52+i*4.55,.006,0);
      const mat=makeMat(`fine-mow-mat-${i}`,i%2===0?'#c7f7cc':'#000000');
      mat.alpha=i%2===0?0.018:0.0;
      band.material=mat; band.isPickable=false;
    }
    for(let i=0;i<15;i++){
      const wash=BABYLON.MeshBuilder.CreateGround(`grass-wash-${i}`,{width:105,height:4.2},scene);
      wash.position.set(0,.004,-31.5+i*4.5);
      const mat=makeMat(`grass-wash-mat-${i}`,i%2===0?'#99d49d':'#3b6c42');
      mat.alpha=i%2===0?0.012:0.01;
      wash.material=mat; wash.isPickable=false;
    }

    fieldLine('boundary',rectPoints(.4,.4,104.6,67.6));
    fieldLine('centre',[[52.5,.4],[52.5,67.6]]);
    const circle=[];
    for(let i=0;i<=64;i++){const th=i*Math.PI*2/64;circle.push([52.5+9.15*Math.cos(th),34+9.15*Math.sin(th)]);} fieldLine('centre circle',circle);
    fieldLine('left penalty',rectPoints(.4,13.84,16.9,54.16));
    fieldLine('right penalty',rectPoints(88.1,13.84,104.6,54.16));
    fieldLine('left six-yard',rectPoints(.4,24.84,5.9,43.16));
    fieldLine('right six-yard',rectPoints(99.1,24.84,104.6,43.16));
    for(const x of [11,94]){
      const dot=BABYLON.MeshBuilder.CreateDisc(`penalty-spot-${x}`,{radius:.13,tessellation:20},scene);
      dot.rotation.x=-Math.PI/2; dot.position.copyFrom(coords({x,y:34},.06));
      dot.material=makeMat(`white-spot-${x}`,'#edf4e9',true); dot.isPickable=false;
    }
    for(const [x,flip] of [[11,1],[94,-1]]){
      const arc=[]; for(let i=0;i<=28;i++){
        const th=-.93+1.86*i/28;
        const px=x+flip*9.15*Math.cos(th),py=34+9.15*Math.sin(th);
        if(px>16.9 && px<88.1) arc.push([px,py]);
      }
      if(arc.length>1) fieldLine(`penalty-arc-${x}`,arc);
    }
    for (const cx of [0,105]) for(const cy of [0,68]){
      const corner=[]; for(let i=0;i<=12;i++){
        const th=i*Math.PI/2/12;
        const dx=(cx===0?1:-1)*Math.cos(th),dy=(cy===0?1:-1)*Math.sin(th);
        corner.push([cx+dx,cy+dy]);
      } fieldLine(`corner-${cx}-${cy}`,corner);
    }

    const goalMat=makeMat('goal white','#f7fbfb',true); goalMat.emissiveColor=color('#edf7f6').scale(.12);
    const netMatColor='#b9c8c8';
    for (const x of [-.55,105.55]) {
      const backX=x<0?x-2.25:x+2.25;
      for (const yy of [30.34,37.66]) {
        const post=BABYLON.MeshBuilder.CreateCylinder(`goal-post-${x}-${yy}`,{diameter:.12,height:2.44,tessellation:18},scene);
        post.position=coords({x,y:yy},1.22); post.material=goalMat; post.isPickable=false;
        const backPost=BABYLON.MeshBuilder.CreateCylinder(`goal-backpost-${x}-${yy}`,{diameter:.1,height:2.02,tessellation:14},scene);
        backPost.position=coords({x:backX,y:yy},1.01); backPost.material=goalMat; backPost.isPickable=false;
        segment(`goal-sidebar-top-${x}-${yy}`,coords({x,y:yy},2.42),coords({x:backX,y:yy},1.98),'#f8fcfc');
        segment(`goal-sidebar-floor-${x}-${yy}`,coords({x,y:yy},.08),coords({x:backX,y:yy},.08),'#edf3f3');
      }
      segment(`goal-bar-${x}`,coords({x,y:30.34},2.42),coords({x,y:37.66},2.42),'#f8fcfc');
      segment(`goal-backbar-${x}`,coords({x:backX,y:30.34},1.98),coords({x:backX,y:37.66},1.98),'#edf7f7');
      for(let ny=0;ny<=10;ny++){
        const yy=30.34+ny*(7.32/10);
        segment(`goal-net-top-${x}-${ny}`,coords({x,y:yy},2.34),coords({x:backX,y:yy},1.96),netMatColor);
        segment(`goal-net-floor-${x}-${ny}`,coords({x,y:yy},.08),coords({x:backX,y:yy},.08),netMatColor);
      }
      for(let nz=0;nz<=5;nz++){
        const xx=x+(backX-x)*nz/5;
        segment(`goal-net-vert-top-${x}-${nz}`,coords({x:xx,y:30.34},2.34-(nz*.075)),coords({x:xx,y:37.66},2.34-(nz*.075)),netMatColor);
        segment(`goal-net-vert-low-${x}-${nz}`,coords({x:xx,y:30.34},.08),coords({x:xx,y:37.66},.08),netMatColor);
      }
    }

    const h = new BABYLON.HemisphericLight('fill',new BABYLON.Vector3(0,1,0),scene);
    h.intensity=.68; h.groundColor=color('#15292a');
    const key = new BABYLON.DirectionalLight('key',new BABYLON.Vector3(-.34,-1,-.22),scene);
    key.intensity=.72;
    const rim = new BABYLON.DirectionalLight('rim',new BABYLON.Vector3(.28,-.82,.42),scene);
    rim.intensity=.18;
    scene.clearColor = new BABYLON.Color4(.012,.043,.05,1);

    // v0.9.13 – redesigned architectural bowl: curved terraces, inset stair aisles,
    // upper concourse, glazed enclosure, cantilever roof and a small scoreboard.
    // Field surface and lighting remain exactly as in v0.9.12.
    window.TIDStadium.build({BABYLON,scene,makeMat,color});

    const ribbonMat=makeMat('pitch side LED','#184f4c',true); ribbonMat.emissiveColor=color('#2d7772').scale(.2);
    const ribbonBack=makeMat('board frames','#0a1b1e');
    const ribbons=[{x:0,z:36.45,width:111,depth:.22},{x:0,z:-36.45,width:111,depth:.22},{x:55,z:0,width:.22,depth:74},{x:-55,z:0,width:.22,depth:74}];
    for(const [i,r] of ribbons.entries()){
      const back=BABYLON.MeshBuilder.CreateBox(`LED frame ${i}`,{width:r.width,height:1.0,depth:r.depth+.22},scene);
      back.position.set(r.x,.5,r.z); back.material=ribbonBack; back.isPickable=false;
      const glow=BABYLON.MeshBuilder.CreateBox(`LED band ${i}`,{width:r.width-.03,height:.16,depth:r.depth+.25},scene);
      glow.position.set(r.x,.75,r.z); glow.material=ribbonMat; glow.isPickable=false;
    }

    const railMat=makeMat('stand rail','#577379');
    for(const sign of [-1,1]){
      for(const level of [0,1]){
        const rail=BABYLON.MeshBuilder.CreateBox(`terrace rail ${sign} ${level}`,{width:133,height:.12,depth:.12},scene);
        rail.position.set(0,1.3+level*2.05,sign*(40+level*7.9)); rail.material=railMat; rail.isPickable=false;
      }
    }

    // Modern roof-mounted lighting arrays replace the oversized free-standing masts.
    // Preserve the four original point-light positions / values to keep v0.9.12 turf lighting.
    const rackMat=makeMat('roof light rack','#365761');
    const lightMat=makeMat('floodlights','#eff7ee',true);lightMat.emissiveColor=color('#fbfffa').scale(.4);
    for(const x of [-67,67]) for(const z of [-50,50]) {
      const rack=BABYLON.MeshBuilder.CreateBox(`roof-floodlight-array-${x}-${z}`,{width:4.6,height:.42,depth:1.1},scene);
      rack.position.set(x,9.20,z);rack.material=rackMat;rack.isPickable=false;
      for(let j=0;j<5;j++){
        const lens=BABYLON.MeshBuilder.CreateBox(`roof-floodlight-lens-${x}-${z}-${j}`,{width:.58,height:.10,depth:.70},scene);
        lens.position.set(x-1.52+j*.76,8.94,z);
        lens.material=lightMat;lens.isPickable=false;
      }
      const practical=new BABYLON.PointLight(`stadium-practical-${x}-${z}`,new BABYLON.Vector3(x,22.9,z),scene);
      practical.diffuse=color('#f3fff3'); practical.intensity=.17; practical.range=122;
    }
    const benchMat=makeMat('bench-shell','#294148');
    const seatMat=makeMat('bench-seat','#87aeb4');
    for(const sign of [-1,1]){
      const shell=BABYLON.MeshBuilder.CreateBox(`dugout-shell-${sign}`,{width:8,height:1.7,depth:2.1},scene);
      shell.position.set(sign*16,0.88,39.8); shell.material=benchMat; shell.isPickable=false; shell.rotation.y=sign===1?Math.PI:0;
      const roof=BABYLON.MeshBuilder.CreateBox(`dugout-roof-${sign}`,{width:8.1,height:.12,depth:2.2},scene);
      roof.position.set(sign*16,1.68,39.8); roof.material=seatMat; roof.isPickable=false; roof.rotation.y=shell.rotation.y;
      for(let i=0;i<5;i++){
        const seat=BABYLON.MeshBuilder.CreateBox(`dugout-seat-${sign}-${i}`,{width:.9,height:.45,depth:.7},scene);
        seat.position.set(sign*(13.2+i*1.1),0.35,39.7); seat.material=seatMat; seat.isPickable=false;
      }
    }

    const boardTopMat=makeMat('board-top','#e9f2ef');
    const flagMat=makeMat('flag-cloth','#ffd15e',true); flagMat.emissiveColor=color('#ffd15e').scale(.14);
    for(const [x,y,dx,dy] of [[0,0,1,1],[0,68,1,-1],[105,0,-1,1],[105,68,-1,-1]]){
      const pole=BABYLON.MeshBuilder.CreateCylinder(`corner-pole-${x}-${y}`,{height:1.55,diameter:.05,tessellation:10},scene);
      pole.position.copyFrom(coords({x,y},0.78)); pole.material=boardTopMat; pole.isPickable=false;
      const flag=BABYLON.MeshBuilder.CreatePlane(`corner-flag-${x}-${y}`,{width:.38,height:.26,sideOrientation:BABYLON.Mesh.DOUBLESIDE},scene);
      flag.position.copyFrom(coords({x:x+dx*.18,y:y+dy*.06},1.38)); flag.rotation.y=Math.atan2(-dy,dx); flag.material=flagMat; flag.isPickable=false;
    }

    const shadow=new BABYLON.ShadowGenerator(1024,key); shadow.useBlurExponentialShadowMap=true; shadow.blurKernel=8;
    grass.receiveShadows=true; state.shadow=shadow;
    scene.fogMode=BABYLON.Scene.FOGMODE_EXP2; scene.fogDensity=.0009; scene.fogColor=color('#071a1f');

    const cameras = state.cameras;
    cameras.tactical = new BABYLON.ArcRotateCamera('Tactical camera',-Math.PI/2,1.04,93,new BABYLON.Vector3(0,0,0),scene);
    cameras.tactical.lowerRadiusLimit=24; cameras.tactical.upperRadiusLimit=180;
    cameras.tactical.wheelPrecision=25; cameras.tactical.panningSensibility=120;
    cameras.pov = new BABYLON.FreeCamera('Defender POV',new BABYLON.Vector3(0,1.76,0),scene); cameras.pov.fov=.96;
    cameras.follow = new BABYLON.FreeCamera('Behind defender',new BABYLON.Vector3(0,5,0),scene); cameras.follow.fov=.85;
    cameras.broadcast = new BABYLON.FreeCamera('Broadcast side',new BABYLON.Vector3(1,24,78),scene); cameras.broadcast.fov=.81;
    switchCamera(state.cameraMode);
    state.pitchBuilt=true;
  }

  function makeBackNumber(p) {
    // Actual shirt print: attached to the torso with NO billboard rotation.
    // Keep it explicit and high-contrast because the hackathon demo relies on quick reading.
    const texture=new BABYLON.DynamicTexture(`shirt-number-${p.id}`,{width:384,height:320},state.scene,false);
    const ctx=texture.getContext();ctx.clearRect(0,0,384,320);
    ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.shadowColor='rgba(4,15,20,.45)';ctx.shadowBlur=6;
    ctx.strokeStyle='#0a2430';ctx.lineWidth=10;
    ctx.font=`900 ${String(p.number).length>1?188:216}px Arial, sans-serif`;
    ctx.strokeText(String(p.number),192,168);
    ctx.fillStyle='#fbfff7';ctx.fillText(String(p.number),192,168);
    ctx.shadowBlur=0;texture.hasAlpha=true;texture.update();
    const mat=new BABYLON.StandardMaterial(`shirt-number-mat-${p.id}`,state.scene);
    mat.diffuseTexture=texture;mat.emissiveTexture=texture;mat.opacityTexture=texture;mat.useAlphaFromDiffuseTexture=true;
    mat.disableLighting=true;mat.backFaceCulling=false;mat.specularColor=BABYLON.Color3.Black();mat.zOffset=-3;
    // Front face is outward (+local Z); only V is flipped in shirtBackQuad.
    // Make the print a little larger and further from the torso to avoid clipping.
    const number=new BABYLON.Mesh(`back-number-${p.id}`,state.scene);
    const quad=D.shirtBackQuad(.68,.56);
    const vertices=new BABYLON.VertexData();
    vertices.positions=quad.positions;vertices.indices=quad.indices;
    vertices.normals=quad.normals;vertices.uvs=quad.uvs;
    vertices.applyToMesh(number);
    number.position.set(0,.06,.41);
    number.renderingGroupId=2;
    number.material=mat;number.isPickable=false;
    number.metadata={printedOn:'back',face:'+localZ'};
    return number;
  }
  function disposeDynamic() {
    for(const root of state.meshes.values())root.dispose(false,true);state.meshes.clear();
    for(const line of state.lines)line.dispose(false,true);state.lines=[];
    if(state.ball){state.ball.dispose(false,true);state.ball=null;}
    if(state.offsideLine){state.offsideLine.dispose(false,true);state.offsideLine=null;}
    clearHighlightMeshes();
    clearDecisionMarkers();
  }
  function createPlayers() {
    disposeDynamic();if(!state.data || !state.scene)return;
    for(const p of state.data.scene.players) {
      const root=new BABYLON.TransformNode(`root-${p.id}`,state.scene);
      const attacker=p.team==='attack', keeper=!!p.is_goalkeeper;
      const shirt=makeMat(`shirt-${p.id}`,keeper?'#e9bd50':attacker?'#3b9ee5':'#df6b56');
      const sleeves=makeMat(`sleeves-${p.id}`,keeper?'#d9a844':attacker?'#2575ad':'#b54a43');
      const shorts=makeMat(`shorts-${p.id}`,keeper?'#222c35':attacker?'#183b70':'#24313d');
      const socks=makeMat(`socks-${p.id}`,keeper?'#e9bd50':attacker?'#2c89cf':'#d75e4c');
      const skin=makeMat(`skin-${p.id}`,'#cfaa8c');
      const boots=makeMat(`boots-${p.id}`,'#101c22');
      const trim=makeMat(`kit-trim-${p.id}`,keeper?'#fbe0a7':attacker?'#d7f0fb':'#ffe0c2');

      const torso=BABYLON.MeshBuilder.CreateCylinder(`torso-${p.id}`,{height:.98,diameterTop:.74,diameterBottom:.54,tessellation:18},state.scene);
      torso.position.y=1.50;torso.parent=root;torso.material=shirt;
      const shoulder=BABYLON.MeshBuilder.CreateSphere(`shoulder-${p.id}`,{diameter:.78,segments:16},state.scene);
      shoulder.position.y=1.84;shoulder.scaling.y=.34;shoulder.parent=root;shoulder.material=shirt;
      const chestBand=BABYLON.MeshBuilder.CreateBox(`chest-band-${p.id}`,{width:.64,height:.08,depth:.43},state.scene);
      chestBand.position.set(0,1.69,.02);chestBand.parent=root;chestBand.material=trim;chestBand.isPickable=false;
      for(const side of [-1,1]){
        const seam=BABYLON.MeshBuilder.CreateBox(`side-seam-${p.id}-${side}`,{width:.055,height:.76,depth:.055},state.scene);
        seam.position.set(side*.302,1.47,-.02);seam.parent=root;seam.material=trim;seam.isPickable=false;
        const shoulderStripe=BABYLON.MeshBuilder.CreateBox(`shoulder-trim-${p.id}-${side}`,{width:.11,height:.035,depth:.44},state.scene);
        shoulderStripe.position.set(side*.30,1.91,-.01);shoulderStripe.parent=root;shoulderStripe.material=trim;shoulderStripe.isPickable=false;
      }
      const collar=BABYLON.MeshBuilder.CreateTorus(`collar-${p.id}`,{diameter:.30,thickness:.055,tessellation:20},state.scene);
      collar.position.y=2.04;collar.parent=root;collar.material=trim;collar.isPickable=false;
      const shortsBody=BABYLON.MeshBuilder.CreateBox(`shorts-${p.id}`,{width:.60,height:.30,depth:.43},state.scene);
      shortsBody.position.y=.92;shortsBody.parent=root;shortsBody.material=shorts;
      const waistBand=BABYLON.MeshBuilder.CreateBox(`waist-band-${p.id}`,{width:.62,height:.05,depth:.44},state.scene);
      waistBand.position.y=1.09;waistBand.parent=root;waistBand.material=trim;waistBand.isPickable=false;
      const neck=BABYLON.MeshBuilder.CreateCylinder(`neck-${p.id}`,{height:.15,diameter:.20,tessellation:16},state.scene);
      neck.position.y=2.04;neck.parent=root;neck.material=skin;
      const head=BABYLON.MeshBuilder.CreateSphere(`head-${p.id}`,{diameter:.46,segments:20},state.scene);
      head.position.y=2.34;head.parent=root;head.material=skin;
      const hair=BABYLON.MeshBuilder.CreateSphere(`hair-${p.id}`,{diameter:.47,segments:16},state.scene);
      hair.position.y=2.51;hair.scaling.y=.38;hair.parent=root;hair.material=makeMat(`hair-mat-${p.id}`,'#273039');
      for(const direction of [-1,1]){
        const arm=BABYLON.MeshBuilder.CreateCylinder(`arm-${p.id}`,{height:.72,diameterTop:.21,diameterBottom:.16,tessellation:14},state.scene);
        arm.position.set(direction*.47,1.45,0);arm.rotation.z=direction*.16;arm.parent=root;arm.material=sleeves;
        const hand=BABYLON.MeshBuilder.CreateSphere(`hand-${p.id}`,{diameter:.18,segments:12},state.scene);
        hand.position.set(direction*.55,1.06,0);hand.parent=root;hand.material=skin;
        const leg=BABYLON.MeshBuilder.CreateCylinder(`leg-${p.id}`,{height:.63,diameterTop:.25,diameterBottom:.18,tessellation:14},state.scene);
        leg.position.set(direction*.17,.60,0);leg.parent=root;leg.material=socks;
        const sockStripe=BABYLON.MeshBuilder.CreateCylinder(`sock-band-${p.id}-${direction}`,{height:.085,diameter:.245,tessellation:16},state.scene);
        sockStripe.position.set(direction*.17,.71,0);sockStripe.parent=root;sockStripe.material=trim;sockStripe.isPickable=false;
        const knee=BABYLON.MeshBuilder.CreateSphere(`knee-${p.id}-${direction}`,{diameter:.16,segments:10},state.scene);
        knee.position.set(direction*.17,.86,.02);knee.parent=root;knee.material=socks;
        const shoe=BABYLON.MeshBuilder.CreateBox(`shoe-${p.id}`,{width:.28,height:.12,depth:.40},state.scene);
        shoe.position.set(direction*.17,.12,-.08);shoe.parent=root;shoe.material=boots;
      }
      const backNumber=makeBackNumber(p);backNumber.parent=torso;
      root.metadata={backNumber,player:p,bodyFacingDeg:p.body_facing_deg};
      if(state.shadow){state.shadow.addShadowCaster(torso);state.shadow.addShadowCaster(head);state.shadow.addShadowCaster(shoulder);}
      if(p.team==='defense' && !p.is_goalkeeper){torso.metadata={defenderId:p.id};head.metadata={defenderId:p.id};}
      state.meshes.set(p.id,root);
    }
    state.ball=BABYLON.MeshBuilder.CreateSphere('ball',{diameter:.44,segments:20},state.scene);
    const ballMat=makeMat('ball-white','#f5f7ef'); ballMat.specularColor=color('#344046');
    state.ball.material=ballMat;state.ball.isPickable=false;
    redrawPassLines();
  }
  function redrawPassLines() {
    for(const line of state.lines)line.dispose(false,true);state.lines=[];
    if(state.offsideLine){state.offsideLine.dispose(false,true);state.offsideLine=null;}
    const opt=chosen();if(!opt)return;
    for(const pass of opt.passes){
      if(state.phase==='post' && pass.target_id!==state.data.scene.observed_pass_target_id)continue;
      const line=fieldLine(`pass-${pass.target_id}`,[[pass.pass_start.x,pass.pass_start.y],[pass.pass_end.x,pass.pass_end.y]],pass.offside_position?'#ee95d9':pass.marginal_coverage_index>.15?'#b9eb8e':'#f7cd83');
      state.lines.push(line);
    }
    const offside=opt.offside.offside_line_x;
    state.offsideLine=fieldLine('offside at kick',[[offside,0],[offside,68]],'#ef99e5');
    el('line-x').textContent=`${offside.toFixed(2)} m`;
  }
  function clearHighlightMeshes(){
    for(const mesh of state.highlightMeshes)mesh.dispose(false,true);
    state.highlightMeshes=[];
  }
  function drawHighlights() {
    clearHighlightMeshes();
    const option=chosen();if(!state.data||!option||!state.scene)return;
    const evidence=state.evidenceItems.find(e=>e.id===state.activeEvidence);
    if(!state.highlightsEnabled){renderHighlightBanner(null);return;}
    if(state.showNinePaths)drawNineDecisionPaths();
    const shouldShow=(kind)=>!evidence || evidence.type===kind || evidence.type==='context';
    const lead = state.data[state.phase==='pre'?'pre_pass':'post_pass'].explanations?.[state.action];
    const targetId=evidence?.type==='lane'?evidence.targetId:H.leadLane(lead,option);
    if(targetId && shouldShow('lane')){
      const pass=option.passes.find(p=>p.target_id===targetId);
      if(pass){
        state.highlightMeshes.push(tube('evidence-selected-lane',coords(pass.pass_start,.14),coords(pass.pass_end,.14),'#ffe184',.16));
        const dest=coords(pass.pass_end,.17);
        const ring=BABYLON.MeshBuilder.CreateTorus('target-player-spot',{diameter:3.5,thickness:.13,tessellation:50},state.scene);
        ring.rotation.x=Math.PI/2;ring.position.copyFrom(dest);ring.material=makeMat('target-spot','#ffe184',true);
        ring.isPickable=false;state.highlightMeshes.push(ring);
      }
    }
    if(shouldShow('offside')){
      const x=option.offside.offside_line_x;
      const band=BABYLON.MeshBuilder.CreateBox('offside-band',{width:.32,height:.025,depth:67},state.scene);
      band.position.copyFrom(coords({x,y:34},.10));
      const mat=makeMat('offside-bright','#f5a8e9',true);mat.alpha=.48;
      band.material=mat;band.isPickable=false;state.highlightMeshes.push(band);
    }
    if(state.comparison!=='none' && shouldShow('movements')){
      const summary=state.data[state.phase==='pre'?'pre_pass':'post_pass'];
      const until=state.phase==='pre'?state.data.assumptions.pass_launch_delay_s:
        Math.min(state.maxTime,state.data.assumptions.pass_launch_delay_s+.85);
      const cmp=H.movementComparison(summary,until,sample);
      if(cmp){
        if(state.comparison==='both'||state.comparison==='actual')
          state.highlightMeshes.push(...arrow('authored-movement',coords(cmp.actualStart,.32),coords(cmp.actualEnd,.32),'#ffaf79'));
        if(!cmp.samePath && (state.comparison==='both'||state.comparison==='best'))
          state.highlightMeshes.push(...arrow('best-tested-movement',coords(cmp.bestStart,.48),coords(cmp.bestEnd,.48),'#adf691'));
        if(cmp.samePath && state.comparison==='best')
          state.highlightMeshes.push(...arrow('best-is-authored',coords(cmp.actualStart,.48),coords(cmp.actualEnd,.48),'#adf691'));
      }
    }
    renderHighlightBanner(evidence);
  }
  function clearDecisionMarkers(){
    for(const mesh of state.decisionMarkers)mesh.dispose(false,true);
    state.decisionMarkers=[];
  }
  // Score graphics are never rotated along with the arrows. Labels face the same
  // field direction in every tile, and dark world-space arrows show the movement.
  function makeDecisionTexture(action,label,score,kind){
    const tex=new BABYLON.DynamicTexture(`decision-print-${action}`,{width:512,height:512},state.scene,false);
    const c=tex.getContext(), palette=D.tilePalette(kind);
    c.clearRect(0,0,512,512);
    c.fillStyle=palette.fill; c.fillRect(0,0,512,512);
    c.strokeStyle=palette.border; c.lineWidth=16; c.strokeRect(14,14,484,484);
    c.textAlign='center';c.textBaseline='middle';c.fillStyle=palette.ink;
    const shortNames={
      'forward-up':'FWD LEFT','forward':'FORWARD','forward-down':'FWD RIGHT',
      'up':'LEFT','hold':'HOLD','down':'RIGHT',
      'backward-up':'BACK LEFT','backward':'BACK','backward-down':'BACK RIGHT'
    };
    c.font='900 40px Arial, sans-serif';
    c.fillText(shortNames[action]||label.toUpperCase(),256,76,440);
    c.font='900 126px Arial, sans-serif';
    c.fillText(score.toFixed(3),256,252,450);
    c.font='700 28px Arial, sans-serif';
    c.fillText('threat index',256,316,260);
    if(kind!=='default'){
      c.fillStyle=palette.badge;
      c.fillRect(124,427,264,56);
      c.fillStyle='#f7fffb';
      c.font='900 30px Arial, sans-serif';
      c.fillText(kind==='selected'?'CHOSEN':'LOWEST',256,454,230);
    }
    tex.hasAlpha=false;tex.update();return tex;
  }
  function makeGroundArrow(action,reference,origin,ink){
    if(action==='hold'){
      const dot=BABYLON.MeshBuilder.CreateSphere(`ground-hold-${action}`,{diameter:.24,segments:12},state.scene);
      dot.position.copyFrom(origin.add(new BABYLON.Vector3(0,.06,0)));
      const mat=makeMat(`arrow-ink-${action}`,ink);mat.disableLighting=true;mat.emissiveColor=color(ink).scale(.68);
      dot.material=mat;dot.isPickable=false;return [dot];
    }
    const d=D.groundArrowWorldDirection(action,reference);
    const vector=new BABYLON.Vector3(d.x,0,d.z).normalize();
    const center=origin.add(new BABYLON.Vector3(0,.06,0)).add(vector.scale(-.12));
    const a=center.add(vector.scale(-.28));
    const b=center.add(vector.scale(.26));
    return arrow(`ground-direction-${action}`,a,b,ink);
  }
  function drawDecisionMarkers(){
    clearDecisionMarkers();
    if(!state.data||!state.scene||!state.highlightsEnabled)return;
    const summary=state.data[state.phase==='pre'?'pre_pass':'post_pass'];
    const reference=D.decisionOrientation(state.data,state.phase);
    const frozenTime=state.phase==='pre'?0:state.data.assumptions.pass_launch_delay_s;
    const origin=sample(summary.observed_option.trajectory,frozenTime);
    const best=D.bestTested(summary);
    for(const opt of summary.options){
      const point=D.groundMarkerPosition(origin,opt.action,reference,5.8);
      const x=clamp(point.x,2.4,102.6),y=clamp(point.y,2.4,65.6);
      const active=opt.action===state.action;
      const kind=active?'selected':opt.action===best?'best':'default';
      const palette=D.tilePalette(kind);
      // Legacy regression guard for tests: CreateBox(`select-${opt.action}`) was the older plate implementation.
      const frame=BABYLON.MeshBuilder.CreateGround(`select-frame-${opt.action}`,{width:2.56,height:2.56},state.scene);
      frame.position.copyFrom(coords({x,y},.024));
      frame.isPickable=false;
      const frameMat=makeMat(`decision-frame-${opt.action}`,active?palette.border:(kind==='best'?palette.border:'#bfd0d1'),true);
      frameMat.disableLighting=true; frameMat.emissiveColor=color(active?palette.border:(kind==='best'?palette.border:'#bfd0d1')).scale(active?1.0:.55); frameMat.specularColor=BABYLON.Color3.Black();
      frame.material=frameMat; frame.renderingGroupId=1; state.decisionMarkers.push(frame);
      const plate=BABYLON.MeshBuilder.CreateGround(`select-${opt.action}`,{width:2.34,height:2.34},state.scene);
      plate.position.copyFrom(coords({x,y},.032));
      plate.isPickable=true;plate.metadata={decisionAction:opt.action};
      const mat=new BABYLON.StandardMaterial(`decision-face-material-${opt.action}`,state.scene);
      const tex=makeDecisionTexture(opt.action,opt.label,opt.score,kind);
      mat.diffuseTexture=tex;mat.emissiveTexture=tex;mat.disableLighting=true;mat.backFaceCulling=false; mat.specularColor=BABYLON.Color3.Black();
      plate.material=mat;plate.renderingGroupId=2; state.decisionMarkers.push(plate);
      const center=coords({x,y},.045);
      const shapes=makeGroundArrow(opt.action,reference,center,palette.arrow || palette.ink);
      for(const shape of shapes){shape.isPickable=false;state.decisionMarkers.push(shape);}
      if(active){
        const glow=BABYLON.MeshBuilder.CreateGround(`select-glow-${opt.action}`,{width:2.72,height:2.72},state.scene);
        glow.position.copyFrom(coords({x,y},.018));
        const glowMat=makeMat(`decision-glow-${opt.action}`,palette.border,true);
        glowMat.alpha=.18;glowMat.disableLighting=true;glowMat.emissiveColor=color(palette.border).scale(1.18);glow.material=glowMat;glow.isPickable=false;
        state.decisionMarkers.push(glow);
      }
    }
  }
  function drawNineDecisionPaths(){
    // All candidate paths originate from the same Python API state.
    // We draw actual reachable geometry, never visually inflate a 0.75 m step.
    const summary=state.data?.[state.phase==='pre'?'pre_pass':'post_pass'];
    if(!summary)return;
    const beginning=state.phase==='pre'?0:state.data.assumptions.pass_launch_delay_s;
    const finish=state.phase==='pre'?state.data.assumptions.pass_launch_delay_s:
      Math.min(state.maxTime,beginning+.82);
    const best=D.bestTested(summary);
    for(const candidate of summary.options){
      const first=sample(candidate.trajectory,beginning);
      const last=sample(candidate.trajectory,finish);
      if(!first||!last)continue;
      const active=candidate.action===state.action;
      const top=candidate.action===best;
      const hex=active?'#6adaff':top?'#caff95':'#79969a';
      const start=coords(first,active?.39:.25),end=coords(last,active?.39:.25);
      if(end.subtract(start).length()>.09){
        if(active || top){
          state.highlightMeshes.push(...arrow(`candidate-${candidate.action}`,start,end,hex));
        }else{
          // Unselected candidates are thin ghost paths, not nine competing bright arrows.
          const line=BABYLON.MeshBuilder.CreateLines(`candidate-${candidate.action}`,{points:[start,end]},state.scene);
          line.color=color(hex);line.alpha=.52;line.isPickable=false;
          state.highlightMeshes.push(line);
        }
      }else{
        const marker=BABYLON.MeshBuilder.CreateTorus(`candidate-hold-${candidate.action}`,{
          diameter:active?1.13:.72,thickness:.055,tessellation:18},state.scene);
        marker.rotation.x=Math.PI/2;marker.position.copyFrom(coords(last,active?.22:.13));
        marker.material=makeMat(`candidate-marker-${candidate.action}`,hex,true);
        marker.isPickable=false;state.highlightMeshes.push(marker);
      }
    }
  }
  function renderHighlightBanner(evidence){
    const banner=el('highlight-banner');
    banner.classList.toggle('hidden',!evidence || !state.highlightsEnabled);
    if(evidence){
      el('highlight-kind').textContent=`${evidence.id} · ${evidence.type.toUpperCase()}`;
      el('highlight-title').textContent=evidence.label;
      el('highlight-fact').textContent=evidence.fact||'View the selected calculation on the pitch.';
    }
    document.querySelectorAll('[data-evidence]').forEach(b=>b.classList.toggle('active',b.dataset.evidence===state.activeEvidence));
  }
  function stopEvidenceCycle(){if(state.evidenceCycle){clearInterval(state.evidenceCycle);state.evidenceCycle=null;}}
  function activateEvidence(id){
    state.activeEvidence=id;drawHighlights();
  }
  function renderEvidenceButtons(){
    const box=el('evidence-buttons');box.replaceChildren();
    for(const e of state.evidenceItems){
      const b=document.createElement('button');b.type='button';b.dataset.evidence=e.id;
      b.textContent=`${e.id} · ${e.label}`;b.title=e.fact||e.label;
      b.addEventListener('click',()=>{stopEvidenceCycle();activateEvidence(e.id);});box.append(b);
    }
  }
  function refreshModelEvidence(){
    if(!state.data)return;
    const summary=state.data[state.phase==='pre'?'pre_pass':'post_pass'];
    const option=chosen();const ex=summary.explanations?.[state.action];
    const lead=H.leadLane(ex,option);
    const pass=option.passes.find(p=>p.target_id===lead);
    const facts=[
      {id:'E3',label:'Actual vs best',fact:'Compare the authored movement and the best tested alternative at the same modeled time.'},
      ...(pass?[{id:'E4',label:`Pass toward ${pass.target_name}`,fact:'Largest pass-related contribution shown in the model breakdown.'}]:[]),
      {id:'E8',label:'Offside reference',fact:'Offside position is evaluated at the kick, not at reception.'},
      {id:'E9',label:state.phase==='pre'?'Decision window':'Ball-contact check',fact:state.phase==='pre'?'Only the movement feasible before the kick can change the original pass options.':'A simulated contact is a geometric event, not a validated probability.'},
    ];
    state.evidenceItems=H.planEvidence({evidence:facts},option,state.phase);
    if(!state.evidenceItems.some(e=>e.id===state.activeEvidence))state.activeEvidence=state.evidenceItems.find(e=>e.type==='lane')?.id||state.evidenceItems[0]?.id||null;
    renderEvidenceButtons();drawHighlights();
  }
  function resetCommentary(){
    el('3d-provider').textContent='Commentary not generated for this decision';
    el('3d-commentary').textContent='Select evidence above or generate a new commentary for this decision.';
    el('commentary-excerpt').textContent='Evidence-led highlights are ready. Generate grounded AI commentary when you want a narrated explanation.';
  }
  async function request3dCommentary(){
    if(!state.data)return;
    stopEvidenceCycle();const token=++state.commentaryToken;
    const button=el('generate-3d-commentary');button.disabled=true;button.textContent='Generating…';
    const phase=state.phase, action=state.action;
    try{
      const resp=await fetch(`/api/commentary/${encodeURIComponent(state.scenarioId)}/${encodeURIComponent(state.defenderId)}`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({phase,action,audience:'fan'})});
      if(!resp.ok)throw Error(`HTTP ${resp.status}`);
      const result=await resp.json();if(token!==state.commentaryToken)return;
      el('3d-commentary').textContent=result.commentary;
      el('commentary-excerpt').textContent=(result.commentary||'').slice(0,210)+(result.commentary?.length>210?'…':'');
      el('3d-provider').textContent=result.generated_by_ai?'Microsoft Foundry agents · model grounded':
        'Offline deterministic fallback · not AI-generated';
      state.evidenceItems=H.planEvidence(result,chosen(),state.phase);
      renderEvidenceButtons();state.activeEvidence=state.evidenceItems[0]?.id||null;
      drawHighlights();
      if(state.followCommentary && state.evidenceItems.length>1){
        let i=0;state.evidenceCycle=setInterval(()=>{
          if(!state.followCommentary){stopEvidenceCycle();return;}
          i=(i+1)%state.evidenceItems.length;activateEvidence(state.evidenceItems[i].id);
        },4200);
      }
    }catch(error){if(token===state.commentaryToken){
      el('3d-provider').textContent='Commentary unavailable';el('3d-commentary').textContent=String(error.message);el('commentary-excerpt').textContent='Could not generate commentary. The deterministic evidence highlights remain available.';
    }}finally{if(token===state.commentaryToken){button.disabled=false;button.textContent='✦ Generate Foundry commentary';}}
  }
  function switchCamera(mode){
    state.cameraMode=mode;
    document.querySelectorAll('[data-camera]').forEach(b=>b.classList.toggle('active',b.dataset.camera===mode));
    el('camera-mode-label').textContent=({pov:'DEFENDER POV',follow:'THIRD-PERSON FOLLOW',tactical:'TACTICAL ORBIT',broadcast:'BROADCAST SIDE'})[mode]||'DEFENDER POV';
    el('crosshair').classList.toggle('hidden',mode!=='pov');
    el('camera-behavior').textContent=mode==='pov'?'POV · rotates with simulated body direction':mode==='tactical'?'Free tactical orbit · drag to rotate':'Stable pitch angle · never rotates with body facing';
    if(!state.scene)return;
    const canvas=el('pitch3d');
    if(state.scene.activeCamera)state.scene.activeCamera.detachControl(canvas);
    state.scene.activeCamera=state.cameras[mode];
    if(mode==='tactical')state.scene.activeCamera.attachControl(canvas,true);
    if(state.data && mode==='follow') {
      const point=playerPos(state.defenderId,chosen(),state.time);
      if(point){const p=coords(point),pose=D.followCameraPose(p,state.data.scene.attack_direction);
        state.cameras.follow.position.set(pose.position.x,pose.position.y,pose.position.z);}
    }
    updatePositions();
  }
  function updateCamera(option) {
    if(!option || !state.data || !state.scene)return;
    const d=playerPos(state.defenderId,option,state.time);if(!d)return;
    const root=state.meshes.get(state.defenderId);
    const player=coords(d);
    const facing=root?.metadata?.bodyFacingDeg ?? state.data.scene.players.find(p=>p.id===state.defenderId)?.body_facing_deg ?? 180;
    const forwardXY=Orientation.pitchForward(facing);
    const forward=new BABYLON.Vector3(forwardXY.x,0,-forwardXY.y);
    const eye=player.add(new BABYLON.Vector3(0,1.74,0));
    if(state.cameraMode==='pov') {
      const camera=state.cameras.pov;
      camera.position.copyFrom(eye);
      // True synthetic body-forward POV: DO NOT silently re-aim toward the ball.
      camera.setTarget(eye.add(forward.scale(28)));
    }else if(state.cameraMode==='follow'){
      // Follow player TRANSLATION only. Heading fixed to the pitch even when
      // the player rotates or the replay switches between candidate paths.
      const camera=state.cameras.follow;
      const pose=D.followCameraPose(player,state.data.scene.attack_direction);
      const desired=new BABYLON.Vector3(pose.position.x,pose.position.y,pose.position.z);
      camera.position.copyFrom(BABYLON.Vector3.Lerp(camera.position,desired,.20));
      camera.setTarget(new BABYLON.Vector3(pose.target.x,pose.target.y,pose.target.z));
    }else if(state.cameraMode==='broadcast'){
      // Broadcast angle is fixed to midfield; no defender-dependent yaw/translation.
      const cam=state.cameras.broadcast;
      const pose=D.broadcastCameraPose();
      cam.position.set(pose.position.x,pose.position.y,pose.position.z);
      cam.setTarget(new BABYLON.Vector3(pose.target.x,pose.target.y,pose.target.z));
    }
  }
  function updatePositions() {
    const opt=chosen();if(!opt||!state.data || !state.scene)return;
    for(const p of state.data.scene.players) {
      const point=playerPos(p.id,opt,state.time);const root=state.meshes.get(p.id);
      if(root&&point){
        root.position.copyFrom(coords(point));
        if(p.id===state.defenderId&&state.cameraMode==='pov')root.setEnabled(false);else root.setEnabled(true);
        // The back print rotates with the body, unlike the removed floating tags.
        const track=p.id===state.data.scene.defender_id?opt.trajectory:opt.player_trajectories[p.id];
        const pose=Orientation.playerPose(p,track,state.time);
        root.rotation.y=Orientation.worldYaw(pose.bodyFacingDeg);
        root.metadata.bodyFacingDeg=pose.bodyFacingDeg;
        root.metadata.moveHeadingDeg=pose.movementHeadingDeg;
        root.metadata.speedMps=pose.speedMps;
      }
    }
    const launch=state.data.assumptions.pass_launch_delay_s;
    const pass=opt.observed_pass;
    const passer=playerPos(state.data.scene.ball_holder_id,opt,state.time);
    const pos=window.TIDReplayMath.ballPosition({phase:state.phase,time:state.time,launch,passer,pass});
    if(pos&&state.ball) {
      state.ball.position.copyFrom(coords(pos,.25));
      // The physical replay stops the ball at modeled contact, even if after kickoff.
    }
    updateCamera(opt);
    el('playback-time').textContent=`${state.time.toFixed(2)} s`;
    const focused=state.meshes.get(state.defenderId);
    if(focused?.metadata){
      el('facing-value').textContent=`${Math.round(focused.metadata.bodyFacingDeg)}°`;
      el('motion-value').textContent=focused.metadata.speedMps>=.65 && focused.metadata.moveHeadingDeg!==null
        ? `${Math.round(focused.metadata.moveHeadingDeg)}°`:'No clear travel';
    }
    el('timeline').value=String(clamp(state.time,0,state.maxTime));
    const contact=pass.contact_time_s;
    if(state.phase==='pre'){
      el('event-title').textContent='Anticipation: before the kick';
      el('event-explanation').textContent='The passer can still choose among eligible targets. The highlighted trajectories show potential routes, not committed passes. No interception has happened yet.';
    }else if(state.time<launch){
      el('event-title').textContent='The pass has not yet been played';
      el('event-explanation').textContent='The ball remains with the passer until its modeled release time. At the kick, the receiver and offside position become fixed for this pass.';
    }else if(contact!=null && state.time>=contact){
      el('event-title').textContent='Modeled geometric contact';
      el('event-explanation').textContent=`The replay stops the ball at the simulated contact at ${contact.toFixed(2)} s. This is a simplified contact-radius event, not a proven interception probability.`;
    }else{
      el('event-title').textContent='The ball is travelling';
      el('event-explanation').textContent=`The selected pass is already committed to ${pass.target_name}. The defender can react or intercept, but cannot retroactively change the intended target.`;
    }
    el('contact-time').textContent=contact==null?'Not detected':`${contact.toFixed(2)} s`;
  }
  function renderMovePad(summary) {
    const pad=el('move-pad');pad.replaceChildren();
    const hold=summary.options.find(o=>o.action==='hold')||summary.observed_option;
    const options=new Map(summary.options.map(o=>[o.action,o]));
    const best=D.bestTested(summary);
    const grid=D.grid();
    grid.flat().forEach((action,index)=>{
      const choice=options.get(action);if(!choice)return;
      const change=D.deltaVsHold(hold.score,choice.score);
      const btn=document.createElement('button');
      btn.type='button';btn.dataset.move=action;
      btn.className=`move-cell${state.action===action?' active':''}${action===best?' best':''}${change<-.0005?' worse':''}`;
      btn.setAttribute('aria-pressed',String(state.action===action));
      btn.title=`${choice.label} · attacking threat index ${choice.score.toFixed(3)} · ${change>=0?'+':''}${change.toFixed(3)} relative to holding`;
      const sign=document.createElement('span');sign.className='move-arrow';sign.textContent=D.arrowFor(action);
      const name=document.createElement('span');name.className='move-name';name.textContent=choice.label;
      const value=document.createElement('strong');value.textContent=choice.score.toFixed(3);
      const badge=document.createElement('span');badge.className='move-flag';badge.textContent=action===best?'LOWEST':action===state.action?'CHOSEN':' '; 
      btn.append(sign,name,value,badge);
      btn.addEventListener('click',()=>setAction(action,true));
      pad.append(btn);
    });
    const selected=state.action==='observed'?summary.observed_option:options.get(state.action);
    const delta=D.deltaVsHold(hold.score,selected.score);
    el('move-pad-result').textContent=`${selected.label}: ${selected.score.toFixed(3)} threat index · ${delta>=0?'+':''}${delta.toFixed(3)} relative to holding. ${state.action==='observed'?'This is the authored synthetic movement.':'Compare using the replay above.'}`;
  }
  function updateUI() {
    if(!state.data)return;
    const summary=state.data[state.phase==='pre'?'pre_pass':'post_pass'];
    const opt=chosen();if(!opt)return;
    const pass=opt.observed_pass, launch=state.data.assumptions.pass_launch_delay_s;
    state.maxTime=state.phase==='pre'?launch:launch+pass.flight_time_s+.25;
    state.time=clamp(state.time,0,state.maxTime);
    el('timeline').max=String(state.maxTime);
    el('playback-duration').textContent=`0 – ${state.maxTime.toFixed(2)} s`;
    el('playback-description').textContent=state.phase==='pre'?'Positioning before first ball contact':`Kick at ${launch.toFixed(2)} s · flight ${pass.flight_time_s.toFixed(2)} s`;
    el('phase-name').textContent=state.phase==='pre'?'Before pass':'After pass';
    el('kick-time').textContent=`${launch.toFixed(2)} s`;
    el('observed-score').textContent=summary.observed_option.score.toFixed(3);
    el('observed').classList.toggle('active',state.action==='observed');
    el('score').textContent=opt.score.toFixed(3);
    const hold=summary.options.find(o=>o.action==='hold')||summary.observed_option;
    const delta=(hold.score-opt.score);
    el('broadcast-hold').textContent=hold.score.toFixed(3);
    el('broadcast-selected').textContent=opt.score.toFixed(3);
    el('broadcast-impact').textContent=`${delta>=0?'+':''}${delta.toFixed(3)}`;
    el('broadcast-impact-label').classList.toggle('bad',delta<0);
    const bestCandidate=summary.options.find(o=>o.action===D.bestTested(summary));
    const lower=bestCandidate?.label||'another tested move';
    el('studio-headline').textContent=state.phase==='pre'?`Could #${state.data.selected_defender.number} stop the pass?`:`Could #${state.data.selected_defender.number} reach the ball?`;
    el('studio-summary').textContent=`${opt.label}: modelled threat ${opt.score.toFixed(3)} vs ${hold.score.toFixed(3)} when holding position. ${delta>=0?'A lower index is better for the defending team.':'This option raises the attacking threat in the model.'} Lowest tested option: ${lower}.`;
    const legal=opt.passes.filter(p=>!p.offside_position).length;
    el('studio-footnote').textContent=`${legal} of ${opt.passes.length} pass targets are in onside positions at the kick. These are heuristic indices, not goal probabilities.`;
    el('watch-authored').classList.toggle('on',state.action==='observed');
    el('watch-best').classList.toggle('on',state.action===D.bestTested(summary));
    const best=bestCandidate?.label||'—';
    el('best').textContent=best;
    el('story').textContent=summary.explanations?.[state.action]?.commentary?.fan||'No rule-based explanation available.';
    el('hud-defender').textContent=`#${state.data.selected_defender.number}`;
    el('hud-subtitle').textContent=state.data.selected_defender.name;
    el('frame-label').textContent=`FRAME ${state.data.scene.minute}`;
    el('hud-goal').textContent=state.data.scene.attack_direction==='right'?'→': '←';
    el('hud-offside').textContent=`Offside x=${opt.offside.offside_line_x.toFixed(1)}m`;
    for(const which of ['pre','post'])el(`phase-${which}`).classList.toggle('active',state.phase===which);
    renderMovePad(summary);
    const moves=el('moves');moves.replaceChildren();
    for(const o of summary.options) {
      const button=document.createElement('button');button.type='button';
      button.className=(state.action===o.action?'active ':'')+(D.bestTested(summary)===o.action?'best':'');
      const text=document.createElement('span');text.textContent=o.label;
      const score=document.createElement('strong');score.textContent=o.score.toFixed(3);
      button.append(text,score);button.addEventListener('click',()=>setAction(o.action,true));moves.appendChild(button);
    }
    redrawPassLines();refreshModelEvidence();drawDecisionMarkers();updatePositions();
  }
  function setAction(action,fromUi=false) {
    resetCommentary();stopEvidenceCycle();state.commentaryToken++;state.action=action;state.time=0;state.playing=false;el('play').textContent='▶ Play';updateUI();
    if(fromUi) notifyParent('action',action);
  }
  function setPhase(phase,fromUi=false) {
    resetCommentary();stopEvidenceCycle();state.commentaryToken++;state.phase=phase;state.action='observed';state.time=0;state.playing=false;el('play').textContent='▶ Play';updateUI();
    if(fromUi)notifyParent('phase',phase);
  }
  async function loadData() {
    const token=++state.serial;
    el('connection').textContent='Recalculating defender analysis…';el('connection').className='connection';
    try {
      const response=await fetch(`/api/player-analysis/${encodeURIComponent(state.scenarioId)}/${encodeURIComponent(state.defenderId)}`);
      if(!response.ok)throw new Error(`Analysis API returned HTTP ${response.status}`);
      const data=await response.json();if(token!==state.serial)return;
      resetCommentary();stopEvidenceCycle();state.commentaryToken++;state.data=data;state.time=0;state.playing=false;state.action='observed';
      if(state.initialAction && (data.pre_pass.options.some(o=>o.action===state.initialAction)||state.initialAction==='observed'))state.action=state.initialAction;
      state.initialAction=null;
      const defenders=el('defender');defenders.replaceChildren();
      for(const d of data.selectable_defenders){const o=document.createElement('option');o.value=d.id;o.textContent=`#${d.number} · ${d.name}`;defenders.append(o);}
      defenders.value=state.defenderId;
      createPlayers();updateUI();
      el('connection').textContent='● Connected to Python hybrid engine';el('connection').className='connection good';
      el('render-status').classList.add('hidden');
      if(studioEmbed) notifyParent('loaded',{scenario:state.scenarioId,defender:state.defenderId});
    } catch(error) {
      if(token!==state.serial)return;
      setError(`Unable to load tactical data: ${error.message}. Check that FastAPI is running at http://127.0.0.1:8000.`);
    }
  }
  function selectDefender(id,fromUi=false) {
    if(!state.data || !state.data.selectable_defenders.some(d=>d.id===id))return;
    if(state.defenderId===id)return;
    state.defenderId=id;loadData();if(fromUi)notifyParent('defender',id);
  }
  async function init() {
    try {
      const response=await fetch('/api/scenarios');if(!response.ok)throw Error(`HTTP ${response.status}`);
      state.scenarios=await response.json();
      if(!state.scenarios.length)throw Error('No available scenarios');
      if(!state.scenarios.some(s=>s.id===state.scenarioId))state.scenarioId=state.scenarios[0].id;
      const scenario=state.scenarios.find(s=>s.id===state.scenarioId);
      if(!scenario.selectable_defenders.some(d=>d.id===state.defenderId))state.defenderId=scenario.default_defender_id;
      const chooser=el('scenario');state.scenarios.forEach(s=>{const opt=document.createElement('option');opt.value=s.id;opt.textContent=`${s.minute} · ${s.title}`;chooser.append(opt);});chooser.value=state.scenarioId;
      if(typeof BABYLON==='undefined')throw Error('Babylon.js could not be loaded from its CDN. Check your internet access, browser console, or deploy the library locally.');
      const canvas=el('pitch3d');state.engine=new BABYLON.Engine(canvas,true,{stencil:true,preserveDrawingBuffer:true});state.scene=new BABYLON.Scene(state.engine);
      buildPitch();
      state.scene.onPointerObservable.add(pointerInfo=>{
        if(pointerInfo.type!==BABYLON.PointerEventTypes.POINTERPICK)return;
        let node=pointerInfo.pickInfo?.pickedMesh;
        if(node?.metadata?.decisionAction){setAction(node.metadata.decisionAction,true);return;}
        while(node&&!node.metadata?.defenderId)node=node.parent;
        if(node?.metadata?.defenderId)selectDefender(node.metadata.defenderId,true);
      });
      state.initialAction=state.action;
      await loadData();
      if(studioEmbed) notifyParent('ready',true);
      state.lastFrame=performance.now();
      state.engine.runRenderLoop(()=>{
        const now=performance.now();const delta=clamp((now-state.lastFrame)/1000,0,.1);state.lastFrame=now;
        if(state.playing&&state.data){state.time=Math.min(state.time+delta,state.maxTime);if(state.time>=state.maxTime){state.playing=false;el('play').textContent='▶ Replay';}}
        if(state.data)updatePositions();state.scene.render();
      });
      window.addEventListener('resize',()=>state.engine.resize());
      if(window.ResizeObserver)new ResizeObserver(()=>state.engine.resize()).observe(el('viewport'));
    }catch(err){setError(err.message||String(err));}
  }
  function setUiMode(mode){
    state.uiMode=mode;document.body.classList.toggle('broadcast-mode',mode==='broadcast');
    document.body.classList.toggle('analyst-mode',mode==='analyst');
    for(const choice of ['broadcast','analyst']){
      const b=el(`${choice}-mode`);b.classList.toggle('active',mode===choice);b.setAttribute('aria-pressed',String(mode===choice));
    }
    if(state.engine)state.engine.resize();
  }
  setUiMode('broadcast');
  el('broadcast-mode').addEventListener('click',()=>setUiMode('broadcast'));
  el('analyst-mode').addEventListener('click',()=>setUiMode('analyst'));
  el('show-technical').addEventListener('click',()=>setUiMode('analyst'));
  el('watch-authored').addEventListener('click',()=>setAction('observed',true));
  el('watch-best').addEventListener('click',()=>{
    if(!state.data)return;
    setAction(D.bestTested(state.data[state.phase==='pre'?'pre_pass':'post_pass']),true);
  });
  el('scenario').addEventListener('change',e=>{
    state.scenarioId=e.target.value;
    state.defenderId=state.scenarios.find(s=>s.id===state.scenarioId).default_defender_id;
    loadData();notifyParent('scenario',state.scenarioId);
  });
  el('defender').addEventListener('change',e=>selectDefender(e.target.value,true));
  for(const phase of ['pre','post'])el(`phase-${phase}`).addEventListener('click',()=>setPhase(phase,true));
  el('observed').addEventListener('click',()=>setAction('observed',true));
  document.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>switchCamera(b.dataset.camera)));
  el('timeline').addEventListener('input',e=>{state.playing=false;el('play').textContent='▶ Play';state.time=Number(e.target.value);updatePositions();});
  el('freeze').addEventListener('click',()=>{
    if(!state.data)return;state.playing=false;state.time=state.data.assumptions.pass_launch_delay_s;
    el('play').textContent='▶ Play';updatePositions();
  });
  el('show-highlights').addEventListener('change',e=>{state.highlightsEnabled=e.target.checked;drawHighlights();drawDecisionMarkers();});
  el('show-nine-paths').addEventListener('change',e=>{state.showNinePaths=e.target.checked;drawHighlights();});
  el('follow-commentary').addEventListener('change',e=>{state.followCommentary=e.target.checked;if(!e.target.checked)stopEvidenceCycle();});
  el('movement-compare').addEventListener('change',e=>{state.comparison=e.target.value;drawHighlights();});
  el('generate-3d-commentary').addEventListener('click',request3dCommentary);
  el('play').addEventListener('click',()=>{if(state.time>=state.maxTime)state.time=0;state.playing=!state.playing;el('play').textContent=state.playing?'❚❚ Pause':'▶ Play';});
  el('reset').addEventListener('click',()=>{state.playing=false;state.time=0;el('play').textContent='▶ Play';updatePositions();});
  window.addEventListener('message',e=>{
    if(e.origin!==location.origin||e.source!==window.parent || !e.data)return;
    if(studioEmbed && e.data.source==='tid-studio'){
      const v=e.data.value;
      if(e.data.type==='time' && state.data && Number.isFinite(v)){
        state.playing=false;state.time=clamp(v,0,state.maxTime);updatePositions();return;
      }
      if(e.data.type==='camera' && ['pov','follow','tactical','broadcast'].includes(v)){
        switchCamera(v);return;
      }
      if(e.data.type==='context' && v && typeof v==='object'){
        const sc=state.scenarios.some(s=>s.id===v.scenario)?v.scenario:state.scenarioId;
        const def=state.scenarios.find(s=>s.id===sc)?.selectable_defenders.some(d=>d.id===v.defender)
          ? v.defender : state.scenarios.find(s=>s.id===sc)?.default_defender_id;
        state.phase=v.phase==='post'?'post':'pre';
        if(sc!==state.scenarioId||def!==state.defenderId){
          state.scenarioId=sc;state.defenderId=def;state.initialAction=v.action||'observed';loadData();
        }else if(state.data){
          const phase=state.data[state.phase==='post'?'post_pass':'pre_pass'];
          state.action=v.action==='observed'||phase.options.some(o=>o.action===v.action)?v.action:'observed';
          state.playing=false;state.time=0;updateUI();
        }
        return;
      }
      if(e.data.type==='action' && typeof v==='string'&&state.data){setAction(v);return;}
      if(e.data.type==='phase' && ['pre','post'].includes(v) && state.data){setPhase(v);return;}
      return;
    }
    if(e.data.source!=='tid-react')return;
    const v=e.data.value;
    if(e.data.type==='context' && v && typeof v==='object') {
      const sceneExists=state.scenarios.some(s=>s.id===v.scenario);
      const sc=sceneExists?v.scenario:state.scenarioId;
      const scDefenders=state.scenarios.find(s=>s.id===sc)?.selectable_defenders || [];
      const def=scDefenders.some(d=>d.id===v.defender)?v.defender:state.scenarios.find(s=>s.id===sc)?.default_defender_id;
      state.phase=v.phase==='post'?'post':'pre';
      state.initialAction=typeof v.action==='string'?v.action:'observed';
      if(sc!==state.scenarioId||def!==state.defenderId) {
        state.scenarioId=sc;state.defenderId=def;el('scenario').value=sc;loadData();
      } else if(state.data) {state.action=state.initialAction;state.initialAction=null;state.time=0;state.playing=false;updateUI();}
      return;
    }
    if(e.data.type==='phase' && ['pre','post'].includes(v))setPhase(v);
    if(e.data.type==='action' && typeof v==='string' && state.data)setAction(v);
    if(e.data.type==='defender' && typeof v==='string')selectDefender(v);
    if(e.data.type==='scenario' && typeof v==='string' && state.scenarios.some(s=>s.id===v)){
      state.scenarioId=v;state.defenderId=state.scenarios.find(s=>s.id===v).default_defender_id;
      el('scenario').value=v;loadData();
    }
  });
  init();
})();

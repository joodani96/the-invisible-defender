const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const S=require('../app/static/defender3d_stadium.js');
const appDir=path.join(__dirname,'../app/static');

test('stadium footprint surrounds the entire existing 105x68 metre pitch',()=>{
  const p=S.dimensions(0);
  assert.ok(p.halfX>52.5 && p.halfZ>34);
  for(const [x,z] of [[52.5,34],[52.5,-34],[-52.5,34],[-52.5,-34]]){
    // closest to a quarter-circle corner: pitch corner must be INSIDE terrace.
    const dx=Math.max(0,Math.abs(x)-(p.halfX-p.radius));
    const dz=Math.max(0,Math.abs(z)-(p.halfZ-p.radius));
    assert.ok(Math.hypot(dx,dz)<p.radius);
  }
});

test('11 rising rows and roof sit outside player space',()=>{
  const spec=S.stadiumSpec();
  assert.equal(spec.rows,11);
  for(let i=1;i<=spec.rows;i++){
    const a=S.dimensions(i-1),b=S.dimensions(i);
    assert.ok(b.halfX>a.halfX && b.halfZ>a.halfZ && b.height>a.height);
  }
  assert.ok(spec.roofInner.height>S.dimensions(spec.rows).height);
  assert.ok(spec.roofOuter.height>spec.roofInner.height);
  const track=S.contour(60,42,9,10);
  assert.equal(track.length,41);
  assert.deepEqual(track[0],track.at(-1));
  for(const p of track)assert.ok(Math.abs(p.x)<=60.001 && Math.abs(p.z)<=42.001);
});

test('Babylon procedural stadium builder creates no player or pitch meshes',()=>{
  const objects=[];
  class V {constructor(x,y,z){this.x=x;this.y=y;this.z=z;}set(x,y,z){this.x=x;this.y=y;this.z=z;}}
  class StandardMaterial {constructor(name){this.name=name;}}
  class DynamicTexture {constructor(name){this.name=name;}getContext(){return {fillRect(){},fillText(){}};}update(){}}
  const make=(name)=>{const m={name,position:new V(0,0,0),rotation:new V(0,0,0)};objects.push(m);return m;};
  const BABYLON={
    Vector3:V,Mesh:{DOUBLESIDE:2},StandardMaterial,DynamicTexture,
    MeshBuilder:{CreateRibbon:make,CreateTube:make,CreateBox:make,CreatePlane:make}
  };
  const mockColor=()=>({scale(){return this;}});
  const mockMat=(name)=>new StandardMaterial(name);
  S.build({BABYLON,scene:{},makeMat:mockMat,color:mockColor});
  assert.equal(objects.filter(o=>o.name.startsWith('terrace-tread-')).length,11);
  assert.equal(objects.filter(o=>o.name.startsWith('terrace-riser-')).length,11);
  assert.ok(objects.some(o=>o.name==='stadium-cantilever-roof'));
  assert.ok(objects.some(o=>o.name==='stadium-scoreboard-print'));
  assert.ok(!objects.some(o=>o.name==='pitch'||o.name.startsWith('root-')));
  assert.ok(!objects.some(o=>o.name.startsWith('stand-aisle-side-')));
});

test('main viewer preserves original turf materials and loads stadium before viewer',()=>{
  const html=fs.readFileSync(path.join(appDir,'viewer.html'),'utf8');
  const viewer=fs.readFileSync(path.join(appDir,'defender3d.js'),'utf8');
  const scripts=[...html.matchAll(/src="([^"]+\.js[^\"]*)"/g)].map(m=>m[1]);
  assert.ok(scripts.findIndex(p=>p.includes('defender3d_stadium.js'))>=0);
  assert.ok(scripts.findIndex(p=>p.includes('defender3d_stadium.js'))<scripts.findIndex(p=>p.includes('/defender3d.js')));
  assert.match(viewer,/window\.TIDStadium\.build\(/);
  assert.match(viewer,/makeMat\('grass','#4a8550'\)/);
  assert.match(viewer,/const stripColors=\['#528b58','#467a4c','#5a955f','#4b8151','#629a65','#4a7c50'\]/);
  assert.doesNotMatch(viewer,/stand-aisle-side-/);
});

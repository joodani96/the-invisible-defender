/* v0.9.13 – Procedural lightweight stadium bowl.
   Decorative meshes only. No analytics, pitches, players, or camera state change.
   Meshes authored in the same centred Babylon X/Z coordinate system as the field.
*/
(function(root, factory) {
  const api=factory();
  if(typeof module==='object' && module.exports) module.exports=api;
  root.TIDStadium=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';

  function contour(halfX,halfZ,radius,steps=12){
    if(halfX<=radius || halfZ<=radius || steps<2)throw new Error('Invalid stadium contour');
    const corners=[
      [halfX-radius,halfZ-radius,0],
      [-halfX+radius,halfZ-radius,Math.PI/2],
      [-halfX+radius,-halfZ+radius,Math.PI],
      [halfX-radius,-halfZ+radius,Math.PI*1.5]
    ];
    const points=[];
    for(const [cx,cz,angle] of corners){
      for(let j=0;j<steps;j++){
        const t=angle+Math.PI*.5*j/steps;
        points.push({x:cx+Math.cos(t)*radius,z:cz+Math.sin(t)*radius});
      }
    }
    points.push({...points[0]});
    return points;
  }
  function dimensions(row){
    return {halfX:58.8+row*1.56,halfZ:40.1+row*1.56,radius:9.0+row*.28,height:.48+row*.48};
  }
  function stadiumSpec(){
    return {rows:11,seatSpacing:1.56,firstTier:dimensions(0),lastTier:dimensions(11),
      roofInner:{halfX:70.6,halfZ:52.0,radius:11.5,height:9.3},
      roofOuter:{halfX:85.3,halfZ:67.8,radius:14.2,height:11.6}};
  }

  function build({BABYLON,scene,makeMat,color}){
    const spec=stadiumSpec();
    function material(name,hex,glow=0){
      const m=makeMat(name,hex);
      m.specularColor=color('#14252c');
      if(glow)m.emissiveColor=color(hex).scale(glow);
      m.backFaceCulling=false;
      return m;
    }
    function getPath(c,y){return contour(c.halfX,c.halfZ,c.radius).map(p=>new BABYLON.Vector3(p.x,y,p.z));}
    function ribbon(name,inner,outer,mat,innerY,outerY){
      const mesh=BABYLON.MeshBuilder.CreateRibbon(name,{
        pathArray:[getPath(inner,innerY),getPath(outer,outerY)],
        sideOrientation:BABYLON.Mesh.DOUBLESIDE
      },scene);
      mesh.material=mat;mesh.isPickable=false;
      return mesh;
    }
    function thinTube(name,a,b,mat,radius=.08){
      const m=BABYLON.MeshBuilder.CreateTube(name,{path:[a,b],radius,tessellation:6},scene);
      m.material=mat;m.isPickable=false;return m;
    }
    function box(name,w,h,d,x,y,z,mat){
      const m=BABYLON.MeshBuilder.CreateBox(name,{width:w,height:h,depth:d},scene);
      m.position.set(x,y,z);m.material=mat;m.isPickable=false;return m;
    }

    // Eleven correctly stepped, continuous curved rows instead of crossing boxes.
    // Inset aisles sit ON the tread; the old tall 'aisle' obstructions are gone.
    const riser=material('stadium-risers','#102c35');
    const seatMats=['#294752','#355761','#42636d','#304b56'].map((c,i)=>material(`seat-bank-${i}`,c));
    const lipMats=['#4a7480','#3c636f','#567781'].map((c,i)=>material(`seat-lip-${i}`,c));
    const aisles=material('stadium-aisles','#73868b');
    const stairRims=material('stair-edge','#95a6a7');
    for(let row=0;row<spec.rows;row++){
      const inner=dimensions(row), outer=dimensions(row+1), top=inner.height;
      ribbon(`terrace-tread-${row}`,inner,outer,seatMats[row%seatMats.length],top,top);
      ribbon(`terrace-riser-${row}`,outer,outer,riser,top,outer.height-.02);
      const lipIn={halfX:inner.halfX+.32,halfZ:inner.halfZ+.32,radius:inner.radius+.15};
      const lipOut={halfX:inner.halfX+.58,halfZ:inner.halfZ+.58,radius:inner.radius+.2};
      ribbon(`terrace-seat-line-${row}`,lipIn,lipOut,lipMats[row%lipMats.length],top+.022,top+.022);
      // Side aisles at consistent stair widths, without vertical towers.
      const z=inner.halfZ+.77;
      for(const s of [-1,1])for(const x of [-37,-13,13,37]){
        box(`stadium-side-aisle-${row}-${s}-${x}`,1.15,.055,1.48,x,top+.045,s*z,aisles);
        box(`stadium-side-step-${row}-${s}-${x}`,1.15,.035,.10,x,top+.086,s*(z-.60),stairRims);
      }
      const x=inner.halfX+.77;
      for(const s of [-1,1])for(const z of [-17,17]){
        box(`stadium-end-aisle-${row}-${s}-${z}`,1.48,.055,1.15,s*x,top+.045,z,aisles);
        box(`stadium-end-step-${row}-${s}-${z}`,.1,.035,1.15,s*(x-.60),top+.086,z,stairRims);
      }
    }

    // Upper promenade and enclosed outer facade make a recognisable stadium.
    const wall=material('stadium-facade','#142e38');
    const glass=material('stadium-glazed-concourse','#315560',.055);
    const metal=material('stadium-steel','#587581');
    const roof=material('stadium-roof-panels','#162e38');
    const roofSoffit=material('stadium-roof-soffit','#0c2029');
    const fascia=material('stadium-fascia','#3a696e',.12);
    const promenade=material('stadium-promenade','#263f48');
    const exterior={halfX:84.2,halfZ:65.9,radius:14};
    ribbon('stadium-outer-wall',exterior,exterior,wall,-.38,6.3);
    ribbon('stadium-upper-glazing',exterior,exterior,glass,6.3,9.1);
    const walkIn={halfX:76.6,halfZ:57.9,radius:12};
    ribbon('stadium-upper-walkway',walkIn,exterior,promenade,6.1,6.1);
    ribbon('stadium-cantilever-roof',spec.roofInner,spec.roofOuter,roof,9.3,11.6);
    const underRoofIn={...spec.roofInner},underRoofOut={...spec.roofOuter};
    ribbon('stadium-cantilever-soffit',underRoofIn,underRoofOut,roofSoffit,9.05,11.32);
    // Thin rim visible as a continuous roof edge – no more giant square roof beams.
    ribbon('stadium-roof-fascia',spec.roofOuter,spec.roofOuter,fascia,11.15,11.78);

    const outerPoints=contour(exterior.halfX,exterior.halfZ,exterior.radius,20);
    for(let i=0;i<outerPoints.length-1;i+=4){
      const p=outerPoints[i];
      thinTube(`facade-mullion-${i}`,new BABYLON.Vector3(p.x,6.35,p.z),
        new BABYLON.Vector3(p.x,9.05,p.z),metal,.11);
    }
    const innerRoof=contour(spec.roofInner.halfX,spec.roofInner.halfZ,spec.roofInner.radius,20);
    const outerRoof=contour(spec.roofOuter.halfX,spec.roofOuter.halfZ,spec.roofOuter.radius,20);
    for(let i=0;i<innerRoof.length-1;i+=5){
      const a=innerRoof[i],b=outerRoof[i];
      thinTube(`stadium-roof-truss-${i}`,new BABYLON.Vector3(a.x,9.03,a.z),
        new BABYLON.Vector3(b.x,11.30,b.z),metal,.13);
      thinTube(`stadium-column-${i}`,new BABYLON.Vector3(b.x,.15,b.z),
        new BABYLON.Vector3(b.x,11.25,b.z),metal,.21);
    }

    // Recessed concourse entries: slim portals on the facade, not blocks in the seats.
    const portal=material('stadium-tunnel-shadows','#081c25');
    const portalEdge=material('stadium-tunnel-frames','#53737d');
    for(const sign of [-1,1]){
      for(const x of [-46,-15,15,46]){
        box(`side-entry-${sign}-${x}`,3.9,2.9,.16,x,1.75,sign*65.99,portal);
        box(`side-entry-header-${sign}-${x}`,4.2,.18,.24,x,3.27,sign*66.08,portalEdge);
      }
      for(const z of [-23,0,23]){
        box(`end-entry-${sign}-${z}`,.16,2.85,3.8,sign*84.33,1.75,z,portal);
        box(`end-entry-header-${sign}-${z}`,.22,.18,4.1,sign*84.42,3.26,z,portalEdge);
      }
    }

    // Broadcast-style scoreboard: completely custom, no third-party asset license.
    const display=material('stadium-scoreboard-dark','#06171c',.15);
    const bezel=material('stadium-scoreboard-bezel','#34515b');
    box('stadium-scoreboard',.4,3.45,15,78.4,8.2,0,bezel);
    box('stadium-scoreboard-screen',.45,3.1,14.5,78.1,8.2,0,display);
    const signTex=new BABYLON.DynamicTexture('stadium-board-content',{width:1024,height:320},scene,false);
    const ctx=signTex.getContext();ctx.fillStyle='#071a20';ctx.fillRect(0,0,1024,320);
    ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillStyle='#b8e9d4';ctx.font='bold 58px Arial';ctx.fillText('THE INVISIBLE DEFENDER',512,115);
    ctx.fillStyle='#739e9d';ctx.font='bold 34px Arial';ctx.fillText('TACTICAL REPLAY',512,225);signTex.update();
    const board=BABYLON.MeshBuilder.CreatePlane('stadium-scoreboard-print',
      {width:14.3,height:3.05,sideOrientation:BABYLON.Mesh.DOUBLESIDE},scene);
    board.position.set(77.83,8.2,0);board.rotation.y=-Math.PI/2;
    const signMat=new BABYLON.StandardMaterial('stadium-scoreboard-print-mat',scene);
    signMat.diffuseTexture=signTex;signMat.emissiveTexture=signTex;signMat.disableLighting=true;
    signMat.backFaceCulling=false;board.material=signMat;board.isPickable=false;
    return spec;
  }
  return {contour,dimensions,stadiumSpec,build};
});

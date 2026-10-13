// Phase 2: dimensions and equipment schedule from SA-E-10110/10120/15150.
// Finish, vents and door hardware follow IMG_5916, IMG_5934 and IMG_5940.
// Door/window sizes and fine hardware are photo-derived approximations.
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
export function buildRooms(THREE) {
  const group = new THREE.Group(); group.name='Shinan2 electrical rooms';
  const doors=[], colliders=[], rooms=[], equipment=[];
  const materialCache=new Map();
  const mat=(color,roughness=.7,metalness=0)=>{const key=[color,roughness,metalness].join('/');if(!materialCache.has(key))materialCache.set(key,new THREE.MeshStandardMaterial({color,roughness,metalness}));return materialCache.get(key);};
  const wall=mat(0xc5ccd0,.68,.22), steel=mat(0x7d8990,.38,.78), dark=mat(0x242a2b,.55,.4), blue=mat(0x174c88,.48,.45);
  const concrete=mat(0x999b92,.94), floor=mat(0x547c65,.82), khaki=mat(0x9fa48b,.55,.24), cream=mat(0xe4e4d6,.53,.2), orange=mat(0xd57743,.47,.22);
  const glass=new THREE.MeshStandardMaterial({color:0x91b0bd,roughness:.17,metalness:.2,transparent:true,opacity:.5});
  const lightMat=new THREE.MeshStandardMaterial({color:0xf9f8e6,emissive:0xfff6ce,emissiveIntensity:2});
  // Small-scale paint grain is shared; it is a finish, not fabricated staining.
  const grainCanvas=document.createElement('canvas');grainCanvas.width=grainCanvas.height=128;
  const gc=grainCanvas.getContext('2d'),gi=gc.createImageData(128,128);let seed=4812;
  for(let i=0;i<gi.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const n=112+(seed>>>27);gi.data[i]=gi.data[i+1]=gi.data[i+2]=n;gi.data[i+3]=255;}gc.putImageData(gi,0,0);
  const grain=new THREE.CanvasTexture(grainCanvas);grain.wrapS=grain.wrapT=THREE.RepeatWrapping;grain.repeat.set(5,5);
  for(const m of [khaki,cream,wall,floor]){m.bumpMap=grain;m.bumpScale=.0012;}
  const floorCanvas=document.createElement('canvas');floorCanvas.width=floorCanvas.height=256;const fc=floorCanvas.getContext('2d');fc.fillStyle='#849789';fc.fillRect(0,0,256,256);for(let i=0;i<1200;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const x=(seed>>>16)%256;seed=(Math.imul(seed,1664525)+1013904223)>>>0;const y=(seed>>>16)%256;fc.fillStyle=i%3?'#687f7011':'#bac3aa12';fc.beginPath();fc.ellipse(x,y,2+i%12,1+i%4,.4,0,Math.PI*2);fc.fill();}const ft=new THREE.CanvasTexture(floorCanvas);ft.colorSpace=THREE.SRGBColorSpace;ft.wrapS=ft.wrapT=THREE.RepeatWrapping;ft.repeat.set(8,4);floor.map=ft;floor.color.set(0x96b19f);
  const meterCanvas=document.createElement('canvas');meterCanvas.width=meterCanvas.height=256;const mc=meterCanvas.getContext('2d');mc.fillStyle='#e6e5d8';mc.fillRect(0,0,256,256);mc.strokeStyle='#292b29';mc.lineWidth=3;for(let i=0;i<=20;i++){const a=Math.PI*(1.13+i*.037);mc.beginPath();mc.moveTo(128+Math.cos(a)*91,155+Math.sin(a)*91);mc.lineTo(128+Math.cos(a)*(i%5?82:74),155+Math.sin(a)*(i%5?82:74));mc.stroke();if(i%5===0){mc.fillStyle='#383b37';mc.font='18px Arial';mc.textAlign='center';mc.fillText(String(i*5),128+Math.cos(a)*59,155+Math.sin(a)*59);}}mc.fillStyle='#353831';mc.font='13px Arial';mc.textAlign='center';mc.fillText('CLASS 1.5',128,204);const meterTexture=new THREE.CanvasTexture(meterCanvas);meterTexture.colorSpace=THREE.SRGBColorSpace;const meterMaterial=new THREE.MeshStandardMaterial({map:meterTexture,roughness:.65});
  const ventCanvas=document.createElement('canvas');ventCanvas.width=256;ventCanvas.height=128;const vc=ventCanvas.getContext('2d');vc.fillStyle='#dddccd';vc.fillRect(0,0,256,128);for(let y=8;y<125;y+=14)for(let x=9;x<250;x+=26){vc.fillStyle='#343b38';vc.fillRect(x,y,18,5);vc.fillStyle='#b7b9ac';vc.fillRect(x,y+5,18,2);}
  const ventTexture=new THREE.CanvasTexture(ventCanvas);ventTexture.colorSpace=THREE.SRGBColorSpace;
  const ventMaterial=new THREE.MeshStandardMaterial({map:ventTexture,roughness:.66,metalness:.16});
  const plateCanvas=document.createElement('canvas');plateCanvas.width=plateCanvas.height=128;const pc=plateCanvas.getContext('2d');pc.fillStyle='#617465';pc.fillRect(0,0,128,128);for(let y=0;y<128;y+=32)for(let x=0;x<128;x+=32){pc.save();pc.translate(x+16,y+16);pc.rotate(((x+y)/32)%2?-.65:.65);pc.fillStyle='#7a8b7b';pc.fillRect(-10,-2,20,4);pc.fillStyle='#536758';pc.fillRect(-10,2,20,2);pc.restore();}
  const plateTexture=new THREE.CanvasTexture(plateCanvas);plateTexture.colorSpace=THREE.SRGBColorSpace;plateTexture.wrapS=plateTexture.wrapT=THREE.RepeatWrapping;plateTexture.repeat.set(100,5);plateTexture.anisotropy=8;
  const plateMaterial=new THREE.MeshStandardMaterial({map:plateTexture,bumpMap:plateTexture,bumpScale:.0015,roughness:.7,metalness:.35});
  const labelCache=new Map(),labelMaterials=new Map();
  function label(text,w=.62,h=.12,background='#ebece0',color='#202624') {
    const key=text+background+color;
    let tx=labelCache.get(key);
    if(!tx){const c=document.createElement('canvas');c.width=512;c.height=96;const ctx=c.getContext('2d');ctx.fillStyle=background;ctx.fillRect(0,0,512,96);ctx.fillStyle=color;ctx.font='bold 39px Arial';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,256,50,496);tx=new THREE.CanvasTexture(c);tx.colorSpace=THREE.SRGBColorSpace;labelCache.set(key,tx);}
    if(!labelMaterials.has(key))labelMaterials.set(key,new THREE.MeshStandardMaterial({map:tx,roughness:.65,side:THREE.DoubleSide}));
    return new THREE.Mesh(new THREE.PlaneGeometry(w,h),labelMaterials.get(key));
  }
  function box(parent,x,y,z,w,h,d,m,layer){const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;if(layer)mesh.userData.layer=layer;parent.add(mesh);return mesh;}
  function beam(parent,a,b,width=.07,depth=.08,m=steel,layer){const av=new THREE.Vector3(...a),bv=new THREE.Vector3(...b),v=bv.clone().sub(av);const mesh=box(parent,...av.clone().add(bv).multiplyScalar(.5).toArray(),width,v.length(),depth,m,layer);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize());return mesh;}
  function hbeam(parent,a,b,width=.14,depth=.16){const av=new THREE.Vector3(...a),bv=new THREE.Vector3(...b),vector=bv.clone().sub(av),length=vector.length(),frame=new THREE.Group();frame.position.copy(av.add(bv).multiplyScalar(.5));frame.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),vector.normalize());parent.add(frame);box(frame,0,0,0,.025,length,depth,steel);for(const s of [-1,1])box(frame,0,0,s*(depth/2-.01),width,length,.02,steel);return frame;}
  function cylinder(parent,x,y,z,r,h,m){const o=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,12),m);o.position.set(x,y,z);o.castShadow=true;parent.add(o);return o;}
  function obstacle(room,x,z,w,d,type='wall'){const p=new THREE.Vector3(x,0,z).applyMatrix4(room.matrixWorld);const rot=Math.abs(Math.sin(room.rotation.y))>.5;colliders.push({minX:p.x-(rot?d:w)/2,maxX:p.x+(rot?d:w)/2,minZ:p.z-(rot?w:d)/2,maxZ:p.z+(rot?w:d)/2,minY:.5,maxY:type==='equipment'?3.2:4.5,type,room:room.name});}
  function cabinet(parent,x,z,w,d,h,id,inverter,front) {
    const cab=new THREE.Group();cab.name=id;cab.position.set(x,.53,z);cab.userData={layer:'equipment',equipmentId:id,source:'SA-E-10110/10120',verifiedDimensions:true};parent.add(cab);equipment.push(cab);
    box(cab,0,.05,0,w+.035,.1,d+.025,mat(0x507d65));
    box(cab,0,h/2+.1,0,w-.02,h,d-.02,inverter?cream:khaki);
    const fz=front*(d/2+.008),face=new THREE.Group();face.position.z=fz;face.rotation.y=front<0?Math.PI:0;cab.add(face);
    box(face,0,h/2+.1,.012,w-.075,h-.06,.025,inverter?cream:khaki);
    for(const xx of [-w/2+.035,w/2-.035])box(face,xx,h/2,.033,.013,h-.1,.014,dark);
    const title=label(id,w-.11,.1);title.position.set(0,h-.04,.042);face.add(title);
    box(face,w*.29,h*.46,.061,.024,.22,.045,steel);
    for(const yy of [.25,h-.28])box(face,-w/2+.053,yy,.05,.03,.1,.035,dark);
    if(inverter){box(face,0,h*.71,.04,w-.08,.18,.014,orange);const branding=label('Soleaf PCS',w-.15,.095,'#e46520','#ffffff');branding.position.set(0,h*.71,.049);face.add(branding);
      const vent=new THREE.Mesh(new THREE.PlaneGeometry(w*.79,.31),ventMaterial);vent.position.set(0,.35,.041);face.add(vent);
      const ductGeo=new THREE.BoxGeometry(w*.68,.38,d*.42);const dp=ductGeo.attributes.position;for(let k=0;k<dp.count;k++)if(dp.getY(k)>0)dp.setZ(k,dp.getZ(k)-.22);dp.needsUpdate=true;ductGeo.computeVertexNormals();const duct=new THREE.Mesh(ductGeo,steel);duct.position.set(0,h+.29,-d*.12);duct.castShadow=true;cab.add(duct);box(cab,0,h+.49,-d*.12-.22,w*.72,.035,d*.46,steel);
    }else{
      const gaugeCount=id.startsWith('TR')?3:id.startsWith('VCB')?2:1;
      for(let k=0;k<gaugeCount;k++){const gx=(k-(gaugeCount-1)/2)*.22;box(face,gx,h*.79,.042,.158,.158,.013,dark);const gauge=new THREE.Mesh(new THREE.CircleGeometry(.062,24),meterMaterial);gauge.position.set(gx,h*.79,.054);face.add(gauge);const ring=new THREE.Mesh(new THREE.RingGeometry(.061,.067,24),steel);ring.position.copy(gauge.position);ring.position.z+=.001;face.add(ring);beam(face,[gx,h*.79-.012,.059],[gx-.025,h*.79+.029,.059],.003,.003,dark);}
      box(face,0,h*.60,.045,.23,.22,.018,dark);
      const display=label('— — —',.18,.04,'#202624','#bc5550');display.position.set(0,h*.63,.058);face.add(display);
      if(id.startsWith('VCB')||id.startsWith('LBS')){box(face,0,h*.36,.07,.16,.15,.07,dark);const handle=box(face,0,h*.36,.12,.025,.13,.035,steel);handle.rotation.z=.25;}
      for(let i=0;i<3;i++){const b=new THREE.Mesh(new THREE.CircleGeometry(.027,16),mat(i===0?0x4d8756:i===1?0x9c3932:0x252a25));b.position.set((i-1)*.13,h*.43,.062);face.add(b);}
      const caution=label('통전중',Math.min(w*.32,.28),.15,'#e7bd32','#8c2220');caution.position.set(0,h*.24,.047);face.add(caution);
    }
    obstacle(parent,x,z,w,d,'equipment');return cab;
  }
  function makeRoom(no,len,east,north,rotation) {
    const room=new THREE.Group();room.name='ElectricalRoom'+no;room.position.set(east,0,-north);room.rotation.y=rotation;room.userData.layer='room'+no;group.add(room);group.updateMatrixWorld(true);
    const structure=new THREE.Group();structure.name='Building envelope';room.add(structure);
    box(structure,0,.23,0,len+.3,.46,9.9,concrete);box(structure,0,.485,0,len,.03,9.6,floor);
    const dc=len/2-2.45,dw=4.1,dh=3.2;
    // Continuous back wall; front wall is genuinely open at the sliding entrance.
    box(structure,0,2.5,4.8,len,4,.13,wall);obstacle(room,0,4.8,len,.16);
    const leftEnd=dc-dw/2;
    box(structure,(-len/2+leftEnd)/2,2.5,-4.8,leftEnd+len/2,4,.13,wall);obstacle(room,(-len/2+leftEnd)/2,-4.8,leftEnd+len/2,.16);
    const rightStart=dc+dw/2;
    box(structure,(rightStart+len/2)/2,2.5,-4.8,len/2-rightStart,4,.13,wall);obstacle(room,(rightStart+len/2)/2,-4.8,len/2-rightStart,.16);
    box(structure,dc,.5+dh+(4-dh)/2,-4.8,dw,4-dh,.13,wall);
    // Side walls with glazed window openings at standing eye height.
    for(const s of [-1,1]){
      box(structure,s*len/2,1.05,0,.13,1.1,9.6,wall);box(structure,s*len/2,3.62,0,.13,1.76,9.6,wall);
      for(const zz of [-3.7,0,3.7])box(structure,s*len/2,2.17,zz,.13,1.14,zz===0?4.4:2.2,wall);
      for(const zz of [-2.55,2.55]){box(structure,s*len/2,2.16,zz,.045,1.08,.86,glass);for(const y of [1.59,2.73])box(structure,s*len/2,y,zz,.18,.055,1.0,steel);}
      obstacle(room,s*len/2,0,.18,9.6);
    }
    // Horizontal sandwich panel joints, matching the building photographs.
    for(let y=.95;y<4.45;y+=.45){box(structure,0,y,4.879,len,.013,.009,steel);box(structure,(-len/2+leftEnd)/2,y,-4.879,leftEnd+len/2,.013,.009,steel);}
    const roof=new THREE.Group();roof.name='Removable roof '+no;roof.userData.layer='roof';room.add(roof);
    const slope=Math.atan2(1.5,4.8),roofWidth=Math.hypot(4.8,1.5);
    for(const s of [-1,1]){const p=box(roof,0,5.25,s*2.4,len+.5,.13,roofWidth+.15,wall);p.rotation.x=s*slope;box(roof,0,4.52,s*4.91,len+.65,.2,.12,blue);}
    box(roof,0,6.03,0,len+.5,.12,.2,blue);
    // Gables are triangles, avoiding a false horizontal ceiling.
    for(const s of [-1,1]){const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute([s*len/2,4.5,-4.8,s*len/2,6,0,s*len/2,4.5,4.8],3));geo.computeVertexNormals();const gm=wall.clone();gm.side=THREE.DoubleSide;roof.add(new THREE.Mesh(geo,gm));}
    for(let x=-len/2+.25;x<len/2;x+=3.8){for(const s of [-1,1]){hbeam(structure,[x,.5,s*4.66],[x,4.5,s*4.66],.14,.16);hbeam(roof,[x,4.47,s*4.66],[x,5.87,0],.14,.16);hbeam(roof,[x,4.45,s*4.66],[x,4.45,0],.1,.12);beam(roof,[x,4.45,s*2.4],[x,5.87,0],.06,.06);}box(roof,x,4.36,0,.09,.09,9.3,steel);}
    for(let i=0;i<4;i++){const x=-len*.36+i*len*.24;cylinder(roof,x,6.14,0,.17,.32,steel);cylinder(roof,x,6.38,0,.25,.26,steel);cylinder(roof,x,6.54,0,.275,.035,steel);for(let j=0;j<12;j++){const a=j*Math.PI/6;box(roof,x+Math.cos(a)*.252,6.38,Math.sin(a)*.252,.016,.21,.018,dark);}}
    // Photo-derived wall exhaust cowls and conduits, positioned clear of door travel.
    for(const x of [-len*.30,-len*.12]){const hoodGeo=new THREE.CylinderGeometry(.36,.36,.75,24,1,false,0,Math.PI);hoodGeo.rotateZ(Math.PI/2);hoodGeo.rotateX(-Math.PI/2);const hood=new THREE.Mesh(hoodGeo,steel);hood.position.set(x,2.27,-4.94);hood.castShadow=true;structure.add(hood);box(structure,x,2.04,-5.08,.64,.025,.27,dark);box(structure,x,1.53,-4.94,.035,1.1,.035,steel);}
    const warning=label('전기실 · 관계자 외 출입금지',1.5,.15,'#f0e8c3','#922d28');warning.position.set(dc-2.45,1.65,-4.89);warning.rotation.y=Math.PI;structure.add(warning);
    // Entry rail, canopy and sliding metal door. Progress is supplied by the viewer.
    box(structure,dc-dw*.42,3.93,-5.03,dw*1.9,.09,.09,steel);
    box(structure,dc,4.05,-5.12,dw+.35,.08,.75,blue);
    const leaf=new THREE.Group();leaf.name='Sliding door '+no;leaf.position.set(dc,.5,-4.99);room.add(leaf);
    box(leaf,0,dh/2,0,dw+.1,dh,.075,wall);for(let y=.4;y<dh;y+=.4)box(leaf,0,y,-.044,dw,.013,.008,steel);box(leaf,-dw/2+.2,1.3,-.09,.035,.32,.06,dark);
    const door={mesh:leaf,closedX:dc,openX:dc-dw-.13,open:false,width:dw,height:dh,room,progress:0};
    door.setProgress=t=>{door.progress=Math.max(0,Math.min(1,t));leaf.position.x=door.closedX+(door.openX-door.closedX)*door.progress;};
    door.worldCenter=room.localToWorld(new THREE.Vector3(dc,1.5,-4.8));doors.push(door);
    // Concrete ramp: top at the interior floor, toe at grade, width matches opening.
    const rampGeo=new THREE.BufferGeometry();const rw=dw/2+.2,rz=-4.9,rz2=-8.9;
    rampGeo.setAttribute('position',new THREE.Float32BufferAttribute([dc-rw,.5,rz,dc+rw,.5,rz,dc+rw,.015,rz2,dc-rw,.5,rz,dc+rw,.015,rz2,dc-rw,.015,rz2],3));rampGeo.computeVertexNormals();const rm=concrete.clone();rm.side=THREE.DoubleSide;const ramp=new THREE.Mesh(rampGeo,rm);ramp.receiveShadow=true;structure.add(ramp);
    const trays=new THREE.Group();trays.name='Overhead ladder trays';trays.userData.layer='trays';room.add(trays);
    for(const z of [-2.1,2.1]){for(const edge of [-.32,.32])box(trays,0,3.37,z+edge,len-.75,.1,.04,steel);for(let x=-len/2+.4;x<len/2-.4;x+=.28)box(trays,x,3.34,z,.045,.025,.64,steel);for(let i=0;i<7;i++)box(trays,0,3.42,z-.23+i*.07,len-.85,.035,.035,dark);}
    for(let x=-len/2+1;x<len/2;x+=3){beam(trays,[x,3.3,-2.1],[x,5.05,-2.1],.024,.024);beam(trays,[x,3.3,2.1],[x,5.05,2.1],.024,.024);box(structure,x,3.82,0,1.22,.07,.17,steel);box(structure,x,3.775,0,1.15,.025,.105,lightMat);}
    // Green trench lids and yellow perimeter paint seen in the interior photos.
    for(const z of [-1.05,1.05]){box(room,0,.509,z,len-.65,.014,.95,plateMaterial,'equipment');for(let x=-len/2+.45;x<len/2-.3;x+=.8){box(room,x,.519,z,.008,.006,.94,dark,'equipment');box(room,x+.1,.525,z-.3,.13,.01,.012,steel,'equipment');}box(room,0,.522,z+(z<0?.45:-.45),len-.7,.006,.045,mat(0xc7ac3e),'equipment');}
    const fill=new THREE.PointLight(0xfff4da,85,19,2);fill.position.set(0,3.9,0);room.add(fill);
    const outside=label('SHINAN 2  /  ROOM '+no,2.5,.25,'#e7e9e6','#24455a');outside.position.set(0,3.82,-4.885);outside.rotation.y=Math.PI;structure.add(outside);
    const meta={id:no,no,group:room,length:len,width:9.6,rotation,floorHeight:.5,door,entry:room.localToWorld(new THREE.Vector3(dc,1.8,-9.8)),inside:room.localToWorld(new THREE.Vector3(dc,1.85,-2.8)),center:room.localToWorld(new THREE.Vector3(0,1.85,0)),ramp:{localX:dc,width:dw+.4,localZ0:-8.9,localZ1:-4.9,height:.5},source:'SA-E-10110/10120/15150; IMG_5916/5934/5940'};rooms.push(meta);
    return room;
  }
  const r1=makeRoom(1,20.5,9.14,145.9,-Math.PI/2),r2=makeRoom(2,18,195.7,107.67,0);
  for(const [i,id] of ['TR-B','TR-A','TR-1'].entries())cabinet(r1,-5.05+i*2,1.78,2,2.5,2.55,id,false,-1);
  for(const [i,id] of ['VCB-4','VCB-3','VCB-2','VCB-1','PT-1','MOF-1','LBS-1'].entries())cabinet(r1,.60+i*1.3,1.78,1.3,2.5,2.55,id,false,-1);
  for(const [i,id] of ['REC-1','LV-B','LV-A','MCCB-1'].entries())cabinet(r1,-4.85+i*.8,-2.81,.8,1.5,2.35,id,false,1);
  for(let i=0;i<10;i++)cabinet(r1,-1.65+i*.8,-2.65,.8,1.3,2.1,'INV-'+(i<5?'A':'B')+(i%5),true,1);
  for(const [i,id] of ['TR-E','TR-D','TR-C'].entries())cabinet(r2,-7+i*2,-1.75,2,2.5,2.55,id,false,1);
  for(const [i,id] of ['VCB-8','VCB-7','VCB-6','VCB-5'].entries())cabinet(r2,-1.35+i*1.3,-1.75,1.3,2.5,2.55,id,false,1);
  for(const [i,id] of ['REC-2','MCCB-2','LV-E','LV-D','LV-C'].entries())cabinet(r2,-7.6+i*.8,2.75,.8,1.5,2.35,id,false,-1);
  for(let i=0;i<15;i++)cabinet(r2,-3.6+i*.8,2.75,.8,1.3,2.1,'INV-'+['C','D','E'][Math.floor(i/5)]+(4-i%5),true,-1);
  // Room 1 control/storage annex: two real openings connect to the equipment aisle.
  const partition=mat(0xd3d7cc);
  for(const [z,d] of [[-4.45,.7],[-.4,5.4],[4,1.6]]){box(r1,-7.5,2.45,z,.12,3.9,d,partition);obstacle(r1,-7.5,z,.15,d);}
  box(r1,-8.875,2.45,1.5,2.75,3.9,.12,partition);obstacle(r1,-8.875,1.5,2.75,.12);
  box(r1,-8.8,1.22,-2.5,1.4,.07,.65,cream,'equipment');for(const x of [-9.35,-8.25])box(r1,x,.85,-2.5,.05,.7,.05,steel,'equipment');
  box(r1,-8.8,1.55,-2.66,.62,.38,.065,dark,'equipment');const monitor=label('SITE MONITOR',.55,.3,'#183135','#77958c');monitor.position.set(-8.8,1.55,-2.617);r1.add(monitor);
  group.updateMatrixWorld(true);
  // Bake static primitives into semantic-layer/material batches. Door leaves stay
  // independent so their animated transforms and collision boxes remain valid.
  for(const cabinet of equipment){const bounds=new THREE.Box3().setFromObject(cabinet);cabinet.userData.worldBounds={min:bounds.min.toArray(),max:bounds.max.toArray()};}
  let sourceMeshes=0,batchMeshes=0;
  for(const room of [r1,r2]){
    const inverse=room.matrixWorld.clone().invert(),buckets=new Map(),remove=[];
    room.traverse(obj=>{
      if(!obj.isMesh || Array.isArray(obj.material))return;
      let layer='structure',cursor=obj,isDoor=false;
      while(cursor&&cursor!==room){if(doors.some(d=>d.mesh===cursor)){isDoor=true;break;}if(layer==='structure'&&cursor.userData.layer)layer=cursor.userData.layer;cursor=cursor.parent;}
      if(isDoor)return;
      const key=layer+'|'+obj.material.uuid;let bucket=buckets.get(key);if(!bucket){bucket={layer,material:obj.material,geometries:[]};buckets.set(key,bucket);}
      let geometry=obj.geometry.clone();if(geometry.index){const expanded=geometry.toNonIndexed();geometry.dispose();geometry=expanded;}
      if(!geometry.attributes.normal)geometry.computeVertexNormals();if(!geometry.attributes.uv)geometry.setAttribute('uv',new THREE.BufferAttribute(new Float32Array(geometry.attributes.position.count*2),2));
      for(const key of Object.keys(geometry.attributes))if(!['position','normal','uv'].includes(key))geometry.deleteAttribute(key);
      geometry.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse,obj.matrixWorld));bucket.geometries.push(geometry);remove.push(obj);sourceMeshes++;
    });
    for(const bucket of buckets.values()){
      const geometry=mergeGeometries(bucket.geometries,false);if(!geometry)throw new Error('Room static geometry merge failed');
      const mesh=new THREE.Mesh(geometry,bucket.material);mesh.name='Batched '+bucket.layer;mesh.userData.layer=bucket.layer;mesh.castShadow=true;mesh.receiveShadow=true;room.add(mesh);batchMeshes++;
      bucket.geometries.forEach(g=>g.dispose());
    }
    remove.forEach(o=>{o.removeFromParent();o.geometry.dispose();});
  }
  group.userData.renderBatches={sourceMeshes,batchMeshes};
  return {group,doors,colliders,rooms,equipment,sourceNotes:['Equipment count: 51 cabinet segments, including 25 inverter segments.','Door hardware, window arrangement and fine materials are photo-derived approximations.','Cable tray routes are visual context; individual circuit connectivity is not certified.']};
}

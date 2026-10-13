import * as THREE from 'three';
import * as CANNON from 'cannon-es';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

// Footprints / equipment XY are drawing-derived. Surface finishes, door hardware,
// personnel-door clear width and ramp gradients are visualization assumptions.
export function addInteriors({scene,world,buildings,equipment,materials={}}){
  const buildingGroups=[],doors=[],rooms=[],bodies=[],contacts=[],roomLights=[];
  const mat=(color,roughness=.7,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
  const M={wall:materials.wall||mat(0xc9cecd),roof:materials.roof||mat(0xb86c48),steel:materials.steel||mat(0x65757c,.4,.6),floor:mat(0xadb5ae,.63),trim:mat(0x344f58,.4,.4),inside:mat(0xe1e3dc),dark:mat(0x172b31,.4),cabinet:mat(0xabbab8,.4,.3),inv:mat(0x51858b,.4,.25),yellow:mat(0xd3aa43),light:new THREE.MeshBasicMaterial({color:0xf4f7df}),glass:mat(0x7f9b9e,.25,.2)};
  const finish=document.createElement('canvas');finish.width=finish.height=256;const ctx=finish.getContext('2d');const pixels=ctx.createImageData(256,256);let seed=20261004;
  for(let i=0;i<pixels.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const v=174+(seed>>>27);pixels.data.set([v,v,v,255],i);}ctx.putImageData(pixels,0,0);
  const floorTexture=new THREE.CanvasTexture(finish);floorTexture.wrapS=floorTexture.wrapT=THREE.RepeatWrapping;floorTexture.repeat.set(12,6);floorTexture.colorSpace=THREE.SRGBColorSpace;M.floor.map=floorTexture;
  M.indicator=new THREE.MeshStandardMaterial({color:0x76b395,emissive:0x28613a,emissiveIntensity:.35,roughness:.3});
  for(const [name,m] of Object.entries(M))m.name=m.name||'Interior_'+name;
  function box(parent,x,y,z,w,h,d,m){const o=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),m);o.position.set(x,y,z);o.castShadow=o.receiveShadow=true;parent.add(o);return o;}
  function toWorld(room,p){return new THREE.Vector3(...p).applyAxisAngle(new THREE.Vector3(0,1,0),room.rotation).add(new THREE.Vector3(room.center[0],0,-room.center[1]));}
  function toLocal(room,p){return new THREE.Vector3(p.x-room.center[0],p.y,p.z+room.center[1]).applyAxisAngle(new THREE.Vector3(0,1,0),-room.rotation);}
  function solid(room,p,size,angle=0){const v=toWorld(room,p),b=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(size[0]/2,size[1]/2,size[2]/2))});b.position.set(v.x,v.y,v.z);b.quaternion.setFromAxisAngle(new CANNON.Vec3(0,1,0),room.rotation+angle);world.addBody(b);bodies.push(b);return b;}
  function label(parent,text,x,y,z,w=1.4,rotation=0){const c=document.createElement('canvas');c.width=512;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle='#172e36';ctx.fillRect(0,0,512,128);ctx.fillStyle='#eff2e8';ctx.font='bold 48px Arial';ctx.textAlign='center';ctx.fillText(text,256,83);const tx=new THREE.CanvasTexture(c);tx.colorSpace=THREE.SRGBColorSpace;const o=new THREE.Mesh(new THREE.PlaneGeometry(w,w/4),new THREE.MeshBasicMaterial({map:tx}));o.position.set(x,y,z);o.rotation.y=rotation;parent.add(o);return o;}
  function wall(room,g,p,size){box(g,...p,...size,M.wall);solid(room,p,size);}
  function monitorRoom(room,g){
    // 3SA-E-10110: monitoring room in the north-west corner, two desks,
    // communication rack and wall monitor. Small furniture details are inferred.
    wall(room,g,[-3.25,2.4,-3.45],[.1,3.8,2.6]);
    wall(room,g,[-6.015,2.4,-2.15],[5.43,3.8,.1]);
    wall(room,g,[-9.45,3.6,-2.15],[1.3,1.4,.1]);
    const pivot=new THREE.Group();pivot.userData.door=true;pivot.position.set(-10.1,.5,-2.15);pivot.rotation.y=Math.PI/2;g.add(pivot);
    const leaf=box(pivot,0,1.15,.65,.06,2.3,1.3,M.cabinet);box(pivot,.065,1.15,1.13,.07,.05,.18,M.steel);
    const d={id:room.id+'-monitor',room,side:1,z:-2.15,anchor:[-9.45,-2.15],axis:'z',closedAngle:Math.PI/2,width:1.3,pivot,leaf,angle:0,target:0,blocked:false};d.body=solid(room,[-9.45,1.65,-2.15],[.06,2.3,1.3],Math.PI/2);pivot.name=d.id;doors.push(d);
    label(g,'CONTROL ROOM',-6.3,3.25,-2.08,2);
    for(const x of [-6.8,-5.2]){box(g,x,1.23,-2.65,1.5,.08,.7,M.cabinet);solid(room,[x,.87,-2.65],[1.5,.75,.7]);for(const dx of [-.65,.65])box(g,x+dx,.86,-2.65,.05,.7,.56,M.steel);box(g,x,1.55,-2.72,.45,.3,.04,M.dark);box(g,x,1.32,-2.72,.04,.15,.08,M.steel);box(g,x,.98,-3.48,.48,.09,.48,M.dark);box(g,x,1.25,-3.68,.48,.55,.08,M.dark);solid(room,[x,.9,-3.5],[.5,.8,.5]);}
    for(const x of [-6.8,-5.2])for(const dx of [-.19,.19])for(const dz of [-.19,.19])box(g,x+dx,.7,-3.48+dz,.035,.47,.035,M.steel);
    box(g,-3.8,1.4,-2.75,.6,1.8,.8,M.dark);solid(room,[-3.8,1.4,-2.75],[.6,1.8,.8]);
    box(g,-3.32,2.5,-3.55,.035,.84,1.5,M.dark);box(g,-3.35,2.5,-3.55,.018,.72,1.36,M.glass);
    box(g,-5.65,3.45,-4.58,1,.36,.24,M.cabinet);for(let i=0;i<4;i++)box(g,-5.65,3.32+i*.035,-4.447,.82,.012,.015,M.dark);
    label(g,'AIR CON',-5.65,3.8,-4.43,.85);
    box(g,-9.9,3.3,-1.91,.12,.12,.18,M.trim);const camera=box(g,-9.78,3.28,-1.86,.2,.14,.32,M.cabinet);camera.rotation.y=-.6;
    label(g,'CAMERA 1',-9.5,3.6,-1.82,.72);
    for(const [id,x,z] of [['LTG100',-9.83,-4.55],['ETT-J100',-3.4,-2.45],['ETT-E100',9.8,4.57]]){box(g,x,.8,z,.25,.34,.12,M.trim);label(g,id,x,1.1,z+.07,.6);}
  }
  function createDoor(room,g,side,z){const w=1.22,h=2.3,x=side*room.length/2;
    const pivot=new THREE.Group();pivot.userData.door=true;pivot.position.set(x,.5,z-w/2);g.add(pivot);
    const leaf=box(pivot,0,h/2,w/2,.075,h,w,M.trim);
    for(const s of [-1,1]){box(pivot,s*.045,h/2,w/2,.015,h-.18,w-.16,M.cabinet);box(pivot,s*.09,1.1,w-.17,.1,.045,.2,M.steel);}
    const door={id:room.id+'-'+(side>0?'east':'west'),room,side,z,width:w,pivot,leaf,angle:0,target:0,blocked:false};
    door.body=solid(room,[x,.5+h/2,z],[.075,h,w]);pivot.name=door.id;doors.push(door);
    for(const dz of [-w/2-.055,w/2+.055])box(g,x,1.68,z+dz,.22,2.4,.09,M.trim);
    box(g,x,2.88,z,.22,.12,w+.2,M.trim);
    // Gentle ramp avoids the full-building slab obstacle; thin floor collider
    // continues through the opening. Sloped box is a real collision surface.
    const ramp=box(g,x+side*1.55,.225,z,3.1,.1,1.55,M.floor);ramp.rotation.z=-side*Math.atan(.5/3.1);
    const rb=solid(room,[x+side*1.55,.225,z],[3.1,.1,1.55]);const q=new CANNON.Quaternion();q.setFromAxisAngle(new CANNON.Vec3(0,0,1),-side*Math.atan(.5/3.1));rb.quaternion=rb.quaternion.mult(q);
    label(g,'EXIT',x-side*.13,3.1,z,.75,side>0?-Math.PI/2:Math.PI/2);
    return door;
  }
  for(const room of buildings){const g=new THREE.Group();g.name=room.id+' | walkable interior';g.position.set(room.center[0],0,-room.center[1]);g.rotation.y=room.rotation;scene.add(g);buildingGroups.push(g);rooms.push(room);const w=room.length,d=room.width,e=room.eave_z,r=room.ridge_z;
    box(g,0,.23,0,w+.15,.46,d+.15,M.floor);solid(room,[0,.23,0],[w+.15,.46,d+.15]);
    for(const s of [-1,1]){wall(room,g,[0,2.5,s*d/2],[w,4,.16]);const z=s*3.15,lo=z-.61,hi=z+.61;
      wall(room,g,[s*w/2,2.5,(-d/2+lo)/2],[.16,4,lo+d/2]);wall(room,g,[s*w/2,2.5,(hi+d/2)/2],[.16,4,d/2-hi]);wall(room,g,[s*w/2,3.7,z],[.16,1.6,1.22]);createDoor(room,g,s,z);
      for(let y=.9;y<e;y+=.34)box(g,0,y,s*(d/2+.09),w,.014,.014,M.steel);
      for(let k=0;k<5;k++)for(const y of [1.75,3.45]){if(s<0&&y===1.75&&k===4)continue;const x=-8+k*4;box(g,x,y,s*(d/2+.1),1.6,.9,.09,M.trim);box(g,x,y,s*(d/2+.16),1.43,.73,.025,M.glass);box(g,x,y,s*(d/2-.1),1.43,.73,.025,M.glass);}
      const a=Math.atan2(r-e,d/2),len=Math.hypot(d/2+.25,r-e);const roof=box(g,0,(e+r)/2+.02,s*(d/4+.08),w+.55,.13,len,M.roof);roof.rotation.x=s*a;
      for(let x=-w/2;x<=w/2;x+=.4){const seam=box(g,x,(e+r)/2+.1,s*(d/4+.08),.018,.024,len,M.roof);seam.rotation.x=s*a;}
    }
    const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute([-w/2,e,-d/2,-w/2,e,d/2,-w/2,r,0,w/2,e,d/2,w/2,e,-d/2,w/2,r,0],3));geo.computeVertexNormals();const gm=M.wall.clone();gm.side=THREE.DoubleSide;g.add(new THREE.Mesh(geo,gm));
    box(g,0,4.43,0,w-.2,.1,d-.2,M.inside);
    for(const x of [-8,-4,0,4,8]){for(const z of [-2,2]){box(g,x,4.34,z,1.25,.07,.25,M.trim);box(g,x,4.29,z,1.16,.025,.18,M.light);}for(const z of [-d/2+.2,d/2-.2])box(g,x,2.5,z,.13,4,.13,M.steel);}
    for(const x of [-6,0,6]){const light=new THREE.PointLight(0xfff4dd,16,11,1.5);light.position.set(x,3.7,0);g.add(light);roomLights.push({room,light});}
    if(room.id==='S3-ER1')monitorRoom(room,g);
    // Flush trench covers follow the equipment aisles; route is illustrative.
    for(const z of [-1.1,3.8]){box(g,0,.469,z,w-1,.015,.42,M.steel);for(let x=-9.4;x<9.5;x+=.5)box(g,x,.48,z,.012,.012,.42,M.dark);}
    for(const z of [-.8,.8])box(g,0,.477,z,w-1,.008,.035,M.yellow);
    // Closed equipment delivery doors preserve the drawing-led end elevations.
    for(const side of [-1,1]){const x=side*(w/2+.1);box(g,x,1.9,0,.08,2.8,3.35,M.trim);box(g,x+side*.06,1.9,0,.04,2.65,3.2,M.cabinet);for(let z=-1.4;z<1.6;z+=.24)box(g,x+side*.09,1.9,z,.02,2.6,.018,M.steel);box(g,x+side*.55,3.45,0,1.3,.1,3.8,M.roof);}
    for(const x of [-7.5,-2.5,2.5,7.5]){const vent=new THREE.Mesh(new THREE.CylinderGeometry(.3,.23,.45,16),M.steel);vent.position.set(x,r+.25,0);g.add(vent);const cap=new THREE.Mesh(new THREE.SphereGeometry(.3,16,8,0,Math.PI*2,0,Math.PI/2),M.steel);cap.position.set(x,r+.475,0);g.add(cap);}
    for(const z of [-d/2-.15,d/2+.15]){box(g,0,e-.05,z,w+.4,.1,.12,M.steel);for(const x of [-w/2+.15,w/2-.15])box(g,x,2.35,z,.075,4.2,.075,M.steel);}
    const es=equipment.filter(eq=>eq.building===room.id);
    const contactCanvas=document.createElement('canvas');contactCanvas.width=contactCanvas.height=128;const contactCtx=contactCanvas.getContext('2d');
    for(let j=0;j<24;j++){contactCtx.fillStyle='rgba(15,24,25,.024)';contactCtx.fillRect(j,j,128-2*j,128-2*j);}
    const contactMap=new THREE.CanvasTexture(contactCanvas),contactMat=new THREE.MeshBasicMaterial({map:contactMap,transparent:true,depthWrite:false,opacity:.6});
    const contactGeo=new THREE.PlaneGeometry(1,1);contactGeo.rotateX(-Math.PI/2);const contact=new THREE.InstancedMesh(contactGeo,contactMat,es.length),stamp=new THREE.Object3D();
    es.forEach((eq,i)=>{const p=toLocal(room,{x:eq.pos[0],y:eq.pos[2],z:-eq.pos[1]});stamp.position.set(p.x,.478,p.z);stamp.rotation.y=eq.rotation-room.rotation;stamp.scale.set(eq.size[0]+.65,1,eq.size[1]+.65);stamp.updateMatrix();contact.setMatrixAt(i,stamp.matrix);});contact.instanceMatrix.needsUpdate=true;contact.name=room.id+'/inferred_contact_shading';g.add(contact);

    for(const eq of es){const p=toLocal(room,{x:eq.pos[0],y:eq.pos[2],z:-eq.pos[1]}),eg=new THREE.Group();eg.name=eq.id;eg.position.copy(p);eg.rotation.y=eq.rotation-room.rotation;g.add(eg);const [cw,cd,ch]=eq.size;const inv=eq.id.startsWith('INV');box(eg,0,0,0,cw,ch,cd,inv?M.inv:M.cabinet);box(eg,0,-ch/2+.045,0,cw+.015,.09,cd+.015,M.dark);
      solid(room,[p.x,p.y,p.z],[cw,ch,cd],eq.rotation-room.rotation);
      for(const side of [-1,1]){const face=side*(cd/2+.008);box(eg,0,0,face,cw-.08,ch-.1,.018,M.cabinet);box(eg,0,0,face+side*.016,.009,ch-.1,.014,M.steel);box(eg,cw*.34,.02,face+side*.025,.035,.3,.04,M.dark);if(side===(p.z>0?-1:1)){box(eg,0,ch*.2,face+side*.022,Math.min(.32,cw*.42),.2,.025,M.dark);box(eg,0,ch*.2,face+side*.037,Math.min(.24,cw*.34),.13,.009,M.glass);for(let k=0;k<3;k++)box(eg,-.09+k*.09,ch*.08,face+side*.026,.035,.035,.02,k===0?M.indicator:M.dark);}for(let k=0;k<5;k++)box(eg,0,-ch*.28+k*.055,face+side*.021,cw*.64,.015,.021,M.dark);label(eg,eq.id,0,ch*.38,face+side*.035,Math.min(cw*.8,1.25),side<0?Math.PI:0);}
    }
    // Batch static architectural surfaces. Doors, cabinet labels and lights remain
    // separate objects so interaction and text stay correct.
    g.updateMatrixWorld(true);const inverse=g.matrixWorld.clone().invert(),staticMeshes=[];
    function collect(parent){for(const c of parent.children){if(c.userData.door)continue;if(c.isMesh&&!c.material.map)staticMeshes.push(c);else if(c.isGroup)collect(c);}}collect(g);
    const buckets=new Map();for(const c of staticMeshes){const geom=c.geometry.clone().applyMatrix4(inverse.clone().multiply(c.matrixWorld));if(!buckets.has(c.material))buckets.set(c.material,[]);buckets.get(c.material).push(geom.index?geom.toNonIndexed():geom);c.removeFromParent();}for(const [m,gs]of buckets){const mesh=new THREE.Mesh(mergeGeometries(gs),m);mesh.name=room.id+'/'+m.name;mesh.castShadow=mesh.receiveShadow=true;g.add(mesh);}
  }
  function distance(door,pos){const p=toLocal(door.room,pos);return Math.hypot(p.x-(door.anchor?.[0]??door.side*door.room.length/2),p.z-door.z);}
  function nearestDoor(pos,camera){const candidates=doors.filter(d=>buildingGroups[rooms.indexOf(d.room)].visible).map(d=>({door:d,distance:distance(d,pos)}));if(camera){const forward=camera.getWorldDirection(new THREE.Vector3());for(const c of candidates){const d=c.door,center=toWorld(d.room,[d.anchor?.[0]??d.side*d.room.length/2,1.7,d.z]);c.facing=center.sub(camera.position).normalize().dot(forward);}return candidates.filter(c=>c.facing>.3).sort((a,b)=>a.distance-b.distance)[0];}return candidates.sort((a,b)=>a.distance-b.distance)[0];}
  function toggle(d,pos){if(distance(d,pos)>3.4)return {ok:false,reason:'too_far'};const opening=d.target===0;if(!opening&&distance(d,pos)<1.5){d.blocked=true;return{ok:false,reason:'doorway_occupied',id:d.id};}const p=toLocal(d.room,pos);d.target=opening?(d.axis==='z'?(p.z>=d.z?1:-1):(p.x-d.side*d.room.length/2>=0?-1:1))*Math.PI*.52:0;d.blocked=false;return{ok:true,id:d.id,opening};}
  function update(dt,pos,viewPosition=pos){for(const {room,light} of roomLights)light.visible=Math.hypot(viewPosition.x-room.center[0],viewPosition.z+room.center[1])<22;for(const d of doors){if(d.target===0&&Math.abs(d.angle)>.02&&distance(d,pos)<1.5){d.blocked=true;continue;}d.blocked=false;const delta=d.target-d.angle;d.angle+=Math.sign(delta)*Math.min(Math.abs(delta),dt*1.5);d.pivot.rotation.y=(d.closedAngle||0)+d.angle;const local=new THREE.Vector3(0,1.15,d.width/2).applyAxisAngle(new THREE.Vector3(0,1,0),d.pivot.rotation.y).add(d.pivot.position),p=toWorld(d.room,local.toArray());d.body.position.set(p.x,p.y,p.z);d.body.quaternion.setFromAxisAngle(new CANNON.Vec3(0,1,0),d.room.rotation+d.pivot.rotation.y);d.body.aabbNeedsUpdate=true;}}
  function interact(camera,pos){const n=nearestDoor(pos,camera);if(!n||n.distance>3.4)return {ok:false,reason:'too_far'};return toggle(n.door,pos);}
  function entryPose(index=0){const room=rooms[index],door=doors.find(d=>d.room===room&&d.side>0&&!d.anchor);return {position:toWorld(room,[room.length/2+3.8,1.7,door.z]),target:toWorld(room,[room.length/2-2,1.7,door.z]),door:door.id};}
  function testPhysics(player){
    const saved={p:player.position.clone(),v:player.velocity.clone(),sleep:player.sleepState,doors:doors.map(d=>({angle:d.angle,target:d.target}))},results=[];
    function place(room,p){const v=toWorld(room,p);player.position.set(v.x,v.y,v.z);player.velocity.setZero();player.wakeUp();}
    function drive(room,v,frames){const direction=new THREE.Vector3(...v).applyAxisAngle(new THREE.Vector3(0,1,0),room.rotation);for(let i=0;i<frames;i++){update(1/60,player.position);player.velocity.x=direction.x;player.velocity.z=direction.z;world.step(1/60);}}
    try{for(const d of doors){
      d.angle=d.target=0;const center=d.anchor||[d.side*d.room.length/2,d.z],n=d.axis==='z'?[0,1]:[d.side,0];
      const signed=()=>{const p=toLocal(d.room,player.position);return(p.x-center[0])*n[0]+(p.z-center[1])*n[1];};
      place(d.room,[center[0]+n[0]*2,.9,center[1]+n[1]*2]);drive(d.room,[-n[0]*2.2,0,-n[1]*2.2],140);const closed=signed();
      const open=toggle(d,player.position);drive(d.room,[0,0,0],90);drive(d.room,[-n[0]*2.2,0,-n[1]*2.2],60);const inside=signed();
      place(d.room,[center[0]-n[0]*.6,.9,center[1]-n[1]*.6]);const occupied=toggle(d,player.position);
      place(d.room,[center[0]-n[0]*2,.9,center[1]-n[1]*2]);const close=toggle(d,player.position);drive(d.room,[0,0,0],90);drive(d.room,[n[0]*2.2,0,n[1]*2.2],90);const closedInside=signed();
      const reopen=toggle(d,player.position);drive(d.room,[0,0,0],90);drive(d.room,[n[0]*2.2,0,n[1]*2.2],60);const outside=signed();
      results.push({door:d.id,closed,inside,closedInside,outside,closedBlocked:closed>.3,entered:open.ok&&inside<-.45,occupiedProtected:occupied.reason==='doorway_occupied',insideClosedBlocked:close.ok&&closedInside<-.3,exited:reopen.ok&&outside>.45});
    }
    for(const room of rooms){place(room,[0,.9,room.width/2-1]);drive(room,[0,0,2.2],120);const p=toLocal(room,player.position);results.push({wall:room.id,local:p.toArray(),blocked:p.z<room.width/2-.3});
      const eq=equipment.find(e=>e.building===room.id),ep=toLocal(room,{x:eq.pos[0],y:eq.pos[2],z:-eq.pos[1]}),front=ep.z-eq.size[1]/2;
      place(room,[ep.x,.9,front-1]);drive(room,[0,0,2.2],120);const stopped=toLocal(room,player.position);results.push({equipment:eq.id,front,stopped:stopped.z,blocked:stopped.z<front-.3});
    }
    }finally{doors.forEach((d,i)=>Object.assign(d,saved.doors[i]));update(0,{x:1e6,y:0,z:1e6});player.position.copy(saved.p);player.velocity.copy(saved.v);if(saved.sleep===CANNON.Body.SLEEPING)player.sleep();}
    return results;
  }
  const inspect=()=>({rooms:rooms.length,equipment:equipment.filter(e=>e.building).length,doors:doors.map(d=>({id:d.id,angle:d.angle,target:d.target,blocked:d.blocked,position:toWorld(d.room,[d.anchor?.[0]??d.side*d.room.length/2,1.7,d.z]).toArray()})),assumed:['surface finishes','door hardware and clear width','ramps','trench paths','lighting']});
  function clickDoor(ray,pos){for(const d of doors){if(!buildingGroups[rooms.indexOf(d.room)].visible||distance(d,pos)>3.4)continue;if(ray.intersectObject(d.pivot,true).length){toggle(d,pos);return true;}}return false;}
  return {buildingGroups,contacts,bodies,rooms,doors,update,interact,clickDoor,nearestDoor,entryPose,inspect,toLocal,toWorld,testPhysics,toggleDoor:(id,pos)=>{const d=doors.find(d=>d.id===id);return d?toggle(d,pos):{ok:false};}};
}

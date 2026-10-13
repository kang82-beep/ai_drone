import * as THREE from 'three';
import {Line2} from 'three/addons/lines/Line2.js';
import {LineGeometry} from 'three/addons/lines/LineGeometry.js';
import {LineMaterial} from 'three/addons/lines/LineMaterial.js';
import DATA from './cable_data.js';

export function addCables(scene){
  const definitions=[['series','모듈 직렬 배선',0xe8b15c],['dc_branch','DC 스트링 인출 · P/N',0xed915c],['dc_feeder','DC 접속반–인버터 · P/N',0xb395e4],['ac_schematic','AC·고압 연결 · 개략',0xefcf70],['trays','트레이 · 전선관 도면선',0x91a4aa],['equipment','접속반 · 전기설비',0x477986]];
  const groups={},bases={},selected={},materials={};
  for(const [id,label,color] of definitions){
    const group=new THREE.Group();group.name='Electrical_'+id;group.visible=false;scene.add(group);groups[id]=group;
    const selection=new THREE.Group();group.add(selection);selected[id]=selection;
    materials[id]=new THREE.MeshStandardMaterial({color,roughness:.58,metalness:.18});
  }
  const shape=new THREE.CylinderGeometry(1,1,1,6),dummy=new THREE.Object3D(),up=new THREE.Vector3(0,1,0);
  const point=p=>new THREE.Vector3(p[0],p[2],-p[1]);
  function wires(records,kind,radius=.055){
    const segments=[];
    for(const r of records)for(let i=1;i<r.points.length;i++){
      const a=point(r.points[i-1]),b=point(r.points[i]);if(a.distanceTo(b)>.0001)segments.push({a,b,negative:r.id?.endsWith(' N')});
    }
    const mesh=new THREE.InstancedMesh(shape,materials[kind],segments.length);
    segments.forEach(({a,b,negative},i)=>{dummy.position.copy(a).add(b).multiplyScalar(.5);dummy.quaternion.setFromUnitVectors(up,b.clone().sub(a).normalize());dummy.scale.set(radius,a.distanceTo(b),radius);dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);mesh.setColorAt(i,new THREE.Color(negative?0x48bfd5:definitions.find(d=>d[0]===kind)[2]));});
    mesh.instanceMatrix.needsUpdate=true;mesh.computeBoundingSphere();return mesh;
  }
  bases.series=wires(DATA.series,'series',.035);
  for(const kind of ['dc_branch','dc_feeder','ac_schematic'])bases[kind]=wires(DATA.paths.filter(p=>p.kind===kind),kind,kind==='dc_branch'?.045:.065);
  bases.trays=wires(DATA.tray_edges.map(e=>({points:e.points.map(p=>[...p,.43])})),'trays',.035);
  const boxes=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),materials.equipment,DATA.equipment.length);
  DATA.equipment.forEach((e,i)=>{dummy.position.copy(point(e.pos));dummy.rotation.set(0,e.rotation,0);dummy.scale.set(e.size[0],e.size[2],e.size[1]);dummy.updateMatrix();boxes.setMatrixAt(i,dummy.matrix);boxes.setColorAt(i,new THREE.Color(e.id.startsWith('JB')?0xd7ddd8:e.id.startsWith('INV')?0x568fa1:0x83969b));});
  boxes.computeBoundingSphere();bases.equipment=boxes;
  for(const [id,mesh] of Object.entries(bases))groups[id].add(mesh);
  const schedule=new Map(DATA.schedule.map(c=>[c.id,c])),pathMap=new Map(DATA.paths.map(p=>[p.id,p]));
  let currentString=null,currentCable=null,focus=false,highlighted=[],focusPoints=[];
  function clear(){for(const g of Object.values(selected)){for(const child of [...g.children]){g.remove(child);if(child.isInstancedMesh)child.dispose();else{child.geometry?.dispose();child.material?.map?.dispose();child.material?.dispose();}}}highlighted=[];focusPoints=[];}
  function mark(records,kind){for(const r of records){
    const geo=new LineGeometry();geo.setPositions(r.points.flatMap(p=>[p[0],p[2],-p[1]]));
    const mat=new LineMaterial({color:r.id.endsWith(' N')?0x48d9f2:kind==='series'?0xffd581:0xff9561,linewidth:3,depthTest:false,depthWrite:false});mat.resolution.set(innerWidth,innerHeight);
    const line=new Line2(geo,mat);line.renderOrder=10;selected[kind].add(line);highlighted.push(r.id);focusPoints.push(...r.points);
  }}
  function label(id){let e=DATA.equipment.find(e=>e.id===id);if(!e){const index=DATA.strings.findIndex(s=>s.id===id);if(index>=0)e={pos:DATA.series[index].points[0]};}if(!e)return;
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=64;const ctx=canvas.getContext('2d');ctx.fillStyle='#14242def';ctx.fillRect(0,0,256,64);ctx.fillStyle='#f5dfab';ctx.font='bold 30px Segoe UI';ctx.textAlign='center';ctx.fillText(id,128,43);
    const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),depthTest:false,depthWrite:false}));sprite.position.copy(point(e.pos)).y+=3;sprite.scale.set(12,3,1);sprite.renderOrder=11;selected.equipment.add(sprite);
  }
  addEventListener('resize',()=>{for(const g of Object.values(selected))for(const child of g.children)child.material?.resolution?.set(innerWidth,innerHeight);});
  function selectString(index){clear();currentString=DATA.strings[index];currentCable=null;if(!currentString)return null;
    mark([DATA.series[index]],'series');
    mark(DATA.paths.filter(p=>p.kind==='dc_branch'&&p.from===currentString.id),'dc_branch');
    mark(DATA.paths.filter(p=>p.kind==='dc_feeder'&&p.from===currentString.jb),'dc_feeder');
    label(currentString.id);label(currentString.jb);label(currentString.inverter);
    return currentString;
  }
  function selectCable(id){clear();currentCable=schedule.get(id)||null;currentString=null;const p=pathMap.get(id);if(p){mark([p],p.kind);label(p.from);label(p.to);}return {cable:currentCable,path:p};}
  function setFocus(value){focus=value;for(const k of ['series','dc_branch','dc_feeder','ac_schematic'])bases[k].visible=!focus;}
  return {entries:definitions.map(([id,label])=>({id:'cable_'+id,label,section:'전기 연결',objects:[groups[id]]})),data:DATA,groups,
    forModule:index=>DATA.strings[DATA.module_to_string[index]],selectModule:index=>selectString(DATA.module_to_string[index]),selectString,selectCable,setFocus,
    schedule,pathMap,focusPoints:()=>focusPoints,inspect:()=>({strings:DATA.strings.length,modules:DATA.module_to_string.length,equipment:DATA.equipment.length,cables:DATA.paths.length,focus,selectedString:currentString?.id||null,selectedCable:currentCable?.id||null,highlighted,visible:Object.fromEntries(Object.entries(groups).map(([id,g])=>[id,g.visible]))})};
}

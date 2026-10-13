import * as THREE from 'three';
import secondaryData from '../results/shinan2_cables/secondary_systems.json';

// Source membership is kept separate from physical cable routing and earth continuity.
export function addSecondaryCircuits({node,link,nodes,groups,wp}){
  const boxes=[
    ['L-E1',1,[-6.7,1.55,-4.55],[.6,.8,.2],'lighting',62],
    ['L-E2',2,[-8.75,1.45,.2],[.2,.6,.6],'lighting',62],
    ['ETT-P1',1,[-7.2,1.6,4.55],[.6,1.2,.15],'ground',50],
    ['ETT-P2',2,[-5.1,1.6,-4.55],[.6,1.2,.15],'ground',50],
    ['ETT-J1',1,[-7.5,1.175,1.9],[.15,.35,.4],'ground',50],
    ['ETT-J2',2,[-8.75,1.175,4],[.15,.35,.4],'ground',50]
  ];
  const material=new THREE.MeshStandardMaterial({color:'#a7b0a6',roughness:.62,metalness:.4});
  for(const [id,room,local,size,layer,page] of boxes){
    const position=wp(room,local);
    node(id,position,layer,{page,room,secondary:true,positionStatus:'Approximate placement read from room plans; box dimensions from source detail; terminal positions not asserted.',sourceSchedule:secondaryData.panelSchedules[id]||secondaryData.groundTerminalBoxes[id.startsWith('ETT-P')?'ETT-P1/P2':'ETT-J1/J2']});
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),material);mesh.position.copy(position);mesh.rotation.y=room===1?-Math.PI/2:0;mesh.name=id;mesh.castShadow=true;mesh.userData={node:id,page,secondary:true,positionStatus:'approximate'};groups[layer]?.add(mesh);
  }
  function layerFor(system){return system==='lightning'?'lightning':system.includes('earth')?'ground':'lighting';}
  const memberships=new Set();
  function ensure(id,record){if(nodes.has(id))return;node(id,null,layerFor(record.system),{secondary:true,page:record.page,positionStatus:'Logical drawing endpoint; no position asserted.',system:record.system});}
  for(const record of secondaryData.circuits){
    ensure(record.source,record);ensure(record.target,record);
    // A named panel circuit is a logical child, not an additional physical cable.
    if(/^L-E[12]:/.test(record.source)&&!memberships.has(record.source)){
      const parent=record.source.split(':')[0];memberships.add(record.source);
      link(parent,record.source,'lighting',null,{id:'SECONDARY-MEMBER-'+record.source,secondary:true,page:62,system:'panel_circuit_membership',routeStatus:'logical panel membership; internal conductor/terminal not specified'});
    }
    link(record.source,record.target,record.system,null,{...record,cable:record.cable?{notation:record.cable}:null,secondary:true,routeStatus:record.routeStatus||'logical membership only; actual route not extracted'});
    const target=nodes.get(record.target);target.secondaryCircuits??=[];target.secondaryCircuits.push(record.id);
  }
  for(const room of [1,2]){
    const n=nodes.get(`ROOM${room}-LIGHTING`);if(n)n.sourceSchedule=secondaryData.lighting[room];
  }
  // No duplicate lights or fabricated electrode positions: existing room fixtures remain.
  return {circuits:secondaryData.circuits.length,lightingFixtures:43,outlets:13,logicalMemberships:memberships.size,sourcePages:[46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63],status:'Source-verified secondary circuit membership; most physical routes and terminal positions unassigned.',limitations:secondaryData.limitations};
}

// PDF64/65: positions are scan-registered, not surveyed. Post height 4m is drawn.
export function addSurveillance({node,link,nodes,groups,wp}){
  const group=groups.cctv,metal=new THREE.MeshStandardMaterial({color:0xa5b3b8,metalness:.65,roughness:.4});
  node('VIDEO-SERVER',wp(1,[-8.5,1.4,-2.7]),'cctv',{page:64,positionStatus:'control room reference point; equipment placement approximate'});
  const anchors=[[1,954,195],[2,487,323],[3,666,915],[4,1263,1012],[5,1437,638],[6,1490,96],[7,523,559]],scale=1017/344.32;
  for(const [id,px,py] of anchors){const x=(px-500)/scale,z=(py-1001)/scale,y=id===7?3:3.1;const n=node('CAMERA-'+id,[x,y,z],'cctv',{page:65,positionStatus:'scan-derived XY; camera mounting height approximate',cameraType:id===7?'fixed':'PTZ',poleHeight:id===7?null:4});
    if(id!==7){const pole=new THREE.Mesh(new THREE.CylinderGeometry(.075,.075,4,12),metal);pole.position.set(x,2,z);pole.castShadow=true;group.add(pole);}
    const body=new THREE.Mesh(id===7?new THREE.BoxGeometry(.3,.17,.35):new THREE.SphereGeometry(.15,12,8),metal);body.position.set(x,y,z);body.name=n.id;group.add(body);
    const server=nodes.get('VIDEO-SERVER').pos;
    link(n.id,'VIDEO-SERVER','cctv',[[x,y,z],[x,.5,z],[server[0],.5,z],[server[0],.5,server[2]],server],{page:65,cable:{notation:'7C-HFBT · ON THE FENCE (p65)'},routeStatus:'schematic connection; full fence-following route not established'});
  }
  node('KT-MODEM',wp(1,[-8.8,1.6,-2.7]),'cctv');node('NETWORK-ROUTER',wp(1,[-8.8,1.5,-2.7]),'cctv');node('HUB-24PORT',wp(1,[-8.8,1.4,-2.7]),'cctv');
  for(const [a,b] of [['KT-MODEM','NETWORK-ROUTER'],['NETWORK-ROUTER','HUB-24PORT'],['HUB-24PORT','VIDEO-SERVER'],['HUB-24PORT','COMM-CONVERTER']])link(a,b,'cctv',null,{page:64,cable:{notation:'TCP/IP · UTP CAT6 (p64)'},routeStatus:'schematic network connection; terminal pinout not specified'});
  return {cameras:7,cameraSourcePages:[64,65],cameraGeometry:'source positions; simplified housings'};
}

export function addGridManholes({edges,link,node}){
  const index=edges.findIndex(e=>e.source==='POLE-201'&&e.target==='POLE-163');if(index<0)return;
  const original=edges.splice(index,1)[0],ids=['POLE-201','MH07','MH06','MH05','MH04','MH03','MH02','MH01','POLE-163'];
  const lengths=[109.5,140.8,204.5,187.7,209.5,217,145,106];
  for(let i=1;i<ids.length;i++){if(ids[i].startsWith('MH'))node(ids[i],null,'grid_manhole',{page:66,positionStatus:'no world position asserted'});link(ids[i-1],ids[i],'grid_HV',null,{page:66,cable:original.cable,drawingLengthM:lengths[i-1],routeStatus:'block diagram only; geographic route not registered',note:i===1?'Drawing also shows alternate 74.1m in parentheses':undefined});}
  return {manholes:7,drawingTotalM:1320,geographicRoute:'not registered'};
}

import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {Sky} from 'three/addons/objects/Sky.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import * as CANNON from 'cannon-es';
import {WalkBroadphase} from './walk_physics.js';
import {addEnvironment} from './environment.js';
import {createLayers} from './layers.js';
import {addCables} from './cables.js';
import {addInteriors} from './interiors.js';
import {createSolarControls} from './solar.js';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {createInspection} from './inspection.js';
import {mapCandidate} from './map_registration.js';
import {createConsoleLink} from './console_link.js';

const $=id=>document.getElementById(id), params=new URLSearchParams(location.search);
if(params.has('clean'))document.body.classList.add('clean');
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,innerWidth/innerHeight,.1,4000);
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,powerPreference:'high-performance'});
renderer.setSize(innerWidth,innerHeight);renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.9;renderer.outputColorSpace=THREE.SRGBColorSpace;$('viewport').appendChild(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.09;controls.minDistance=1.5;controls.maxDistance=1100;controls.maxPolarAngle=Math.PI*.493;
const sky=new Sky();sky.scale.setScalar(3500);sky.material.uniforms.turbidity.value=3;sky.material.uniforms.rayleigh.value=1.3;sky.material.uniforms.mieCoefficient.value=.004;sky.material.uniforms.mieDirectionalG.value=.8;scene.add(sky);
const sun=new THREE.DirectionalLight(0xfff2da,3.1);sun.castShadow=true;sun.shadow.mapSize.set(4096,4096);sun.shadow.camera.near=1;sun.shadow.camera.far=3200;sun.shadow.bias=-.00008;sun.shadow.normalBias=.035;scene.add(sun,sun.target);scene.add(new THREE.HemisphereLight(0xc5e0ff,0x746249,1.1));scene.fog=new THREE.FogExp2(0xc7d0d2,.00042);
const pmrem=new THREE.PMREMGenerator(renderer);let env;
let solarState=null,environmentTimer=null;
function light(state){solarState=state;const v=new THREE.Vector3(...state.direction);sky.material.uniforms.sunPosition.value.copy(v);sun.color.set(state.elevation<15?0xffd5a0:0xfff2da);sun.intensity=state.elevation<=0?0:3.1*Math.min(1,state.elevation/8);sun.castShadow=state.elevation>0;
  updateShadow();if(!environmentTimer)environmentTimer=setTimeout(()=>{env?.dispose();env=pmrem.fromScene(sky);scene.environment=env.texture;scene.environmentIntensity=.42;environmentTimer=null;},500);
}

const loader=new THREE.TextureLoader();
function texture(name,repeat=1,srgb=true){const t=loader.load('assets/'+name,undefined,undefined,()=>{});t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(repeat,repeat);t.colorSpace=srgb?THREE.SRGBColorSpace:THREE.NoColorSpace;t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());return t;}
const material={panel:new THREE.MeshPhysicalMaterial({color:0x91aabe,map:texture('panel_color.jpg'),roughness:.27,metalness:0,clearcoat:1,clearcoatRoughness:.18,ior:1.5,envMapIntensity:.45}),frame:new THREE.MeshStandardMaterial({color:0xc0c5c7,metalness:.82,roughness:.38}),steel:new THREE.MeshStandardMaterial({color:0x8d9596,metalness:.65,roughness:.52}),concrete:new THREE.MeshStandardMaterial({color:0xd0cfc5,map:texture('concrete_color.jpg'),normalMap:texture('concrete_normal.jpg',1,false),normalScale:new THREE.Vector2(.35,.35),roughness:.96}),wall:new THREE.MeshStandardMaterial({color:0xc9cecd,metalness:.25,roughness:.65}),roof:new THREE.MeshStandardMaterial({color:0xb86c48,metalness:.25,roughness:.65}),trim:new THREE.MeshStandardMaterial({color:0x344f58,metalness:.4,roughness:.44}),glass:new THREE.MeshPhysicalMaterial({color:0x47616d,metalness:0,roughness:.2,clearcoat:1}),door:new THREE.MeshStandardMaterial({color:0x9faaa9,metalness:.45,roughness:.5})};
const box=new THREE.BoxGeometry(1,1,1),obj=new THREE.Object3D();
material.wall.normalMap=texture('concrete_normal.jpg',6,false);material.wall.normalScale=new THREE.Vector2(.075,.075);
material.roof.normalMap=texture('concrete_normal.jpg',10,false);material.roof.normalScale=new THREE.Vector2(.045,.045);
function geometryBox(x,y,z,w,h,d,rx=0){const g=box.clone();g.scale(w,h,d);g.rotateX(rx);g.translate(x,y,z);return g;}
function meshBox(parent,x,y,z,w,h,d,mat,rx=0){const m=new THREE.Mesh(geometryBox(x,y,z,w,h,d,rx),mat);m.castShadow=m.receiveShadow=true;parent.add(m);return m;}
function instance(geo,mat,n){const m=new THREE.InstancedMesh(geo,mat,n);m.castShadow=m.receiveShadow=true;m.instanceMatrix.setUsage(THREE.StaticDrawUsage);scene.add(m);return m;}
function position(inst,index,x,y,z,rx=0,sx=1,sy=1,sz=1){obj.position.set(x,y,z);obj.rotation.set(rx,0,0);obj.scale.set(sx,sy,sz);obj.updateMatrix();inst.setMatrixAt(index,obj.matrix);}
const world=new CANNON.World({gravity:new CANNON.Vec3(0,-9.81,0)});world.broadphase=new WalkBroadphase();const floor=new CANNON.Body({mass:0,shape:new CANNON.Plane()});floor.quaternion.setFromEuler(-Math.PI/2,0,0);world.addBody(floor);
// The walker is velocity-controlled; ground friction must not counteract input.
// Normal contact impulses still block walls and keep the body above the ground.
world.defaultContactMaterial.friction=0;
function collider(x,y,z,w,h,d,rotation=0){const b=new CANNON.Body({mass:0,shape:new CANNON.Box(new CANNON.Vec3(w/2,h/2,d/2))});b.position.set(x,y,z);b.quaternion.setFromEuler(0,rotation,0);world.addBody(b);}
const player=new CANNON.Body({mass:75,shape:new CANNON.Sphere(.38),linearDamping:.92,fixedRotation:true});world.addBody(player);player.sleep();let walking=false,yaw=0,pitch=0;const keys=new Set();
const data=await fetch('assets/layout.json').then(r=>{if(!r.ok)throw Error('배치 파일을 불러오지 못했습니다');return r.json()}).catch(fail);
function fail(e){$('loadtext').textContent=e.message;throw e;}
const groups=data.groups,modules=[],slope=Math.tan(Math.PI/6),tilt=Math.PI/6,L=1.425/Math.cos(tilt);
const frameGeo=mergeGeometries([geometryBox(-.483,0,0,.018,.045,L),geometryBox(.483,0,0,.018,.045,L),geometryBox(0,0,-L/2+.009,.983,.045,.018),geometryBox(0,0,L/2-.009,.983,.045,.018)]);
const panels=instance(new THREE.BoxGeometry(.947,.03,L-.036),material.panel,30000),frames=instance(frameGeo,material.frame,30000);
const slabs=instance(new THREE.BoxGeometry(9,.3,1.9),material.concrete,1500);
const supportGeos=[];for(const x of [.6,3.55,6.5,9.45])for(const depth of [.45,2.4]){const h=.72+depth*slope;supportGeos.push(geometryBox(x,h/2,-depth,.075,h,.075));}
for(const depth of [.45,2.4])supportGeos.push(geometryBox(5.0275,.70+depth*slope,-depth,9.6,.1,.065));
for(const x of [.6,3.55,6.5,9.45])supportGeos.push(geometryBox(x,1.51,-1.425,.08,.09,L*2,tilt));
const supports=instance(mergeGeometries(supportGeos),material.steel,1500);let mi=0;
for(let gi=0;gi<groups.length;gi++){const g=groups[gi],b=g.bounds;position(slabs,gi,b[0]+5.0275,.15,-(b[1]+1.425));position(supports,gi,b[0],0,-b[1]);collider(b[0]+5.0275,1,-(b[1]+1.425),10.1,2,2.85);for(let row=0;row<2;row++)for(let col=0;col<10;col++){const x=b[0]+col*1.008+.4915,n=b[1]+row*1.425+.7125,y=.8+(row*1.425+.7125)*slope;position(panels,mi,x,y,-n,tilt);position(frames,mi,x,y,-n,tilt);modules.push({id:`${g.id}-R${row+1}-M${String(col+1).padStart(2,'0')}`,group:g.id,x,n,y,handle:g.cad_handle});mi++;}}
for(const m of [panels,frames,slabs,supports]){m.instanceMatrix.needsUpdate=true;m.computeBoundingSphere();}
const map=new Map(modules.map((m,i)=>[m.id,i]));let consoleLink=null;
const inspection=createInspection({modules,sourceHash:data.source_sha256,selectID:id=>{if(map.has(id))select(map.get(id),true);}});
const groundMat=new THREE.MeshStandardMaterial({color:0xb7ac94,map:texture('ground_color.jpg',600),normalMap:texture('ground_normal.jpg',600,false),normalScale:new THREE.Vector2(.38,.38),roughness:1});const ground=new THREE.Mesh(new THREE.PlaneGeometry(3500,3500),groundMat);ground.rotation.x=-Math.PI/2;ground.position.set(170,-.015,210);ground.receiveShadow=true;scene.add(ground);
groundMat.normalScale.set(.2,.2);
groundMat.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',THREE.ShaderChunk.map_fragment.replace('texture2D( map, vMapUv )','mix(texture2D(map,vMapUv),texture2D(map,mat2(0.8,-0.6,0.6,0.8)*vMapUv*0.379+vec2(0.317,0.731)),0.45)'));};
// Boundary is a surveyed plan line, not an invented fence or perimeter road.
const boundary=new THREE.BufferGeometry().setFromPoints([...data.boundary,data.boundary[0]].map(p=>new THREE.Vector3(p[0],.025,-p[1])));const boundaryLine=new THREE.Line(boundary,new THREE.LineBasicMaterial({color:0xaaa487,transparent:true,opacity:.6}));scene.add(boundaryLine);
// Sparse low vegetation appears only outside the drawing's array footprint.
let seed=731;function rand(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
const reedGeo=mergeGeometries([geometryBox(0,.22,0,.018,.44,.018,.13),geometryBox(.04,.15,0,.014,.3,.014,-.25)]),reeds=instance(reedGeo,new THREE.MeshStandardMaterial({color:0x8b8763,roughness:1}),4500);reeds.castShadow=false;for(let i=0;i<4500;i++){let x,n;do{x=-70+rand()*490;n=-510+rand()*610;}while(groups.some(g=>x>g.bounds[0]-2&&x<g.bounds[2]+2&&n>g.bounds[1]-2&&n<g.bounds[3]+2));position(reeds,i,x,0,-n,0,.5+rand(),.35+rand(),.5+rand());}reeds.instanceMatrix.needsUpdate=true;
const surrounding=addEnvironment(scene);ground.visible=false;reeds.visible=false;
const environmentButton=document.getElementById('environment');
function toggleEnvironment(){const values=layers.state();layers.setMany(environmentLayerIDs,!environmentLayerIDs.every(id=>values[id]));}
environmentButton.onclick=toggleEnvironment;
const cables=addCables(scene);
const interiors=addInteriors({scene,world,buildings:data.buildings,equipment:cables.data.equipment,materials:material});
const buildingMeshes=interiors.buildingGroups;
// Selection outline is separate from the materials and never represents a defect.
const selection=new THREE.Mesh(new THREE.BoxGeometry(1.04,.065,L+.06),new THREE.MeshBasicMaterial({color:0xdfeab4,wireframe:true}));selection.visible=false;scene.add(selection);let selected=-1,transition=null,currentView='overview';
const envObjects=[...surrounding.group.children];
const environmentLayerIDs=['terrain','roads','farmland','forest','coast'];
const layerEntries=[
  ...cables.entries,
  {id:'panels',label:'태양광 모듈',section:'발전 설비',objects:[panels]},
  {id:'frames',label:'모듈 프레임',section:'발전 설비',objects:[frames]},
  {id:'supports',label:'지지대 · 구조물',section:'발전 설비',objects:[supports]},
  {id:'foundations',label:'콘크리트 기초',section:'발전 설비',objects:[slabs]},
  ...buildingMeshes.map((group,i)=>({id:'building'+(i+1),label:'전기실 '+(i+1),section:'전기실',objects:[group]})),
  {id:'boundary',label:'준공도면 부지 경계',section:'부지 및 주변',objects:[boundaryLine]},
  {id:'terrain',label:'지면 · 구릉',section:'부지 및 주변',objects:envObjects.filter(o=>o.name==='Context_Terrain_ASSUMED_HEIGHT')},
  {id:'roads',label:'도로 · 진입로',section:'부지 및 주변',objects:envObjects.filter(o=>o.name.startsWith('Road'))},
  {id:'farmland',label:'농경지',section:'부지 및 주변',objects:envObjects.filter(o=>o.name.startsWith('Farmland'))},
  {id:'forest',label:'수목',section:'부지 및 주변',objects:envObjects.filter(o=>o.isInstancedMesh)},
  {id:'coast',label:'제방 · 갯벌 · 수면',section:'부지 및 주변',objects:envObjects.filter(o=>!o.isInstancedMesh&&!o.name.startsWith('Road')&&!o.name.startsWith('Farmland')&&o.name!=='Context_Terrain_ASSUMED_HEIGHT')},
];
const layers=createLayers(layerEntries,()=>{
  const values=layers.state(),count=environmentLayerIDs.filter(id=>values[id]).length;
  environmentButton.textContent=count===5?'주변 환경 켜짐':count===0?'주변 환경 꺼짐':'주변 환경 일부';
  environmentButton.setAttribute('aria-pressed',count===5?'true':count===0?'false':'mixed');
  selection.visible=selected>=0&&panels.visible;
  $('selection').hidden=!selection.visible;
  $('layer-walk-note').hidden=!walking;
  $('cable-legend').hidden=!cables.entries.some(e=>e.objects[0].visible);
});
function select(index,focus=false){inspection.selectModule(modules[index].id);consoleLink?.onSelect(modules[index].id);if(!panels.visible)layers.set('panels',true);selected=index;const electrical=cables.selectModule(index);$('electrical-chain').textContent=`${electrical.id} → ${electrical.jb} → ${electrical.inverter}`;showStringInfo(electrical);const m=modules[index];selection.visible=true;selection.position.set(m.x,m.y,-m.n);selection.rotation.x=tilt;$('selection').hidden=false;$('moduleid').textContent=m.id;$('groupid').textContent=m.group;$('coords').textContent=`${m.x.toFixed(2)} / ${m.n.toFixed(2)} m`;const geographic=mapCandidate(m.x,m.n,data.source_sha256);if(geographic)$('coords').textContent+=` · 위도 ${geographic.lat.toFixed(7)}, 경도 ${geographic.lon.toFixed(7)} (${geographic.status})`;$('searchstatus').textContent='도면 식별자 · 현장 실물 대조 필요';if(focus){setView('detail',true);move(new THREE.Vector3(m.x+4,m.y+3,-m.n+5),new THREE.Vector3(m.x,m.y,-m.n));}updateQA();}
function move(pos,target){transition={from:camera.position.clone(),to:pos,fromTarget:controls.target.clone(),target,start:performance.now()};}
const detail=modules.find(m=>m.group==='S3-G0600')||modules[11980],b=data.buildings[1];
const presets={overview:[new THREE.Vector3(548,352,625),new THREE.Vector3(172,0,222)],detail:[new THREE.Vector3(detail.x+4,3.8,-detail.n+4.5),new THREE.Vector3(detail.x+2,1.4,-detail.n-.5)],building:[new THREE.Vector3(b.center[0]+25,11,-b.center[1]+22),new THREE.Vector3(b.center[0],2.6,-b.center[1])],top:[new THREE.Vector3(170,840,222),new THREE.Vector3(170,0,222)],walk:[interiors.entryPose(1).position,interiors.entryPose(1).target]};
const viewNames={overview:'전체 조감도',detail:'모듈 디테일',building:'전기실 외관',top:'수직 배치도',walk:'현장 보행'};
function setView(v,instant=false){if(!presets[v])v='overview';currentView=v;walking=v==='walk';keys.clear();document.body.classList.toggle('walking',walking);$('layer-walk-note').hidden=!walking;controls.enabled=!walking;const [pos,target]=presets[v];document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===v));$('viewname').textContent=viewNames[v];$('viewnumber').textContent=`0${Object.keys(viewNames).indexOf(v)+1} / 05`;$('hint').textContent=walking?'WASD 이동 · 드래그 시선 · E 문 개폐 · Shift 빠르게':'드래그 회전 · 휠 확대 · 오른쪽 드래그 이동';if(instant){transition=null;camera.position.copy(pos);controls.target.copy(target);camera.lookAt(target);}else move(pos,target);if(walking){player.position.set(pos.x,pos.y-1.32,pos.z);player.velocity.setZero();player.wakeUp();const dir=target.clone().sub(pos).normalize();yaw=Math.atan2(-dir.x,-dir.z);pitch=Math.asin(dir.y);}else player.sleep();updateShadow();updateQA();}
function enterRoom(index=Number($('room-choice').value)){
  const pose=interiors.entryPose(index);presets.walk=[pose.position,pose.target];
  layers.set('building'+(index+1),true);layers.setMany(cables.entries.map(e=>e.id),false);
  $('cable-panel').hidden=true;$('cables-toggle').setAttribute('aria-expanded','false');
  $('room-choice').value=String(index);setView('walk',true);document.activeElement?.blur();
}
function useDoor(){if(!walking)return;const result=interiors.interact(camera,player.position);$('door-message').textContent=result.reason==='doorway_occupied'?'문에서 한 걸음 떨어진 뒤 닫으세요.':'';}
$('room-entry').onclick=()=>enterRoom();$('door-action').onclick=useDoor;
function updateDoorHUD(){
  const n=walking?interiors.nearestDoor(player.position,camera):null;
  $('door-hud').hidden=!n||n.distance>3.4;
  if(n&&n.distance<=3.4)$('door-action').textContent='E · '+(n.door.target===0?'문 열기':'문 닫기');
  const inside=walking&&interiors.rooms.find(room=>{const p=interiors.toLocal(room,player.position);return Math.abs(p.x)<room.length/2&&Math.abs(p.z)<room.width/2;});
  $('room-status').hidden=!walking;$('room-status').textContent=inside?inside.id+' · 실내 탐색':'출입구로 이동하여 E로 문을 여세요';
}
async function exportInteriors(){
  const exportScene=new THREE.Scene();for(const group of buildingMeshes){const copy=group.clone(true);copy.visible=true;exportScene.add(copy);}
  const bytes=new Uint8Array(await new GLTFExporter().parseAsync(exportScene,{binary:true,onlyVisible:false}));
  let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary);
}
function previewRoom(index,monitor=false){setView('building',true);$('room-choice').value=String(index);$('viewname').textContent='전기실 '+(index+1)+(monitor?' · 감시실':' · 중앙 통로');const room=data.buildings[index];camera.position.copy(interiors.toWorld(room,monitor?[-9.6,2.05,-3.5]:[9.1,2.2,-.6]));controls.target.copy(interiors.toWorld(room,monitor?[-4.8,1.5,-2.9]:[-6,2,-.6]));camera.lookAt(controls.target);updateShadow();}
function updateShadow(){const t=controls.target,range=currentView==='overview'||currentView==='top'?430:50;Object.assign(sun.shadow.camera,{left:-range,right:range,top:range,bottom:-range});sun.shadow.camera.updateProjectionMatrix();const v=sky.material.uniforms.sunPosition.value;sun.position.copy(t).addScaledVector(v,1400);sun.target.position.copy(t);}
function testCollision(){const p=player.position.clone(),v=player.velocity.clone(),g=groups[599].bounds;player.wakeUp();player.position.set((g[0]+g[2])/2,.4,-g[1]+1.2);player.velocity.setZero();for(let i=0;i<120;i++){player.velocity.z=-3;world.step(1/60);}const result={passed:player.position.z>-g[1]+.25&&player.position.y>.3,arraySouth:-g[1],stoppedZ:player.position.z,groundHeight:player.position.y};player.position.copy(p);player.velocity.copy(v);if(!walking)player.sleep();return result;}
controls.addEventListener('end',updateShadow);for(const button of document.querySelectorAll('[data-view]'))button.onclick=()=>setView(button.dataset.view);
$('searchform').onsubmit=e=>{e.preventDefault();const id=$('search').value.trim().toUpperCase();if(map.has(id)){select(map.get(id),true);}else $('searchstatus').textContent='일치하는 ID가 없습니다. 예: S3-G0600-R1-M01';};$('copyid').onclick=async()=>{try{await navigator.clipboard.writeText(modules[selected].id);$('copyid').textContent='복사되었습니다';}catch{$('searchstatus').textContent='위 모듈 ID를 선택하여 복사하세요.';}};
const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();let down=null;
renderer.domElement.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};});renderer.domElement.addEventListener('pointermove',e=>{if(walking&&e.buttons){yaw-=e.movementX*.003;pitch=THREE.MathUtils.clamp(pitch-e.movementY*.003,-1.3,1.3);}});renderer.domElement.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;pointer.set(e.clientX/innerWidth*2-1,1-e.clientY/innerHeight*2);ray.setFromCamera(pointer,camera);if(walking&&interiors.clickDoor(ray,player.position)){return;}const hits=panels.visible?ray.intersectObject(panels):[];if(hits.length)select(hits[0].instanceId);});
addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)||e.target.isContentEditable||$('sources').open)return;if(walking&&e.code==='KeyE'&&!e.repeat){useDoor();e.preventDefault();}keys.add(e.code);if(walking&&['KeyW','KeyA','KeyS','KeyD','Space'].includes(e.code))e.preventDefault();});addEventListener('keyup',e=>keys.delete(e.code));addEventListener('blur',()=>keys.clear());
$('quality').onchange=e=>{const q=e.target.value;renderer.setPixelRatio(q==='ultra'?Math.min(devicePixelRatio,2):q==='high'?Math.min(devicePixelRatio,1.5):1);const size=q==='ultra'?8192:q==='high'?4096:2048;sun.shadow.mapSize.set(size,size);sun.shadow.map?.dispose();sun.shadow.map=null;};$('help').onclick=()=>$('sources').showModal();$('closehelp').onclick=()=>$('sources').close();$('fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();$('capture').onclick=()=>{renderer.render(scene,camera);const a=document.createElement('a');a.download=`Shinan3_${currentView}.png`;a.href=renderer.domElement.toDataURL('image/png');a.click();};
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);});
const compassArrow=document.querySelector('.compass span'),northDirection=new THREE.Vector3(),cameraDirection=new THREE.Vector3();
function updateCompass(){camera.getWorldDirection(cameraDirection);northDirection.set(0,0,-1).applyQuaternion(camera.quaternion.clone().invert());const angle=Math.atan2(northDirection.x,-northDirection.z)*180/Math.PI;compassArrow.style.transform=`rotate(${angle}deg)`;}
function updateQA(){window.__SHINAN_QA__={ready:true,modules:modules.length,groups:groups.length,buildings:data.buildings.length,selectedID:selected>=0?modules[selected].id:null,view:currentView,physics:'Cannon-es ground + 1500 array boxes + 3 rooms',assumed:['flat ground','materials','support sections','building details'],thermalLinked:inspection.inspect().candidateModules>0,inspection:inspection.inspect,environment:()=>({visible:environmentLayerIDs.some(id=>layers.state()[id]),trees:surrounding.treeCount,meshes:surrounding.meshCount,measuredElevation:false}),toggleEnvironment,layers,cables:cables.inspect,testCollision,exportInteriors,previewRoom,solar:()=>({...solarControls.inspect(),direction:solarState.direction,shadowEnabled:sun.castShadow,lightIntensity:sun.intensity}),testInteriors:()=>interiors.testPhysics(player),interiors:interiors.inspect,enterRoom,roomPosition:()=>interiors.toLocal(data.buildings[Number($('room-choice').value)],player.position).toArray(),physicsState:()=>({position:[player.position.x,player.position.y,player.position.z],velocity:[player.velocity.x,player.velocity.y,player.velocity.z],bodies:world.bodies.length,walking}),setView:(v)=>setView(v,true),selectID:id=>map.has(id)&&select(map.get(id),true),renderer};}
function showCablePanel(){
  $('cable-panel').hidden=false;$('layer-panel').hidden=true;$('layers-toggle').setAttribute('aria-expanded','false');
  $('cables-toggle').setAttribute('aria-expanded','true');
}
function cableMode(){
  layers.setMany(['cable_series','cable_dc_branch','cable_dc_feeder','cable_trays','cable_equipment'],true);
  layers.setMany(['panels','frames','supports','foundations','building1','building2','building3','forest','cable_ac_schematic'],false);
  layers.setMany(['terrain','roads','boundary','farmland','coast'],true);
  showCablePanel();setView('top');
}
function focusElectrical(){
  const pts=cables.focusPoints().map(p=>new THREE.Vector3(p[0],p[2],-p[1]));if(!pts.length)return;
  const box=new THREE.Box3().setFromPoints(pts),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
  const span=Math.max(size.x,size.z,35);setView('top',true);move(center.clone().add(new THREE.Vector3(0,span*2.2,span*.7)),center);$('viewname').textContent='선택 연결 추적';
}
function showStringInfo(s){
  $('cable-result-title').textContent=s.id;
  $('cable-result-body').textContent=`20개 모듈 직렬 → ${s.jb} → ${s.inverter}\n스트링 경계: ${s.source}\n양극·음극 인출과 접속반 간선: Cable Schedule.xls 대조 완료\n개별 포설 경로·높이·굵기는 시각화용 추정`;
  $('cable-id').value='D'+s.id.slice(3)+' P';
}
$('cables-toggle').onclick=()=>{if(!$('cable-panel').hidden){$('cable-panel').hidden=true;$('cables-toggle').setAttribute('aria-expanded','false');}else{cableMode();if(selected<0){const first=cables.data.strings.findIndex(s=>s.id==='SM-111A01');cables.selectString(first);showStringInfo(cables.data.strings[first]);}}};
$('cable-close').onclick=()=>{$('cable-panel').hidden=true;$('cables-toggle').setAttribute('aria-expanded','false');};
$('trace-cable').onclick=()=>{cableMode();$('cable-focus').checked=true;cables.setFocus(true);if(selected>=0)showStringInfo(cables.selectModule(selected));focusElectrical();};
$('cable-focus').onchange=e=>cables.setFocus(e.target.checked);
$('cable-form').onsubmit=e=>{
  e.preventDefault();let id=$('cable-id').value.trim().toUpperCase().replace(/\s+/g,' ');
  const si=cables.data.strings.findIndex(s=>s.id===id);
  if(si>=0){showStringInfo(cables.selectString(si));cables.setFocus(true);$('cable-focus').checked=true;focusElectrical();return;}
  if(!cables.schedule.has(id)){$('cable-result-title').textContent='일치하는 케이블이 없습니다';$('cable-result-body').textContent='예: D111A01 P, D111A00 N 또는 SM-111A01';return;}
  const {cable:c,path}=cables.selectCable(id);
  $('cable-result-title').textContent=c.id;
  $('cable-result-body').textContent=`${c.from.replaceAll('\n',' / ')} → ${c.to.replaceAll('\n',' / ')}\n${c.type} · ${c.cores}C × ${c.size_mm2} mm²\n목록상 길이 ${c.schedule_length_m} m (3D 선 길이와 다름)\n경로 코드: ${c.route_codes||'미기재'}\nCable Schedule.xls · 원본 행 ${c.row}\n${path?'연결 확인 / 3D 포설 형상 추정':'연결 목록만 제공 · 3D 위치 미확정'}`;
  if(path)layers.set('cable_'+path.kind,true);
  cables.setFocus(true);$('cable-focus').checked=true;if(path)focusElectrical();
};
$('cable-reset').onclick=()=>{for(const e of layerEntries)layers.set(e.id,!e.id.startsWith('cable_'));cables.setFocus(false);$('cable-focus').checked=false;$('cable-panel').hidden=true;$('cables-toggle').setAttribute('aria-expanded','false');setView('overview');};
setView(params.get('view')||'overview',true);const solarControls=createSolarControls(light);consoleLink=createConsoleLink({scene,modules,index:map,slope,tilt,length:L,select,solar:solarControls});consoleLink.start();updateShadow();$('loading').style.opacity=0;setTimeout(()=>$('loading').remove(),550);let last=performance.now(),framesCount=0,fpsTime=last;
function animate(now){requestAnimationFrame(animate);const dt=Math.min((now-last)/1000,.05);last=now;solarControls.tick(dt);interiors.update(dt,player.position,camera.position);updateDoorHUD();if(transition){const t=Math.min(1,(now-transition.start)/900),ease=t*t*(3-2*t);camera.position.lerpVectors(transition.from,transition.to,ease);controls.target.lerpVectors(transition.fromTarget,transition.target,ease);camera.lookAt(controls.target);if(t===1){transition=null;updateShadow();}}else if(walking){const fw=(keys.has('KeyW')?1:0)-(keys.has('KeyS')?1:0),side=(keys.has('KeyD')?1:0)-(keys.has('KeyA')?1:0),speed=(keys.has('ShiftLeft')?3.2:2.2)/Math.max(1,Math.hypot(fw,side));player.velocity.x=(-Math.sin(yaw)*fw+Math.cos(yaw)*side)*speed;player.velocity.z=(-Math.cos(yaw)*fw-Math.sin(yaw)*side)*speed;world.step(1/60,dt,3);camera.position.set(player.position.x,player.position.y+1.32,player.position.z);camera.rotation.set(pitch,yaw,0,'YXZ');controls.target.copy(camera.position);updateShadow();}else controls.update();updateCompass();renderer.render(scene,camera);framesCount++;if(now-fpsTime>1000){const fps=framesCount*1000/(now-fpsTime);$('runtime').textContent=`${Math.round(fps)} FPS · ${renderer.info.render.calls} DRAW · 로컬 좌표 m`;window.__SHINAN_QA__.fps=Math.round(fps);window.__SHINAN_QA__.drawCalls=renderer.info.render.calls;framesCount=0;fpsTime=now;}}
requestAnimationFrame(animate);

import * as C from 'cannon-es';
import {WalkBroadphase} from './walk_physics.js';
import fs from 'node:fs';
const data=JSON.parse(fs.readFileSync(new URL('./assets/layout.json',import.meta.url),'utf8'));
function run(optimized){
 const w=new C.World({gravity:new C.Vec3(0,-9.81,0)});w.broadphase=optimized?new WalkBroadphase():new C.SAPBroadphase(w);
 w.defaultContactMaterial.friction=0;
 const floor=new C.Body({mass:0,shape:new C.Plane()});floor.quaternion.setFromEuler(-Math.PI/2,0,0);w.addBody(floor);
 for(const g of data.groups){const b=g.bounds,o=new C.Body({mass:0,shape:new C.Box(new C.Vec3(5.05,1,1.425))});o.position.set(b[0]+5.0275,1,-b[1]-1.425);w.addBody(o);}
 for(const b of data.buildings){const o=new C.Body({mass:0,shape:new C.Box(new C.Vec3(b.length/2,b.ridge_z/2,b.width/2))});o.position.set(b.center[0],b.ridge_z/2,-b.center[1]);o.quaternion.setFromEuler(0,b.rotation,0);w.addBody(o);}
 const p=new C.Body({mass:75,shape:new C.Sphere(.38),linearDamping:.92,fixedRotation:true});w.addBody(p);const b=data.buildings[1];p.position.set(b.center[0]+16,.4,-b.center[1]);
 const start=performance.now();let firstSecondDistance,maxWallPenetration=0;for(let i=0;i<540;i++){p.velocity.x=-2.2;p.velocity.z=0;w.step(1/60);const localX=Math.cos(b.rotation)*(p.position.x-b.center[0])-Math.sin(b.rotation)*(p.position.z+b.center[1]);maxWallPenetration=Math.max(maxWallPenetration,b.length/2+.38-localX);if(i===59)firstSecondDistance=b.center[0]+16-p.position.x;}const elapsed=performance.now()-start;
 const stop=p.position.clone();for(let i=0;i<60;i++){p.velocity.x=p.velocity.z=0;w.step(1/60);}const releaseDelta=p.position.distanceTo(stop);
 return{method:optimized?'WalkBroadphase':'SAPBroadphase',milliseconds:elapsed,steps:540,bodies:w.bodies.length,position:[p.position.x,p.position.y,p.position.z],distance:b.center[0]+16-p.position.x,firstSecondDistance,releaseDelta,maxWallPenetration};
}
const results=[run(false),run(true)];console.log(JSON.stringify(results,null,2));fs.writeFileSync(new URL('../results/shinan3_review/physics_benchmark.json',import.meta.url),JSON.stringify(results,null,2));
if(Math.abs(results[0].distance-results[1].distance)>.02)throw Error('Collision stop position changed');
for(const r of results)if(r.firstSecondDistance<1.8||r.firstSecondDistance>2.4||r.distance<5||r.distance>6||r.releaseDelta>.05||r.position[1]<.3)throw Error('Walking speed, wall stop, release or ground contact failed');
for(const r of results)if(r.maxWallPenetration>.03)throw Error('Wall penetration exceeds 3cm tolerance');
fs.writeFileSync(new URL('../results/shinan3_review/physics_validation.json',import.meta.url),JSON.stringify({controller:'velocity-controlled Cannon sphere; friction=0; gravity=-9.81; linearDamping=.92',version:2,passed:true,comparison:'SAP vs awake-dynamic broadphase, identical world and input',results},null,2));

import * as CANNON from 'cannon-es';

// This scene has one moving walker and 1,504 fixed obstacles. The generic SAP
// implementation still loops over all static-static pairs before discarding them.
// Keep Cannon's bounds tests, contact solver and collision response, but collect
// candidates only for awake dynamic bodies. No static geometry is omitted.
export class WalkBroadphase extends CANNON.Broadphase {
  constructor(){super();this.useBoundingBoxes=false;}
  collisionPairs(world,p1,p2){
    const bodies=world.bodies;
    for(let i=0;i<bodies.length;i++){
      const a=bodies[i];
      if(a.type===CANNON.Body.STATIC||a.sleepState===CANNON.Body.SLEEPING)continue;
      for(let j=0;j<bodies.length;j++){
        const b=bodies[j];
        if(i===j)continue;
        if(b.type!==CANNON.Body.STATIC&&b.sleepState!==CANNON.Body.SLEEPING&&j<i)continue;
        if(this.needBroadphaseCollision(a,b))this.intersectionTest(a,b,p1,p2);
      }
    }
  }
}

// Context only: traced from SA-E-11210 (p14), not a surveyed terrain model.
export function addEnvironment(THREE, ground) {
  const environment=new THREE.Group();environment.name='Surroundings — scan-derived approximate boundary';ground.add(environment);
  const scale=1017/344.320;
  const drawing=[[265,345],[470,300],[760,228],[975,177],[1190,150],[1495,88],[1587,87],[1584,285],[1530,300],[1495,326],[1460,374],[1465,398],[1414,420],[1297,448],[1310,510],[1400,493],[1465,693],[1450,741],[1405,770],[1355,785],[1290,1018],[1270,1033],[1065,1061],[805,1065],[770,1052],[642,925],[522,700],[460,553],[389,418],[330,350]];
  const boundary=drawing.map(([x,y])=>new THREE.Vector2((x-503)/scale,(y-1005)/scale));
  const mat=(color,roughness=1)=>new THREE.MeshStandardMaterial({color,roughness});
  function polygon(points,material,y,name){const shape=new THREE.Shape(points.map(p=>new THREE.Vector2(p.x,-p.y)));const mesh=new THREE.Mesh(new THREE.ShapeGeometry(shape),material);mesh.rotation.x=-Math.PI/2;mesh.position.y=y;mesh.receiveShadow=true;mesh.name=name;environment.add(mesh);return mesh;}
  // Do not derive elevations from the RGBA orthomosaic: all surfaces remain flat.
  polygon(boundary,mat('#8e9270'),.016,'Dry coastal grass platform');
  const water=mat('#547f86',.3);water.metalness=.12;
  polygon([new THREE.Vector2(-650,-700),new THREE.Vector2(850,-700),new THREE.Vector2(850,-435),new THREE.Vector2(370,-335),new THREE.Vector2(-95,-248),new THREE.Vector2(-170,-310),new THREE.Vector2(-650,-310)],water,.012,'North sea — schematic shoreline from drawing');
  const box=new THREE.BoxGeometry(1,1,1),dummy=new THREE.Object3D();
  const roads=[],posts=[],rails=[],meshLines=[],shrubs=[];
  function segment(a,b,width,y,height,list){const d=b.clone().sub(a),len=d.length();list.push({x:(a.x+b.x)/2,z:(a.y+b.y)/2,y,w:width,h:height,l:len,angle:Math.atan2(d.x,d.y)});}
  const centre=new THREE.Vector2(150,-140);
  let seed=12903;function random(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
  for(let i=0;i<boundary.length;i++){
    const a=boundary[i],b=boundary[(i+1)%boundary.length],delta=b.clone().sub(a),len=delta.length();
    const normal=new THREE.Vector2(-delta.y,delta.x).normalize();if(normal.dot(a.clone().add(b).multiplyScalar(.5).sub(centre))<0)normal.multiplyScalar(-1);
    // North access road and west/south perimeter lanes are present on p14.
    if(i<6||i>=19){const pa=a.clone().addScaledVector(normal,4.8),pb=b.clone().addScaledVector(normal,4.8);segment(pa,pb,4,.035,.05,roads);}
    // Leave a service entrance at the southern access point.
    const gap=i===21;
    const count=Math.max(1,Math.ceil(len/3));
    for(let j=0;j<=count;j++){const p=a.clone().lerp(b,j/count);if(gap&&p.x>178&&p.x<189)continue;posts.push({x:p.x,z:p.y,y:.91,w:.055,h:1.8,l:.055,angle:0});}
    if(!gap){segment(a,b,.034,.3,.034,rails);segment(a,b,.034,1.7,.034,rails);
      // Sparse diagonal wire net represented as one line batch, avoiding hundreds of transparent meshes.
      for(let s=0;s<len;s+=.7){const p=a.clone().addScaledVector(delta,s/len),q=a.clone().addScaledVector(delta,Math.min(len,s+1.4)/len);meshLines.push(p.x,.28,p.y,q.x,1.7,q.y,p.x,1.7,p.y,q.x,.28,q.y);}
    }
    for(let j=0;j<Math.floor(len/4);j++){const p=a.clone().lerp(b,random()).addScaledVector(normal,7+random()*4);if(i<6)continue;shrubs.push({x:p.x,z:p.y,y:.2+random()*.15,s:.3+random()*.45});}
  }
  function batch(name,list,material){const im=new THREE.InstancedMesh(box,material,list.length);list.forEach((v,i)=>{dummy.position.set(v.x,v.y,v.z);dummy.rotation.set(0,v.angle,0);dummy.scale.set(v.w,v.h,v.l);dummy.updateMatrix();im.setMatrixAt(i,dummy.matrix);});im.name=name;im.receiveShadow=true;im.castShadow=true;environment.add(im);return im;}
  batch('Perimeter access lanes — approximate',roads,mat('#b5b4a7'));
  batch('Galvanized perimeter posts',posts,mat('#8b9992',.53));batch('Fence rails',rails,mat('#9da8a0',.5));
  const wireGeo=new THREE.BufferGeometry();wireGeo.setAttribute('position',new THREE.Float32BufferAttribute(meshLines,3));const wire=new THREE.LineSegments(wireGeo,new THREE.LineBasicMaterial({color:'#6b7d74',transparent:true,opacity:.45}));wire.name='Perimeter wire mesh';environment.add(wire);
  const plants=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),mat('#637a49'),shrubs.length);shrubs.forEach((v,i)=>{dummy.position.set(v.x,v.y,v.z);dummy.rotation.set(random(),random()*6,random());dummy.scale.set(v.s,v.s*.55,v.s*.8);dummy.updateMatrix();plants.setMatrixAt(i,dummy.matrix);plants.setColorAt(i,new THREE.Color().setHSL(.19+random()*.06,.18+random()*.16,.25+random()*.12));});plants.name='Sparse low coastal vegetation — indicative';plants.castShadow=true;environment.add(plants);
  return {group:environment,boundary:boundary.map(p=>[p.x,p.y]),fencePosts:posts.length,shrubs:shrubs.length,source:'SA-E-11210 p14 and orthomosaic preview',status:'Approximate planar context; shoreline, vegetation and fence details are schematic. No terrain elevations inferred.'};
}

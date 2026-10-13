import * as THREE from 'three';
import ENV from './environment_data.js';

export function addEnvironment(scene){
  const group=new THREE.Group();group.name='Satellite-guided surrounding context';scene.add(group);
  for(const item of ENV.meshes){
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(item.vertices.flatMap(([e,n,h])=>[e,h,-n]),3));
    const indices=[];
    for(const face of item.faces){
      if(face.length===3)indices.push(...face);
      else {
        const points=face.map(i=>new THREE.Vector2(item.vertices[i][0],item.vertices[i][1]));
        for(const tri of THREE.ShapeUtils.triangulateShape(points,[]))indices.push(...tri.map(i=>face[i]));
      }
    }
    geometry.setIndex(indices);geometry.computeVertexNormals();
    if(item.vertex_colors)geometry.setAttribute('color',new THREE.Float32BufferAttribute(item.vertex_colors.flat(),3));
    const water=item.name==='Coastal_Water'||item.name.startsWith('Tidal_Channel');
    const material=new THREE.MeshStandardMaterial({color:item.vertex_colors?0xffffff:new THREE.Color(...item.color),vertexColors:!!item.vertex_colors,roughness:water?.36:.94,metalness:water?.12:0,side:THREE.DoubleSide});
    const overlay=item.name.startsWith('Farmland')||item.name.startsWith('Road');
    if(overlay){material.polygonOffset=true;material.polygonOffsetFactor=-2;material.polygonOffsetUnits=-2;}
    const mesh=new THREE.Mesh(geometry,material);mesh.name=item.name;mesh.receiveShadow=!overlay;group.add(mesh);
  }
  const crown=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1,1),new THREE.MeshStandardMaterial({color:0xffffff,roughness:.95,flatShading:false}),ENV.trees.length);
  const trunks=new THREE.InstancedMesh(new THREE.CylinderGeometry(.18,.26,1,5),new THREE.MeshStandardMaterial({color:0x685b43,roughness:1}),ENV.trees.length);
  const dummy=new THREE.Object3D(),palette=[0x48603d,0x536943,0x3b5636,0x60714b];
  ENV.trees.forEach(([x,n,z,r,h,color],i)=>{
    dummy.position.set(x,z+h*.68,-n);dummy.rotation.set(.12*Math.sin(i),i*2.39,.1*Math.cos(i));dummy.scale.set(r,h*.46,r*.85);dummy.updateMatrix();crown.setMatrixAt(i,dummy.matrix);crown.setColorAt(i,new THREE.Color(palette[color]));
    dummy.position.set(x,z+h*.29,-n);dummy.rotation.set(0,0,0);dummy.scale.set(1,h*.58,1);dummy.updateMatrix();trunks.setMatrixAt(i,dummy.matrix);
  });
  crown.castShadow=true;crown.receiveShadow=true;trunks.castShadow=false;group.add(crown,trunks);
  crown.computeBoundingSphere();trunks.computeBoundingSphere();
  return {group,treeCount:ENV.trees.length,meshCount:ENV.meshes.length,measuredElevation:false};
}

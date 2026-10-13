// Photo-informed members. Cross sections, footing sizes and anchors remain visual estimates.
export function buildArrayStructure(THREE,layout){
  const supports=new THREE.Group(),foundations=new THREE.Group();supports.name='Galvanized array frames';foundations.name='Rectangular concrete foundations';
  let seed=6911;const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
  function surface(base,amount){const bytes=new Uint8Array(128*128*4);for(let i=0;i<bytes.length;i+=4){const n=(rnd()-.5)*amount;for(let c=0;c<3;c++)bytes[i+c]=Math.max(0,Math.min(255,base[c]+n));bytes[i+3]=255;}const t=new THREE.DataTexture(bytes,128,128);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(3,3);t.colorSpace=THREE.SRGBColorSpace;t.needsUpdate=true;return t;}
  const steel=new THREE.MeshStandardMaterial({color:'#a6b3b8',map:surface([205,209,208],35),metalness:.67,roughness:.54});
  const concrete=new THREE.MeshStandardMaterial({color:'#b4aea0',map:surface([215,209,194],45),roughness:.96});
  const dark=new THREE.MeshStandardMaterial({color:'#252b28',roughness:.8});
  const zinc=new THREE.MeshStandardMaterial({color:'#b5bcb9',metalness:.68,roughness:.43});
  const green=new THREE.MeshStandardMaterial({color:'#2f9b6b',roughness:.68});
  const box=new THREE.BoxGeometry(1,1,1);
  // Actual open channel: web plus two flanges. Unit length along local Y.
  function channel(){const vertices=[],normals=[],uvs=[],indices=[];for(const [w,d,x,z] of [[.006,.08,-.067,0],[.14,.006,0,-.037],[.14,.006,0,.037]]){const g=new THREE.BoxGeometry(w,1,d);g.translate(x,0,z);const offset=vertices.length/3;vertices.push(...g.attributes.position.array);normals.push(...g.attributes.normal.array);uvs.push(...g.attributes.uv.array);indices.push(...Array.from(g.index.array,n=>n+offset));g.dispose();}const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));g.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));g.setIndex(indices);return g;}
  const lists={slabs:[],grout:[],plates:[],channels:[],rails:[],anchors:[],heads:[],earth:[]};
  const up=new THREE.Vector3(0,1,0),identity=new THREE.Quaternion();
  function cube(list,x,y,z,sx,sy,sz){list.push({p:[x,y,z],s:[sx,sy,sz],q:identity});}
  function beam(list,a,b,sx=1,sz=1){const av=new THREE.Vector3(...a),bv=new THREE.Vector3(...b),d=bv.clone().sub(av);list.push({p:av.add(bv).multiplyScalar(.5).toArray(),s:[sx,d.length(),sz],q:new THREE.Quaternion().setFromUnitVectors(up,d.normalize())});}
  const slope=Math.tan(22*Math.PI/180),top=z=>1.43-z*slope-.095;
  for(const g of layout){
    for(const x of [-4.25,0,4.25]){
      cube(lists.slabs,g.x+x,.065,g.z,1.4,.13,3.25);
      for(const z of [-1.15,1.15]){
        cube(lists.grout,g.x+x,.165,g.z+z,.32,.07,.32);
        cube(lists.plates,g.x+x,.211,g.z+z,.29,.022,.29);
        beam(lists.channels,[g.x+x,.225,g.z+z],[g.x+x,top(z)-.09,g.z+z]);
        for(const dx of [-.112,.112])for(const dz of [-.112,.112]){
          cube(lists.anchors,g.x+x+dx,.30,g.z+z+dz,.025,.16,.025);
          cube(lists.heads,g.x+x+dx,.235,g.z+z+dz,.045,.025,.045);
        }
      }
      beam(lists.channels,[g.x+x,.43,g.z+1.15],[g.x+x,top(-1.15)-.19,g.z-1.15],.65,.65);
      beam(lists.channels,[g.x+x,top(-1.52)-.07,g.z-1.52],[g.x+x,top(1.52)-.07,g.z+1.52]);
      // Bolted intersections read as real steel connections close to the frame.
      for(const z of [-1.15,1.15])cube(lists.heads,g.x+x+.073,top(z)-.14,g.z+z,.025,.042,.042);
    }
    for(const z of [-1.24,-.4,.4,1.24])beam(lists.rails,[g.x-5.08,top(z),g.z+z],[g.x+5.08,top(z),g.z+z],.7,.7);
    // Low longitudinal channel visible in photos, away from walking aisles.
    beam(lists.rails,[g.x-5.08,.42,g.z-1.15],[g.x+5.08,.42,g.z-1.15]);
    beam(lists.earth,[g.x-4.18,.38,g.z+1.2],[g.x-4.18,.12,g.z+1.45],.014,.014);
  }
  const temp=new THREE.Object3D();
  function batch(name,list,geometry,material,parent){const mesh=new THREE.InstancedMesh(geometry,material,list.length);for(let i=0;i<list.length;i++){const v=list[i];temp.position.fromArray(v.p);temp.scale.fromArray(v.s);temp.quaternion.copy(v.q);temp.updateMatrix();mesh.setMatrixAt(i,temp.matrix);}mesh.name=name;mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh;}
  batch('Long rectangular paired-post concrete slabs',lists.slabs,box,concrete,foundations);
  batch('Grouted raised pedestals',lists.grout,box,concrete,foundations);
  batch('Square galvanized baseplates',lists.plates,box,zinc,supports);
  const ch=channel();batch('Open C-channel posts, diagonal braces and rafters',lists.channels,ch,steel,supports);
  batch('Module purlins and low longitudinal channels',lists.rails,ch,steel,supports);
  batch('Four black anchor sleeves per base',lists.anchors,box,dark,supports);
  batch('Anchor nuts and connection bolt heads',lists.heads,box,zinc,supports);
  batch('Indicative green grounding conductor',lists.earth,new THREE.CylinderGeometry(.5,.5,1,6),green,supports);
  return {supports,foundations,metadata:{groups:layout.length,posts:layout.length*6,slabs:layout.length*3,anchors:layout.length*24,drawCalls:8,source:['IMG_5910.JPG','IMG_5911.JPG','SA-E-11110 p10'],status:'Photo-informed visual geometry; three post pairs, member sections, footing extents and anchors are approximations, not structural engineering data.'}};
}

"""Import the review GLB with efficient Geometry Nodes instances into Blender.
Run with Blender --background --python this_file.py. Source scene is preserved.
"""
import bpy, json, struct, math
from pathlib import Path
from mathutils import Matrix, Quaternion, Vector
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan2_delivery/Models'
raw=(OUT/'Shinan2_Model.glb').read_bytes()
jlen,jtype=struct.unpack_from('<II',raw,12)
doc=json.loads(raw[20:20+jlen])
binstart=20+jlen
blen,btype=struct.unpack_from('<II',raw,binstart)
binary=raw[binstart+8:binstart+8+blen]
def accessor(index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    count={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
    assert a['componentType']==5126
    offset=v.get('byteOffset',0)+a.get('byteOffset',0)
    stride=v.get('byteStride',count*4)
    return [struct.unpack_from('<'+'f'*count,binary,offset+i*stride) for i in range(a['count'])]
specs=[]
for index,node in enumerate(doc['nodes']):
    ext=node.get('extensions',{}).pop('EXT_mesh_gpu_instancing',None)
    if ext:
        attrs={key:accessor(value) for key,value in ext['attributes'].items()}
        original=node.get('name','Instances')
        node['name']=f'INSTANCE_SOURCE_{index}'
        specs.append((node['name'],original,attrs))
for key in ['extensionsUsed','extensionsRequired']:
    if key in doc:doc[key]=[v for v in doc[key] if v!='EXT_mesh_gpu_instancing']
js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4)
glb=struct.pack('<4sII',b'glTF',2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary
temp=ROOT/'tmp/shinan2_blender_base.glb';temp.write_bytes(glb)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(temp))
C=Matrix(((1,0,0),(0,0,-1),(0,1,0)))
total=0
for name,title,attrs in specs:
    prototype=bpy.data.objects.get(name)
    if prototype is None:raise RuntimeError('Missing imported prototype '+name)
    transform=prototype.matrix_world.copy()
    prototype.name=title+' [prototype]'
    prototype.parent=None;prototype.matrix_world=Matrix.Identity(4)
    prototype.hide_render=True;prototype.hide_set(True)
    n=len(attrs['TRANSLATION']);total+=n
    positions=[(x,-z,y) for x,y,z in attrs['TRANSLATION']]
    mesh=bpy.data.meshes.new(title+' points');mesh.from_pydata(positions,[],[]);mesh.update()
    rotations=mesh.attributes.new('instance_rotation','FLOAT_VECTOR','POINT')
    scales=mesh.attributes.new('instance_scale','FLOAT_VECTOR','POINT')
    rotvals=[];scalevals=[]
    for i in range(n):
        q=attrs.get('ROTATION',[(0,0,0,1)])
        x,y,z,w=q[i] if len(q)>1 else q[0]
        e=(C@Quaternion((w,x,y,z)).to_matrix()@C.transposed()).to_euler()
        rotvals.extend(e)
        s=attrs.get('SCALE',[(1,1,1)])
        sx,sy,sz=s[i] if len(s)>1 else s[0];scalevals.extend((sx,sz,sy))
    rotations.data.foreach_set('vector',rotvals);scales.data.foreach_set('vector',scalevals)
    obj=bpy.data.objects.new(title,mesh);bpy.context.collection.objects.link(obj);obj.matrix_world=transform
    obj['instance_count']=n;obj['source']='ThreeJS review model; scan-derived placement'
    tree=bpy.data.node_groups.new(title+' instances','GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    inp=tree.nodes.new('NodeGroupInput');out=tree.nodes.new('NodeGroupOutput')
    info=tree.nodes.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=prototype
    info.transform_space='ORIGINAL';info.inputs['As Instance'].default_value=False
    inst=tree.nodes.new('GeometryNodeInstanceOnPoints')
    r=tree.nodes.new('GeometryNodeInputNamedAttribute');r.data_type='FLOAT_VECTOR';r.inputs['Name'].default_value='instance_rotation'
    s=tree.nodes.new('GeometryNodeInputNamedAttribute');s.data_type='FLOAT_VECTOR';s.inputs['Name'].default_value='instance_scale'
    tree.links.new(inp.outputs['Geometry'],inst.inputs['Points']);tree.links.new(info.outputs['Geometry'],inst.inputs['Instance'])
    tree.links.new(r.outputs['Attribute'],inst.inputs['Rotation']);tree.links.new(s.outputs['Attribute'],inst.inputs['Scale']);tree.links.new(inst.outputs['Instances'],out.inputs['Geometry'])
    modifier=obj.modifiers.new('Efficient repeated components','NODES');modifier.node_group=tree
scene=bpy.context.scene
scene['site']='Shinan Phase 2';scene['modules']=20420;scene['groups']=1021
scene['accuracy']='Scan-derived positions; source photos guide materials; circuit IDs unverified'
scene['instance_count']=total
scene['electrical_scope']='Drawing-based string/JB/inverter mapping. Cable branches are reconstructed. See Electrical documents for source conflicts.'
# glTF line primitives import as edge-only meshes. Give cable line batches a
# visible, explicitly illustrative radius in the Blender editing model.
wire_objects=[]
for obj in list(scene.objects):
    if obj.type!='MESH' or obj.get('instance_count') or obj.hide_render or len(obj.data.polygons) or not len(obj.data.edges):continue
    parent=obj.parent;is_cable=False
    while parent:
        if parent.name.startswith('Cables '):is_cable=True;break
        parent=parent.parent
    if not is_cable:continue
    tree=bpy.data.node_groups.new('Cable display thickness '+obj.name,'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    inp=tree.nodes.new('NodeGroupInput');out=tree.nodes.new('NodeGroupOutput');curve=tree.nodes.new('GeometryNodeMeshToCurve');profile=tree.nodes.new('GeometryNodeCurvePrimitiveCircle');profile.inputs['Resolution'].default_value=4;profile.inputs['Radius'].default_value=.015
    sweep=tree.nodes.new('GeometryNodeCurveToMesh');tree.links.new(inp.outputs['Geometry'],curve.inputs['Mesh']);tree.links.new(curve.outputs['Curve'],sweep.inputs['Curve']);tree.links.new(profile.outputs['Curve'],sweep.inputs['Profile Curve'])
    if obj.data.materials:
        material=tree.nodes.new('GeometryNodeSetMaterial');material.inputs['Material'].default_value=obj.data.materials[0];tree.links.new(sweep.outputs['Mesh'],material.inputs['Geometry']);tree.links.new(material.outputs['Geometry'],out.inputs['Geometry'])
    else:tree.links.new(sweep.outputs['Mesh'],out.inputs['Geometry'])
    obj.modifiers.new('Illustrative cable radius, not cable schedule diameter','NODES').node_group=tree
    obj['display_radius_m']=.015;wire_objects.append(obj.name)
scene.render.engine='CYCLES';scene.cycles.samples=24
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Coastal daylight') if not scene.world else scene.world
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.66,.74,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.65
camdata=bpy.data.cameras.new('Review overview');cam=bpy.data.objects.new('Review overview',camdata);scene.collection.objects.link(cam)
cam.location=(420,-235,265);target=Vector((171,145,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.lens=40;camdata.clip_end=3000;scene.camera=cam
for obj in scene.objects:
    if obj.type=='LIGHT' and obj.data.type=='SUN':obj.data.energy=0
sun_data=bpy.data.lights.new('Review daylight — 13:00 KST approximate','SUN');sun_data.energy=3.0;sun_data.angle=.015
sun_obj=bpy.data.objects.new(sun_data.name,sun_data);scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler=Vector((.15,.63,-.76)).to_track_quat('-Z','Y').to_euler()
scene.view_settings.exposure=.4
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=500
            area.spaces.active.region_3d.view_location=(170,145,0)
            area.spaces.active.clip_end=3000
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan2_Review.blend'))
report={'objects':len(scene.objects),'instance_count':total,'modules':20420,'cable_batches':len(wire_objects),'blend_bytes':(OUT/'Shinan2_Review.blend').stat().st_size,'status':'imported with geometry-node instances; static model, viewer controls not exported'}
(ROOT/'results/shinan2_review/blender_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))

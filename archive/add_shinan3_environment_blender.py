"""Add shared satellite-guided simplified surroundings to the editable scene."""
from pathlib import Path
import json,math
import bpy,bmesh
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_refined'
data=json.loads((ROOT/'shinan3_viewer/assets/environment.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
scene=bpy.context.scene;bpy.context.preferences.filepaths.save_version=0
name='12_Surrounding_Environment_ASSUMED'
old=bpy.data.collections.get(name)
if old:
    for ob in list(old.objects):bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(old)
coll=bpy.data.collections.new(name);scene.collection.children.link(coll)
def mat(name,color,rough=.94):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough
    return m
def obj(name,verts,faces,material):
    m=bpy.data.meshes.new(name);m.from_pydata(verts,[],faces);m.update();ob=bpy.data.objects.new(name,m);coll.objects.link(ob);m.materials.append(material);return ob
for item in data['meshes']:
    water=item['name']=='Coastal_Water' or item['name'].startswith('Tidal_Channel')
    material=mat(item['name'],item['color'],.36 if water else .94)
    ob=obj(item['name'],item['vertices'],item['faces'],material)
    if 'vertex_colors' in item:
        attr=ob.data.color_attributes.new(name='terrain_color',type='FLOAT_COLOR',domain='POINT')
        for target,color in zip(attr.data,item['vertex_colors']):target.color=(*color,1)
        n=material.node_tree.nodes.new('ShaderNodeVertexColor');n.layer_name='terrain_color'
        bs=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED');material.node_tree.links.new(n.outputs['Color'],bs.inputs['Base Color'])
        for f in ob.data.polygons:f.use_smooth=True
    ob['geometry_status']='Satellite-guided simplified context; elevations not measured'
bm=bmesh.new();bmesh.ops.create_icosphere(bm,subdivisions=2,radius=1)
temp=bpy.data.meshes.new('Canopy_template');bm.to_mesh(temp);bm.free()
tv=[tuple(v.co) for v in temp.vertices];tf=[tuple(f.vertices) for f in temp.polygons]
palette=[0x48603d,0x536943,0x3b5636,0x60714b]
def linear(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
for ci,hexcolor in enumerate(palette):
    color=[linear(((hexcolor>>s)&255)/255) for s in (16,8,0)];v=[];f=[]
    for i,(x,n,z,r,h,c) in enumerate(data['trees']):
        if c!=ci:continue
        a=i*2.39;co,si=math.cos(a),math.sin(a);offset=len(v)
        for vx,vy,vz in tv:v.append((x+vx*r*co-vy*r*.85*si,n+vx*r*si+vy*r*.85*co,z+h*.68+vz*h*.46))
        f.extend(tuple(offset+j for j in face) for face in tf)
    ob=obj('Simplified_Forest_Canopies_'+str(ci),v,f,mat('Forest tone '+str(ci),color))
    for face in ob.data.polygons:face.use_smooth=True
bpy.data.meshes.remove(temp)
# Shared low-poly trunks are merged, so there are no thousands of new scene objects.
v=[];f=[]
for x,n,z,r,h,c in data['trees']:
    off=len(v)
    for top in (0,1):
        for k in range(5):
            a=2*math.pi*k/5;v.append((x+.22*math.cos(a),n+.22*math.sin(a),z+top*h*.58))
    for k in range(5):f.append((off+k,off+(k+1)%5,off+(k+1)%5+5,off+k+5))
obj('Simplified_Forest_Trunks',v,f,mat('Tree bark',(.12,.10,.07)))
roof=bpy.data.materials.get('Metal roof')
if roof:
    color=(.46,.16,.075);roof.diffuse_color=(*color,1)
    bs=next(n for n in roof.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=.25;bs.inputs['Roughness'].default_value=.65
base=bpy.data.objects.get('Context_base')
if base:base.hide_render=True;base.hide_set(True)
cam=bpy.data.objects.get('Surroundings_Overview')
if cam is None:
    cd=bpy.data.cameras.new('Surroundings_Overview');cam=bpy.data.objects.new('Surroundings_Overview',cd);scene.collection.objects.link(cam)
cam.location=(950,-1050,850);cam.rotation_euler=(Vector((40,-180,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1500;cam.data.clip_end=5000
scene['surrounding_environment']=data['scope'];scene['surrounding_source']=data['source']
scene.camera=bpy.data.objects['Aerial_Overview']
scene.cycles.samples=24;scene.render.resolution_x=1600;scene.render.resolution_y=1100
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
pv=[o for o in scene.objects if o.name.startswith('PV_S3-')]
assert len(pv)==1500 and len({m for o in pv for m in json.loads(o['module_ids'])})==30000
(OUT/'environment_validation.json').write_text(json.dumps({'pv_groups':1500,'unique_modules':30000,'context_objects':len(coll.objects),'trees':len(data['trees']),'terrain_elevations_measured':False,'context_scope':data['scope']},indent=2),encoding='utf-8')
print('ENVIRONMENT_SAVED',flush=True)
for filename,camera in [('aerial_refined','Aerial_Overview'),('surroundings_refined','Surroundings_Overview')]:
    scene.camera=bpy.data.objects[camera];scene.render.filepath=str(OUT/(filename+'.png'));bpy.ops.render.render(write_still=True)
    print('RENDERED',filename,flush=True)

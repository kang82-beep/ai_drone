"""Add an explicitly separate, georeferenced RGB inspection area to the flying scene."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/blender_site'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan_Character.blend'))
scene=bpy.context.scene;data=json.loads((OUT/'thermal_review.json').read_text(encoding='utf-8'))
def coll(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c
base=coll('10_THERMAL_Orthomosaic_SEPARATE_COORDINATES');abnormal=coll('11_THERMAL_Abnormal_PROVISIONAL');attention=coll('12_THERMAL_Attention_PROVISIONAL')
def mat(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    node=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');node.inputs['Base Color'].default_value=(*color,1);node.inputs['Roughness'].default_value=.8
    return m
red=mat('Thermal_ABNORMAL_candidate',(1,.025,.015));orange=mat('Thermal_ATTENTION_candidate',(1,.45,.01));white=mat('Thermal_label',(.95,.95,.95))
def mesh(name,vertices,faces,material,c):
    me=bpy.data.meshes.new(name);me.from_pydata(vertices,[],faces);me.update();o=bpy.data.objects.new(name,me);c.objects.link(o);me.materials.append(material);return o
w,h=data['orthomosaic']['size_m'];x=data['orthomosaic']['offset_x']
ground=mat('Real_orthomosaic',(1,1,1));image=bpy.data.images.load(str(OUT/'thermal_orthomosaic.jpg'));image.pack()
nt=ground.node_tree;texture=nt.nodes.new('ShaderNodeTexImage');texture.image=image
bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');nt.links.new(texture.outputs['Color'],bs.inputs['Base Color'])
plane=mesh('RGB_INSPECTION_AREA_not_registered_to_drawing',[(x,0,0),(x+w,0,0),(x+w,h,0),(x,h,0)],[(0,1,2,3)],ground,base)
uv=plane.data.uv_layers.new(name='OrthomosaicUV')
for loop,coord in zip(uv.data,[(0,1),(1,1),(1,0),(0,0)]):loop.uv=coord
for candidate in data['highlight_modules']:
    p=candidate['polygon'];verts=p+[(a,b,z+.07) for a,b,z in p]
    o=mesh('RGB_CANDIDATE_'+candidate['id'],verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],red if candidate['severity']=='abnormal' else orange,abnormal if candidate['severity']=='abnormal' else attention)
    o['matching_status']='PROVISIONAL nearest RGB candidate within 0.9m; not drawing module ID'
    o['result_record_indices']=json.dumps(candidate['records'])
for index in data['navigation_order']:
    r=data['records'][index]
    if not r['position']:continue
    a,b,z=r['position']
    # A raised four-sided marker remains visible from flying height, at approximate GPS point.
    o=mesh('RESULT_'+r['module_uid'],[(a-.23,b-.23,.45),(a+.23,b-.23,.45),(a+.23,b+.23,.45),(a-.23,b+.23,.45),(a,b,2.2)],[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)],red,abnormal)
    for k in ('module_uid','image_id','matching_status','candidate_id','max_temp','delta_temp','crop','thermal'):
        if r.get(k) is not None:o[k]=r[k]
    o['record_index']=index
attention.hide_viewport=True;attention.hide_render=True
def label(text,loc,size):
    cu=bpy.data.curves.new('Thermal_Legend','FONT');cu.body=text;cu.size=size;cu.extrude=.005
    ob=bpy.data.objects.new(text[:35],cu);base.objects.link(ob);ob.location=loc;cu.materials.append(white)
label('ZONE A ONLY / THERMAL VALIDATION',(400,-13,.3),4)
label(f"{data['counts'].get('abnormal',0)} abnormal records | RED = provisional location",(400,-7,.3),2)
label('Separate coordinates from drawing model | N / P: inspect next / previous',(400,h+5,.3),2)
root=bpy.data.objects['PLAYER'];joints=[bpy.data.objects[n] for n in ('LEG_L','LEG_R','ARM_L','ARM_R')]
for ob in [root]+joints:
    ob.animation_data.action=None
if data['navigation_order']:
    first=data['records'][data['navigation_order'][0]];a,b,z=first['position'];root.location=(a,b+4,8);root.rotation_euler.z=0
else:
    root.location=(x+w/2,h/2,80)
for j in joints:j.rotation_euler.x=-.25 if j.name.startswith('ARM') else .12
scene.camera=bpy.data.objects['06_Character_follow'];scene['thermal_review_enabled']=True
scene['thermal_validation_zone']='A'
scene['thermal_summary']=f"Zone A only: {data['counts'].get('abnormal',0)} abnormal / {data['counts'].get('attention',0)} attention records. Approximate GPS; provisional RGB matches; not registered to drawing."
bpy.data.texts.new('THERMAL_REVIEW_JSON').write(json.dumps(data,ensure_ascii=False))
bpy.data.texts.new('THERMAL_README_KO').write('?? ??: A???. E?? ? ?? ??/???/?? ?? ??? ??. ?? GPS? GeoJSON ??? ?????. N/P: A?? ?? ?? ??, I: ??/?? ??. ????? ?? 3D ? ?? ?????. ?? RGB ??? ?? ?? ???? ?? ??? ?? ??? ???? ????.')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan_Thermal_Flight.blend'))
scene.render.filepath=str(OUT/'thermal_flight_preview.png')
if '--skip-render' not in sys.argv:bpy.ops.render.render(write_still=True)
cd=bpy.data.cameras.new('Thermal_overview');cd.clip_end=2500;cd.lens=38
cam=bpy.data.objects.new('Thermal_overview',cd);base.objects.link(cam);cam.location=(x+w*.5,h*.5,470);cam.rotation_euler=(0,0,0)
scene.camera=cam;scene.render.filepath=str(OUT/'thermal_overview.png')
if '--skip-render' not in sys.argv:bpy.ops.render.render(write_still=True)
print('THERMAL_FLIGHT_SAVED',len(data['navigation_order']))

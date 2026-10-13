"""Improve the editable Blender companion without changing CAD module positions.

Run: blender --background --python refine_shinan3_blender.py
Architectural detail on ER3 follows A303/A304; other rooms remain explicit proxies.
"""
from pathlib import Path
import json, math
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'results/shinan3_blender'
OUT=ROOT/'results/shinan3_refined'; OUT.mkdir(exist_ok=True)
ASSETS=ROOT/'shinan3_viewer/assets'
DATA=json.loads((SRC/'layout.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(SRC/'Shinan3_AsBuilt.blend'))
scene=bpy.context.scene
bpy.context.preferences.filepaths.save_version=0
details=bpy.data.collections.new('11_Drawing_Details_A303_A304');scene.collection.children.link(details)

def mat(name,color,metal=0,rough=.6):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    s=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED');s.inputs['Base Color'].default_value=(*color,1)
    s.inputs['Metallic'].default_value=metal;s.inputs['Roughness'].default_value=rough
    return m
steel=mat('Refined brushed galvanized metal',(.43,.46,.49),.72,.37)
trim=mat('Window painted aluminium',(.57,.60,.61),.45,.32)
glass=mat('Window dark dielectric glass',(.038,.075,.10),0,.19)
gs=next(n for n in glass.node_tree.nodes if n.type=='BSDF_PRINCIPLED');gs.inputs['Coat Weight'].default_value=.8
seam=mat('Cladding recessed seams',(.40,.43,.41),0,.7)
wall=bpy.data.materials['Electrical room wall']
concrete=bpy.data.materials['Concrete']

def texture_material(material,filename,scale=1,uv=False,normalfile=None):
    nt=material.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    for n in list(nt.nodes):
        if n.type=='TEX_IMAGE':nt.nodes.remove(n)
    coord=nt.nodes.new('ShaderNodeTexCoord')
    mapping=nt.nodes.new('ShaderNodeVectorMath');mapping.operation='SCALE';mapping.inputs[3].default_value=scale
    nt.links.new(coord.outputs['UV' if uv else 'Object'],mapping.inputs[0])
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ASSETS/filename));tex.image.pack()
    if not uv:tex.projection='BOX';tex.projection_blend=.15
    nt.links.new(mapping.outputs[0],tex.inputs['Vector']);nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    if normalfile:
        normal=nt.nodes.new('ShaderNodeTexImage');normal.image=bpy.data.images.load(str(ASSETS/normalfile));normal.image.colorspace_settings.name='Non-Color';normal.image.pack()
        normal.projection='BOX';normal.projection_blend=.15
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.03
        nt.links.new(mapping.outputs[0],normal.inputs['Vector']);nt.links.new(normal.outputs['Color'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])

pv=bpy.data.materials['PV blue glass | nominal 250W']
texture_material(pv,'panel_color.jpg',uv=True)
ps=next(n for n in pv.node_tree.nodes if n.type=='BSDF_PRINCIPLED');ps.inputs['Metallic'].default_value=0;ps.inputs['Roughness'].default_value=.3
ps.inputs['IOR'].default_value=1.5;ps.inputs['Coat Weight'].default_value=.7;ps.inputs['Coat Roughness'].default_value=.19
for name in ('Site surface | flat assumption','Array field surface | inferred extent'):
    texture_material(bpy.data.materials[name],'ground_color.jpg',.22,normalfile='ground_normal.jpg')
texture_material(concrete,'concrete_color.jpg',.5,normalfile='concrete_normal.jpg')

def mesh(name,verts,faces,material):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);details.objects.link(ob);data.materials.append(material)
    return ob
def cube(name,pos,scale,material,rotation=0,bevel=.008):
    x,y,z=[v*.5 for v in scale]
    verts=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    ob=mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],material)
    ob.location=pos;ob.rotation_euler.z=rotation
    if bevel:
        mod=ob.modifiers.new('Small manufactured edge highlights','BEVEL');mod.width=bevel;mod.segments=2
    return ob
def cylinder(name,start,end,radius,material,vertices=12):
    v=Vector(end)-Vector(start)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=v.length,location=(Vector(start)+Vector(end))/2)
    ob=bpy.context.object;ob.name=name;ob.rotation_euler=v.to_track_quat('Z','Y').to_euler();ob.data.materials.append(material)
    for c in list(ob.users_collection):c.objects.unlink(ob)
    details.objects.link(ob)
    for p in ob.data.polygons:p.use_smooth=True
    return ob
def line_mesh(name,segments,radius,material):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=0
    for a,b in segments:
        s=curve.splines.new('POLY');s.points.add(1);s.points[0].co=(*a,1);s.points[1].co=(*b,1)
    ob=bpy.data.objects.new(name,curve);details.objects.link(ob);curve.materials.append(material);return ob

for ob in list(scene.objects):
    if ob.name.startswith('S3-ER') and any(k in ob.name for k in ('Window','Canopy','LargeDoor')):
        bpy.data.objects.remove(ob,do_unlink=True)
    elif 'GableRoof' in ob.name:
        mod=ob.modifiers.new('Roof panel thickness 100mm','SOLIDIFY');mod.thickness=.1
        mod=ob.modifiers.new('Roof edge highlight','BEVEL');mod.width=.015;mod.segments=2

for b in DATA['buildings']:
    cx,cy=b['center'];a=b['rotation'];ca,sa=math.cos(a),math.sin(a);L=b['length'];W=b['width'];mid=b['id']
    def world(x,y,z):return (cx+x*ca-y*sa,cy+x*sa+y*ca,z)
    def box(label,x,y,z,w,d,h,material,angle=0):return cube(mid+'_'+label,world(x,y,z),(w,d,h),material,a+angle)
    for side in (-1,1):
        x=side*L/2
        ob=mesh(mid+'_Closed_Gable', [world(x,-W/2,4.5),world(x,W/2,4.5),world(x,0,6)],[(0,1,2)],wall)
        mod=ob.modifiers.new('Gable panel thickness','SOLIDIFY');mod.thickness=.1
        ob['evidence']='A304 closed gable; applied as proxy to ER1/ER2'
        box('HangerDoor',x+side*.08,0,2.05,.07,3.2,3.1,trim)
        for yy in (-1.67,1.67):box('DoorJamb',x+side*.13,yy,2.08,.13,.1,3.22,steel)
        box('DoorHeader',x+side*.13,0,3.68,.13,3.44,.13,steel)
        box('DoorCenterSeam',x+side*.125,0,2.05,.035,.025,3.0,seam)
        box('DoorHandle',x+side*.19,.15,1.5,.06,.035,.22,steel)
        box('DoorCanopy',x+side*.60,0,3.92,1.2,3.55,.12,steel)
        for step in range(3):box('EntranceStep',x+side*(.25+(2-step)*.3),0,(step+1)/12,.30,3.7,(step+1)/6,concrete)
        # Window next to end doorway, dimensional detailing approximate.
        for yy in (-3.2,3.2):
            box('EndWindowTrim',x+side*.09,yy,2.0,.13,1.4,1.05,trim)
            box('EndWindowGlass',x+side*.165,yy,2.0,.02,1.24,.89,glass)
            box('EndWindowMullion',x+side*.18,yy,2.0,.035,.035,.91,trim)
    for side in (-1,1):
        y=side*(W/2+.08)
        for xx in (-8,-4,0,4,8):
            for z in (2.,4.):
                if side==1 and xx==8 and z==2:continue
                box('WindowTrim',xx,y,z,1.5,.12,.95,trim)
                box('WindowGlass',xx,y+side*.073,z,1.35,.025,.80,glass)
                box('WindowMullion',xx,y+side*.092,z,.045,.04,.82,trim)
        if side==1:
            box('RearDoor',8,y,1.6,1.0,.12,2.2,trim)
            box('RearCanopy',8,y+.5,2.9,1.3,1.1,.10,steel)
        cylinder(mid+'_Gutter',world(-L/2-.2,side*(W/2+.23),4.43),world(L/2+.2,side*(W/2+.23),4.43),.09,steel)
        for xx in (-L/2+.08,L/2-.08):
            cylinder(mid+'_100mm_Downpipe',world(xx,side*(W/2+.2),.12),world(xx,side*(W/2+.2),4.45),.05,steel)
    for xx in (-8,-4,0,4):
        cylinder(mid+'_VentilatorBase',world(xx,0,6.0),world(xx,0,6.28),.27,steel)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,radius=.30,location=world(xx,0,6.48))
        ob=bpy.context.object;ob.name=mid+'_600mm_RoofVentilator';ob.scale.z=.85;ob.data.materials.append(steel)
        for coll in list(ob.users_collection):coll.objects.unlink(ob)
        details.objects.link(ob)
        for p in ob.data.polygons:p.use_smooth=True
    segments=[]
    for x in [(-L/2+i*.31) for i in range(int(L/.31)+1)]:
        for sign in (-1,1):segments.append((world(x,0,6.015),world(x,sign*(W/2+.28),4.515)))
    line_mesh(mid+'_RoofStandingSeams',segments,.018,steel)
    # Horizontal seams stay behind window panes instead of crossing the glazing.
    segments=[]
    for z in [.65+i*.16 for i in range(24)]:
        for sign in (-1,1):segments.append((world(-L/2,sign*(W/2+.061),z),world(L/2,sign*(W/2+.061),z)))
    line_mesh(mid+'_CladdingJoints',segments,.007,seam)

# Context is neutral; it is not a surveyed reconstruction of surrounding land.
base=bpy.data.objects.get('Context_base')
if base:base.data.materials.clear();base.data.materials.append(bpy.data.materials['Site surface | flat assumption'])
world=scene.world; nt=world.node_tree;nt.nodes.clear()
sky=nt.nodes.new('ShaderNodeTexSky')
sky_models=sky.bl_rna.properties['sky_type'].enum_items.keys()
sky.sky_type='MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in sky_models else 'NISHITA'
sky.sun_elevation=math.radians(38);sky.sun_rotation=math.radians(130);sky.sun_intensity=.7;sky.sun_disc=False
background=nt.nodes.new('ShaderNodeBackground');background.inputs['Strength'].default_value=.045
out=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(sky.outputs['Color'],background.inputs['Color']);nt.links.new(background.outputs[0],out.inputs[0])
bpy.data.lights['Sun'].energy=1.8;bpy.data.lights['Sun'].angle=.04
scene.cycles.samples=40;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1100
scene.camera=bpy.data.objects['Aerial_Overview']
scene['refinement']='A303/A304 architectural detail, restrained dielectric PV, packed authored PBR textures; assumptions retained.'
scene['room_specific_status']='ER3 A303/A304 details; ER1/ER2 architectural proxy requiring room-specific confirmation'
bpy.data.texts.new('REFINEMENT_SCOPE').write('CAD module coordinates and IDs unchanged. Materials are authored approximations, not scans. No completed-site photographs provided. Static Blender scene; no engineering physics simulation. ER1/ER2 repeat ER3 details as explicitly unverified proxies.')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
print('REFINED_BLEND_SAVED',flush=True)
(OUT/'refinement_manifest.json').write_text(json.dumps({'source_dwg_sha256':DATA['source_sha256'],'module_count':30000,'group_count':1500,'room_count':3,'new_detail_objects':len(details.objects),'scope':scene['refinement'],'room_specific_status':scene['room_specific_status'],'assumptions':DATA['assumptions']},ensure_ascii=False,indent=2),encoding='utf-8')
for name,camera in [('building_refined','Electrical_Room_Detail'),('module_refined','PV_Detail'),('aerial_refined','Aerial_Overview')]:
    scene.camera=bpy.data.objects[camera];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    print('RENDERED',name,flush=True)

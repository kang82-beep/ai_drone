"""Build a portable, editable phase-3 scene from extracted CAD groups. Run in Blender."""
from pathlib import Path
import sys,json,math,hashlib
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_blender'
DATA=json.loads((OUT/'layout.json').read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
bpy.context.preferences.filepaths.save_version=0

def collection(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c

def material(name,color,metal=0,roughness=.6):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Metallic'].default_value=metal;shader.inputs['Roughness'].default_value=roughness
    return m

M={
 'panel':material('PV blue glass | nominal 250W',(.025,.105,.19),.35,.27),
 'frame':material('Aluminium frames',(.50,.56,.61),.75,.34),
 'steel':material('Galvanized structure | schematic',(.33,.39,.42),.6,.45),
 'concrete':material('Concrete',(.52,.53,.49)),
 'ground':material('Site surface | flat assumption',(.28,.27,.22)),
 'field':material('Array field surface | inferred extent',(.24,.30,.16)),
 'wall':material('Electrical room wall',(.79,.81,.78)),
 'roof':material('Metal roof',(.19,.25,.29),.4,.5),
 'window':material('Windows',(.10,.25,.32),.3,.25),
 'door':material('Doors',(.27,.35,.38),.3,.45),
 'line':material('CAD reference lines',(.04,.55,.65)),
 'text':material('Labels',(.12,.20,.24)),
}
panels=collection('01_PV_Modules_30000_CAD')
frames=collection('02_Aluminium_Frames')
supports=collection('03_Supports_ASSUMED_DETAILS')
foundations=collection('04_Foundations_9x1p9_C031')
ground=collection('05_Site_and_Field_Surfaces')
shell=collection('06_Electrical_Rooms_3')
roofs=collection('07_Roofs_HIDE_FOR_INTERIOR')
reference=collection('08_CAD_Plan_Reference')
labels=collection('09_Labels')
cameras=collection('10_Cameras_and_Lighting')

FACES=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]

def mesh_object(name,verts,faces,mat,coll):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);coll.objects.link(ob);mesh.materials.append(mat);return ob

def box_geometry(x,y,z,w,d,h):
    return [(x,y,z),(x+w,y,z),(x+w,y+d,z),(x,y+d,z),
            (x,y,z+h),(x+w,y,z+h),(x+w,y+d,z+h),(x,y+d,z+h)],FACES

def add_box(vv,ff,*args):
    v,f=box_geometry(*args);offset=len(vv);vv.extend(v);ff.extend(tuple(offset+i for i in face) for face in f)

def box(name,xyz,size,mat,coll,rotation=0):
    v,f=box_geometry(-size[0]/2,-size[1]/2,0,*size)
    ob=mesh_object(name,v,f,mat,coll);ob.location=xyz;ob.rotation_euler.z=rotation;return ob

def line_object(name,lines,width,mat,coll,z=0):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=width;curve.bevel_resolution=0
    for line in lines:
        spline=curve.splines.new('POLY');spline.points.add(len(line)-1)
        for p,xy in zip(spline.points,line):p.co=(xy[0],xy[1],z,1)
    ob=bpy.data.objects.new(name,curve);coll.objects.link(ob);curve.materials.append(mat);return ob

def label(name,text,location,size=2,rotation=0):
    curve=bpy.data.curves.new(name,'FONT');curve.body=text;curve.size=size;curve.align_x='CENTER'
    ob=bpy.data.objects.new(name,curve);labels.objects.link(ob);curve.materials.append(M['text']);ob.location=location;ob.rotation_euler.z=rotation
    return ob

# Shared geometry keeps 30,000 modules editable without 30,000 independent draw objects.
slope=math.tan(math.radians(30));depth=1.425;low=.8;thickness=.042
pv_v=[];pv_f=[];face_module=[];frame_v=[];frame_f=[]
for row in range(2):
    for col in range(10):
        x=col*1.008;y=row*depth;w=.983
        corners=[(x,y),(x+w,y),(x+w,y+depth),(x,y+depth)]
        top=[(a,b,low+b*slope) for a,b in corners]
        bottom=[(a,b,c-thickness) for a,b,c in top]
        off=len(pv_v);pv_v.extend(bottom+top);pv_f.extend(tuple(off+i for i in f) for f in FACES)
        face_module.extend([row*10+col]*6)
        for side in range(4):
            a=top[side];b=top[(side+1)%4]
            # Narrow flat frame strips at module perimeter; not a structural section model.
            if side in (0,2):
                yy=min(a[1],b[1]) + (0 if side==0 else -.018)
                poly=[(x,yy),(x+w,yy),(x+w,yy+.018),(x,yy+.018)]
            else:
                xx=x+w-.018 if side==1 else x
                poly=[(xx,y),(xx+.018,y),(xx+.018,y+depth),(xx,y+depth)]
            start=len(frame_v);frame_v.extend((a,b,low+b*slope+.002) for a,b in poly);frame_f.append(tuple(start+i for i in range(4)))
template=mesh_object('PV_20_MODULE_TEMPLATE',pv_v,pv_f,M['panel'],panels)
attribute=template.data.attributes.new('module_local_index','INT','FACE');attribute.data.foreach_set('value',face_module)
# UVs work with both Blender and exported glTF. An illustrative cell grid is baked to a small texture.
uv=template.data.uv_layers.new(name='ModuleUV')
for poly in template.data.polygons:
    local=face_module[poly.index];r,c=divmod(local,10)
    for li in poly.loop_indices:
        vertex=template.data.vertices[template.data.loops[li].vertex_index].co
        uv.data[li].uv=((vertex.x-c*1.008)/.983,(vertex.y-r*depth)/depth)
texture_path=OUT/'pv_cells.png'
if texture_path.is_file():
    im=bpy.data.images.load(str(texture_path));im.pack()
    tex=M['panel'].node_tree.nodes.new('ShaderNodeTexImage');tex.image=im
    M['panel'].node_tree.links.new(tex.outputs['Color'],M['panel'].node_tree.nodes['Principled BSDF'].inputs['Base Color'])
frame_template=mesh_object('FRAME_TEMPLATE',frame_v,frame_f,M['frame'],frames)

sv=[];sf=[]
for x in (.75,3.60,6.45,9.30):
    for y in (.675,2.175):
        add_box(sv,sf,x-.04,y-.04,.30,.08,.08,low+y*slope-.35)
for y in (.675,2.175):add_box(sv,sf,.55,y-.045,low+y*slope-.12,8.95,.09,.08)
support_template=mesh_object('SUPPORT_TEMPLATE',sv,sf,M['steel'],supports)
fv,ff=box_geometry(.5275,.475,0,9,1.9,.3)
foundation_template=mesh_object('FOUNDATION_TEMPLATE',fv,ff,M['concrete'],foundations)
base_meshes=[template.data,frame_template.data,support_template.data,foundation_template.data]
for ob in [template,frame_template,support_template,foundation_template]:bpy.data.objects.remove(ob,do_unlink=True)
for g in DATA['groups']:
    x,y,x1,y1=g['bounds']
    assert abs((x1-x)-10.055)<.001 and abs((y1-y)-2.85)<.001
    for prefix,mesh,coll in zip(['PV','FRAME','SUPPORT','FOUNDATION'],base_meshes,[panels,frames,supports,foundations]):
        ob=bpy.data.objects.new(prefix+'_'+g['id'],mesh);coll.objects.link(ob);ob.location=(x,y,0)
        ob['group_id']=g['id'];ob['cad_insert_handle']=g['cad_handle'];ob['source_drawing']='3SA-E-11210_C'
        if prefix=='PV':
            ob['module_ids']=json.dumps([f"{g['id']}-R{r+1}-M{c+1:02}" for r in range(2) for c in range(10)])
            ob['rated_w_per_module']=250;ob['tilt_deg']=30;ob['analysis_link_status']='unlinked'
        if prefix=='SUPPORT':ob['geometry_status']='support sizes/low edge assumed; see README'
print('PV_GROUPS_CREATED',len(DATA['groups']),flush=True)

boundary=DATA['boundary']
base=mesh_object('SITE_FOOTPRINT_from_CAD',[(x,y,-.06) for x,y in boundary],[tuple(range(len(boundary)))],M['ground'],ground)
base['source_layer']='P-신청지';base['elevation_status']='flat ground assumption'
vv=[];ff=[]
for tri in DATA['field_triangles']:
    start=len(vv);vv.extend((x,y,-.035) for x,y in tri);ff.append((start,start+1,start+2))
fields=mesh_object('ARRAY_FIELDS_inferred_buffer',vv,ff,M['field'],ground)
fields['extent_status']='buffered module envelopes; not measured paving boundaries'
line_object('CAD_SITE_BOUNDARY',[boundary+[boundary[0]]],.11,M['concrete'],ground,.05)
box('Context_base',(170,-220,-1.1),(440,530,1),M['concrete'],ground)

for b in DATA['buildings']:
    cx,cy=b['center'];a=b['rotation'];co,si=math.cos(a),math.sin(a)
    def world(x,y,z):return (cx+x*co-y*si,cy+x*si+y*co,z)
    L=b['length'];W=b['width'];mid=b['id']
    floor=box(mid+'_Floor',world(0,0,0),(L,W,.5),M['concrete'],shell,a)
    floor['source']='Electrical plan plus architectural floor height'
    for xx,yy,ww,dd in [(0,-W/2,L,.12),(0,W/2,L,.12),(-L/2,0,.12,W),(L/2,0,.12,W)]:
        box(mid+'_Wall',world(xx,yy,.5),(ww,dd,4),M['wall'],shell,a)
    vertices=[world(-L/2-.3,-W/2-.3,4.5),world(L/2+.3,-W/2-.3,4.5),world(L/2+.3,0,6),world(-L/2-.3,0,6),
              world(-L/2-.3,W/2+.3,4.5),world(L/2+.3,W/2+.3,4.5)]
    roof=mesh_object(mid+'_GableRoof',vertices,[(0,1,2,3),(3,2,5,4)],M['roof'],roofs)
    roof['source']='Civil/architecture PDF p125-128; verify room-specific details'
    for side in (-1,1):
        box(mid+'_LargeDoor',world(side*(L/2+.07),0,.5),(.05,3.2,3.1),M['door'],shell,a)
        for yy in (-3.2,3.2):box(mid+'_Window',world(side*(L/2+.075),yy,1.5),(.06,1.2,1.1),M['window'],shell,a)
        # Visible canopy is a simplified representation, not detailed fabrication geometry.
        box(mid+'_Canopy',world(side*(L/2+2.0),0,3.7),(4,4.2,.09),M['roof'],roofs,a)
    for xx in (-8,-4,0,4,8):
        box(mid+'_SideWindow',world(xx,-W/2-.07,1.8),(1.35,.06,1.0),M['window'],shell,a)
    label(mid+'_Label',mid,world(0,-W/2-3,.05),1.8,a)
    plan=line_object(mid+'_Original_CAD_Plan',b['plan_lines'],.012,M['line'],reference,.505)
    plan['source_block']=b['cad_block']
reference.hide_render=True

label('Title','SHINAN 3  /  7.5 MWp',(175,-485,.02),7)
label('Subtitle','30,000 PV MODULES  |  AS-BUILT CAD LAYOUT',(175,-497,.02),3)
label('NorthMark','N',(390,-10,.1),4)
line_object('NorthArrow',[[(390,-32),(390,-16)],[(386,-21),(390,-16),(394,-21)]],.22,M['text'],labels,.1)

def camera(name,position,target,lens=45,ortho=None):
    data=bpy.data.cameras.new(name);ob=bpy.data.objects.new(name,data);cameras.objects.link(ob)
    ob.location=position;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
    data.lens=lens;data.clip_end=5000
    if ortho:data.type='ORTHO';data.ortho_scale=ortho
    return ob
overview=camera('Aerial_Overview',(640,-850,610),(175,-220,0),48,610)
top=camera('CAD_Top_Check',(175,-220,900),(175,-220,0),ortho=550)
top.rotation_euler=(0,0,0)
g=DATA['groups'][600];x,y,_,_=g['bounds']
detail=camera('PV_Detail',(x+18,y-17,12),(x+5,y+1.4,1.3),42)
b=DATA['buildings'][1];cx,cy=b['center']
building_cam=camera('Electrical_Room_Detail',(cx+29,cy-30,20),(cx,cy,2.3),45)
sun_data=bpy.data.lights.new('Sun','SUN');sun_data.energy=2.2;sun_data.angle=.12
sun=bpy.data.objects.new('Sun',sun_data);cameras.objects.link(sun);sun.rotation_euler=(.45,-.5,-.65)
scene.world=bpy.data.worlds.new('Shinan3 daylight')
scene.world.color=(.24,.27,.31)
world=scene.world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.6,.7,.85,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
scene.camera=overview
scene.render.engine='CYCLES';scene.cycles.samples=20;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
scene['site']='Shinan phase 3 (separate from previous phase model)'
scene['module_count']=30000;scene['capacity_kwp']=7500
scene['source_dwg_sha256']=DATA['source_sha256']
scene['assumptions']=json.dumps(DATA['assumptions'],ensure_ascii=False)
scene['coordinate_system']=DATA['coordinate_transform']
for name,payload in [('SHINAN3_MODULE_CATALOG',DATA['modules']),('SHINAN3_SOURCE_AND_ASSUMPTIONS',{k:v for k,v in DATA.items() if k not in ['modules','groups','field_triangles']})]:
    text=bpy.data.texts.new(name);text.write(json.dumps(payload,ensure_ascii=False,indent=1))
readme=OUT/'README.md'
if readme.is_file():bpy.data.texts.new('README_KO').write(readme.read_text(encoding='utf-8'))
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.clip_end=5000
        area.spaces.active.region_3d.view_distance=650
        area.spaces.active.region_3d.view_location=(175,-220,0)
        area.spaces.active.region_3d.view_rotation=overview.rotation_euler.to_quaternion()
        area.spaces.active.shading.type='MATERIAL'
        area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_AsBuilt.blend'))
print('BLEND_SAVED',flush=True)
# Export only production geometry; native cameras/reference drawings remain in .blend.
bpy.ops.object.select_all(action='DESELECT')
for coll in [panels,frames,supports,foundations,ground,shell,roofs]:
    for ob in coll.objects:ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Shinan3_AsBuilt.glb'),export_format='GLB',use_selection=True,
                          export_extras=True,export_cameras=False,export_lights=False,export_animations=False)
print('GLB_SAVED',flush=True)
report={'module_count':30000,'group_count':1500,'building_count':3,'capacity_kwp':7500,
        'source_sha256':DATA['source_sha256'],'objects':len(scene.objects),'assumptions':DATA['assumptions']}
(OUT/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for cam,name in [(overview,'aerial_preview'),(detail,'module_detail'),(building_cam,'building_detail')]:
    scene.camera=cam;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    print('RENDERED',name,flush=True)

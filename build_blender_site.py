"""Run with Blender --background --python build_blender_site.py.
Creates a self-contained, grouped native scene for first-person exploration.
"""
import sys,math,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from pv_inspector.site_model import load_site
from pv_inspector.site_structures import buildings,building_parts,raised_modules,module_frames,supports,COLORS,SHELL_KINDS
from pv_inspector.cable_routes import all_routes,route_parts
from pv_inspector.circuit_model import build_network,field_parts
from pv_inspector.site_landscape import landscape_parts,road_rectangles,ROAD_SOURCE

OUT=ROOT/'results'/'blender_site';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.fps=24;scene.frame_start=1;scene.frame_end=1440
scene.world=bpy.data.worlds.new('Daylight');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.48,.65,.84,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
COLORS.update(ground='#727951',concrete_road='#b5b3a4',road_joint='#747769',drain='#454b48')
materials={}
for kind,color in COLORS.items():
    mat=bpy.data.materials.new(kind);mat.use_nodes=True
    rgb=tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
    # Hex swatches are sRGB; node colors are scene linear.
    rgba=tuple(((c+.055)/1.055)**2.4 if c>.04045 else c/12.92 for c in rgb)+(1,)
    mat.diffuse_color=rgba;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=rgba
    bs.inputs['Roughness'].default_value=.8 if kind in ('ground','concrete_road','foundation') else .45
    if kind in ('steel','frame','tray','tray_cover','roof_metal'):bs.inputs['Metallic'].default_value=.7
    if kind=='module':
        bs.inputs['Metallic'].default_value=.15;bs.inputs['Roughness'].default_value=.38
        nt=mat.node_tree;tex=nt.nodes.new('ShaderNodeTexCoord');sep=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(tex.outputs['UV'],sep.inputs[0])
        fractions=[]
        for axis,count in [('X',6),('Y',10)]:
            mul=nt.nodes.new('ShaderNodeMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=count;nt.links.new(sep.outputs[axis],mul.inputs[0])
            fract=nt.nodes.new('ShaderNodeMath');fract.operation='FRACT';nt.links.new(mul.outputs[0],fract.inputs[0]);fractions.append(fract)
        minimum=nt.nodes.new('ShaderNodeMath');minimum.operation='MINIMUM'
        for i,n in enumerate(fractions):nt.links.new(n.outputs[0],minimum.inputs[i])
        line=nt.nodes.new('ShaderNodeMath');line.operation='LESS_THAN';line.inputs[1].default_value=.025;nt.links.new(minimum.outputs[0],line.inputs[0])
        mix=nt.nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.016,.038,.075,1);mix.inputs[2].default_value=(.22,.26,.30,1)
        nt.links.new(line.outputs[0],mix.inputs[0]);nt.links.new(mix.outputs[0],bs.inputs['Base Color'])
    if kind in ('ground','concrete_road'):
        nt=mat.node_tree;noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=4 if kind=='ground' else 26
        tex=nt.nodes.new('ShaderNodeTexCoord');nt.links.new(tex.outputs['Object'],noise.inputs['Vector'])
        bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.06 if kind=='ground' else .012
        nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal'])
        ramp=nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color=tuple(c*.65 for c in rgba[:3])+(1,)
        ramp.color_ramp.elements[1].color=rgba
        nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);nt.links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
    materials[kind]=mat

def collection(name):
    c=bpy.data.collections.new(name);scene.collection.children.link(c);return c

def add_group(parts,name):
    """Batch by material to avoid 200k individual objects slowing navigation."""
    c=collection(name);batches={}
    for p in parts:
        vv,ff,ids=batches.setdefault(p['kind'],([],[],[]));offset=len(vv)
        vv.extend(p['vertices']);ff.extend(tuple(offset+i for i in f) for f in p['faces']);ids.append(p['id'])
    for kind,(verts,faces,ids) in batches.items():
        mesh=bpy.data.meshes.new(name+'-'+kind);mesh.from_pydata(verts,[],faces);mesh.update()
        if kind=='module':
            uv=mesh.uv_layers.new(name='ModuleCellGrid')
            corners=[(0,0),(1,0),(1,1),(0,1)]
            for loop in mesh.loops:uv.data[loop.index].uv=corners[loop.vertex_index%4]
        obj=bpy.data.objects.new(name+'-'+kind,mesh);c.objects.link(obj);obj.data.materials.append(materials[kind])
        obj['component_count']=len(ids);obj['provenance']='Drawing + photo-informed geometry; see embedded README and network JSON'
    print('BUILT',name,len(batches),flush=True)
    return c

data=load_site();bs=buildings(data);net=build_network(data)
for lane in range(1,5):
    rr=[r for r in data['rows'] if r['lane']==lane]
    add_group((p for r in rr for p in raised_modules(r)),f'01_Modules_L{lane}')
    add_group((p for r in rr for p in module_frames(raised_modules(r))),f'02_Frames_L{lane}')
    add_group((p for r in rr for p in supports(r)),f'03_Supports_L{lane}')
for b in bs:
    parts=building_parts(b)
    add_group((p for p in parts if p['kind'] in SHELL_KINDS),b['id']+'_Shell_HIDE_TO_INSPECT')
    add_group((p for p in parts if p['kind'] not in SHELL_KINDS),b['id']+'_Interior')
add_group(field_parts(net),'04_Field_Junctions')
add_group((p for r in all_routes(data) for p in route_parts(r,detail=False)),'05_Cable_Containment')
add_group(landscape_parts(),'06_Ground_Roads_Drains')

lights=collection('07_Lighting')
ld=bpy.data.lights.new('Sun','SUN');ld.energy=2.4;ld.angle=math.radians(10)
sun=bpy.data.objects.new('Sun',ld);lights.objects.link(sun);sun.rotation_euler=(.5,-.4,-.5)
cameras=collection('08_Tour_Cameras')
def camera(name,pos,target,lens=28):
    cd=bpy.data.cameras.new(name);cd.lens=lens;cd.clip_start=.05;cd.clip_end=2500
    ob=bpy.data.objects.new(name,cd);cameras.objects.link(ob);ob.location=pos
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();return ob
overview=camera('01_Aerial_overview',(450,470,330),(165,140,0),36)
walk=camera('02_Walk_start',(172.16,287,1.75),(172.16,230,1.6),24)
room=camera('03_Electrical_room',(182,170,1.75),(195,184,2),24)
detail=camera('04_Array_and_tray',(165,169.8,1.75),(158,163,1.3),24)
tour=camera('05_Automatic_tour',(172.16,287,1.75),(172.16,260,1.65),24)
# Ground-level corridor tour. Turns happen while stopped at the clear cross-road.
keys=[(1,(172.16,287,1.75),(172.16,245,1.65)),(480,(172.16,170.5,1.75),(172.16,120,1.65)),
      (576,(172.16,170.5,1.75),(220,170.5,1.65)),(864,(245,170.5,1.75),(265,170.5,1.65)),
      (960,(245,170.5,1.75),(172.16,170.5,1.65)),(1248,(172.16,170.5,1.75),(125,170.5,1.65)),
      (1344,(172.16,170.5,1.75),(172.16,120,1.65)),(1440,(172.16,135,1.75),(172.16,100,1.65))]
for frame,pos,target in keys:
    tour.location=pos;tour.rotation_euler=(Vector(target)-tour.location).to_track_quat('-Z','Y').to_euler()
    tour.keyframe_insert(data_path='location',frame=frame);tour.keyframe_insert(data_path='rotation_euler',frame=frame)
# Use linear motion to stay within the road instead of Bezier overshoot.
if tour.animation_data and tour.animation_data.action:
    action=tour.animation_data.action
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for k in fc.keyframe_points:k.interpolation='LINEAR'
scene.camera=tour;scene.frame_set(1)
for name,frame in [('START - main road',1),('TURN - cross road',480),('EAST arrays',864),('RETURN',960),('NORTH',1344)]:scene.timeline_markers.new(name,frame=frame)
scene['model_limitations']='Flat terrain; roads inferred within drawing gaps; photos inform appearance, not photogrammetry. Network connections are logical, not as-built wiring.'
scene['source_module_count']=20420;scene['road_source']=ROAD_SOURCE
scene['walk_controls']='View > Navigation > Walk Navigation; WASD, mouse; Esc to exit. Numpad 0 then Space plays 60-second tour.'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            space=area.spaces.active;space.clip_end=2500;space.clip_start=.05
            space.shading.type='SOLID';space.shading.color_type='MATERIAL';space.overlay.show_overlays=False
            space.region_3d.view_perspective='CAMERA'
readme='''신안 발전소 Blender 산책 모델

파일을 열면 지상 1.75m 시점의 순회 카메라가 선택됩니다.
Space: 60초 카메라 순회 재생/정지. Numpad 0: 카메라 보기.
자유 탐색: View > Navigation > Walk Navigation. WASD 이동, 마우스 둘러보기, Esc 종료.
카메라 애니메이션을 보존하려면 자유 탐색 전에 Numpad 0으로 카메라 보기에서 나옵니다.
조감도: Outliner에서 01_Aerial_overview 선택 후 Ctrl+Numpad 0.
전기실 내부: ER-01/02_Shell_HIDE_TO_INSPECT 컬렉션의 눈 아이콘을 끕니다.
성능을 위해 동일 구획/재질 메시를 묶었습니다. 원래 개별 모듈 ID는 원본 OBJ와 회로 JSON에 있습니다.
도로: 사진 5923~5929의 콘크리트 관리도로와 배수로 외형, p.14 배열 사이 공간에 정합.
실측 지형, 도로 경계/배수관 연결/구배는 미확정입니다. 사진측량 모델이 아닙니다.
'''
bpy.data.texts.new('READ_ME_KO').write(readme)
bpy.data.texts.new('electrical_network.json').write(json.dumps(net,ensure_ascii=False,indent=2))
for p in sorted((ROOT/'tmp'/'photos').glob('contact-*.jpg')):
    image=bpy.data.images.load(str(p));image.name='REFERENCE_'+p.stem;image.use_fake_user=True;image.pack()
scene.render.filepath=str(OUT/'walk_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan_Plant_Walkthrough.blend'))
# Render a ground-level and aerial review; keep the saved file at the start of the tour.
for cam,filename in [(walk,'walk_preview.png'),(overview,'aerial_preview.png')]:
    scene.camera=cam;scene.render.filepath=str(OUT/filename)
    bpy.ops.render.render(write_still=True)
report={'blend':'Shinan_Plant_Walkthrough.blend','module_count':20420,'objects':len(scene.objects),'vertices':sum(len(o.data.vertices) for o in scene.objects if o.type=='MESH'),'roads':road_rectangles(),'road_source':ROAD_SOURCE,'cameras':[o.name for o in cameras.objects],'tour_frames':1440,'fps':24,'limitations':scene['model_limitations']}
(OUT/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('BLENDER_BUILD_COMPLETE',flush=True)

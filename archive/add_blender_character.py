"""Add a stylized inspector and third-person camera to the saved plant scene."""
import bpy,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/blender_site'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan_Plant_Walkthrough.blend'))
scene=bpy.context.scene
coll=bpy.data.collections.new('09_Inspector_Character');scene.collection.children.link(coll)
def material(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(*color,1)
    return m
mats={k:material('Worker_'+k,c) for k,c in {'vest':(1,.3,.025),'navy':(.025,.06,.12),'skin':(.55,.32,.19),'helmet':(1,.75,.025),'boots':(.025,.028,.03),'reflective':(.8,.85,.7)}.items()}
def empty(name,parent=None,pos=(0,0,0)):
    ob=bpy.data.objects.new(name,None);coll.objects.link(ob);ob.parent=parent;ob.location=pos;return ob
root=empty('PLAYER');joints=[]
def shape(name,pos,scale,mat,parent=root,sphere=False):
    if sphere:bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8)
    else:bpy.ops.mesh.primitive_cube_add()
    ob=bpy.context.object;ob.name=name
    for c in list(ob.users_collection):c.objects.unlink(ob)
    coll.objects.link(ob);ob.parent=parent;ob.location=pos;ob.scale=scale;ob.data.materials.append(mats[mat]);return ob
shape('Vest',(0,0,1.2),(.24,.145,.32),'vest')
shape('Belt',(0,0,.91),(.235,.15,.04),'navy')
shape('Head',(0,-.02,1.65),(.14,.13,.17),'skin',sphere=True)
shape('Helmet',(0,-.02,1.78),(.18,.17,.11),'helmet',sphere=True)
shape('Helmet_brim',(0,-.04,1.74),(.21,.20,.015),'helmet')
shape('Nose',(0,-.15,1.65),(.03,.035,.04),'skin',sphere=True)
for x in [-.15,.15]:shape('Reflective_vertical',(x,-.15,1.23),(.026,.007,.24),'reflective');shape('Reflective_back',(x,.15,1.23),(.026,.007,.24),'reflective')
shape('Reflective_waist',(0,0,1.05),(.245,.155,.025),'reflective')
for side,x in [('L',-.13),('R',.13)]:
    leg=empty('LEG_'+side,root,(x,0,.9));joints.append(leg)
    shape('Trouser_'+side,(0,0,-.36),(.095,.10,.37),'navy',leg)
    shape('Boot_'+side,(0,-.07,-.81),(.105,.17,.09),'boots',leg)
for side,x in [('L',-.31),('R',.31)]:
    arm=empty('ARM_'+side,root,(x,0,1.43));joints.append(arm)
    shape('Sleeve_'+side,(0,0,-.23),(.072,.08,.24),'navy',arm)
    shape('Hand_'+side,(0,0,-.5),(.065,.075,.08),'skin',arm,sphere=True)
camdata=bpy.data.cameras.new('Character_follow');camdata.lens=28;camdata.clip_start=.05;camdata.clip_end=2000
cam=bpy.data.objects.new('06_Character_follow',camdata);coll.objects.link(cam);cam.parent=root;cam.location=(0,4.3,2.7)
cam.rotation_euler=(Vector((0,-2,1.1))-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
tour=bpy.data.objects['05_Automatic_tour'];last=None;distance=0
for frame in list(range(1,1441,4))+[1440]:
    scene.frame_set(frame);pos=tour.location.copy();pos.z=.08
    if last is not None:distance+=(pos-last).length
    # Copy heading from the original camera's horizontal forward direction.
    forward=tour.rotation_euler.to_quaternion()@Vector((0,0,-1))
    angle=math.atan2(forward.x,-forward.y)
    if frame>1:
        while angle-root.rotation_euler.z>math.pi:angle-=2*math.pi
        while angle-root.rotation_euler.z< -math.pi:angle+=2*math.pi
    root.location=pos;root.rotation_euler.z=angle
    root.keyframe_insert(data_path='location',frame=frame);root.keyframe_insert(data_path='rotation_euler',frame=frame)
    moving=last is None or (pos-last).length>.001
    phase=distance*2*math.pi/1.4
    for j in joints:
        sign=1 if j.name in ('LEG_L','ARM_R') else -1
        j.rotation_euler.x=math.sin(phase)*.42*sign if moving else 0
        j.keyframe_insert(data_path='rotation_euler',frame=frame)
    last=pos.copy()
for ob in [root]+joints:
    for layer in ob.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for k in fc.keyframe_points:k.interpolation='LINEAR'
scene.frame_set(1)
scene['character_controls']='Open_Character.bat: WASD move, Left/Right turn, Shift faster, Esc exit. Space tour in ordinary blend opening.'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.data.texts.new('CHARACTER_README').write('캐릭터 순회: Space. 직접 조작: Open_Character.bat 실행. WASD 이동, 좌우 방향키 회전, Shift 빠르게, Esc 종료. 단순 충돌 영역으로 배열과 건물을 통과하지 않게 합니다. 문 열기/실내 진입은 미구현. 캐릭터는 현장 작업자를 나타내는 창작 형상입니다.')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan_Character.blend'))
scene.render.filepath=str(OUT/'character_preview.png');bpy.ops.render.render(write_still=True)
print('CHARACTER_SAVED')

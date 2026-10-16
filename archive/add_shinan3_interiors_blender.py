"""Import the shared room GLB; preserve old shells in hidden reference collections."""
from pathlib import Path
import json, math
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_refined'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
previous=bpy.data.collections.get('14_Walkable_Electrical_Rooms')
if previous:
    for ob in list(previous.objects):bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(previous)
for name in ['06_Electrical_Rooms_3','07_Roofs_HIDE_FOR_INTERIOR','11_Drawing_Details_A303_A304']:
    coll=bpy.data.collections.get(name)
    if coll:
        coll.hide_render=True;coll.hide_viewport=True
        coll['status']='Previous exterior reference; replaced by 14_Walkable_Electrical_Rooms'
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(OUT/'Shinan3_Interiors.glb'))
objects=set(bpy.data.objects)-before
coll=bpy.data.collections.new('14_Walkable_Electrical_Rooms');scene.collection.children.link(coll)
for ob in objects:
    for parent in list(ob.users_collection):parent.objects.unlink(ob)
    coll.objects.link(ob)
    if ob.type=='LIGHT':
        ob.hide_render=False;ob.hide_viewport=False;ob.data.energy=450;ob.data.shadow_soft_size=.45
        ob['lighting_status']='450 W Blender preview fill; inferred visual lighting, not electrical rating'
    if ob.name.startswith('S3-ER') and ob.type=='EMPTY' and ('east' in ob.name or 'west' in ob.name or 'monitor' in ob.name):
        ob['interaction']='Rotate local Z axis (imported hinge); live collision and E key are in ThreeJS only'
for image in bpy.data.images:
    if image.source=='FILE' and not image.packed_file:
        try:image.pack()
        except RuntimeError:pass
layout=json.loads((ROOT/'shinan3_viewer/assets/layout.json').read_text(encoding='utf-8'))
room=layout['buildings'][1];cx,cy=room['center'];a=room['rotation']
def world(x,z,h):return Vector((cx+x*math.cos(a)+z*math.sin(a),cy+x*math.sin(a)-z*math.cos(a),h))
camera_data=bpy.data.cameras.new('Interior_Aisle_Camera');camera=bpy.data.objects.new('Interior_Aisle_Camera',camera_data);coll.objects.link(camera)
camera.location=world(9.1,-.6,2.2);target=world(-6,-.6,2)
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.lens=24;camera_data.clip_start=.08
scene['interior_update']='Shared ThreeJS GLB: 3 room shells, 62 equipment IDs, 6 exterior doors, ER1 monitoring room and door. Finishes and hardware inferred. Browser provides live door collision.'
text=bpy.data.texts.get('INTERIOR_SCOPE') or bpy.data.texts.new('INTERIOR_SCOPE')
text.clear();text.write(scene['interior_update']+'\nPrevious exterior collections are retained but hidden. Static surfaces are merged by material; equipment IDs retain named parent nodes. GLB uses CAD local metres. Door hinge empties can be rotated manually; no Blender game controls are installed.')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
report={'imported_objects':len(objects),'room_roots':[o.name for o in objects if 'walkable interior' in o.name],'door_hinges':[o.name for o in objects if o.type=='EMPTY' and any(o.name.startswith(r['id']+'-'+suffix) for r in layout['buildings'] for suffix in ['east','west','monitor'])],'mesh_count':sum(o.type=='MESH' for o in objects),'source_glb_bytes':(OUT/'Shinan3_Interiors.glb').stat().st_size,'walk_controls':'ThreeJS only','photos_matched':False}
(OUT/'interior_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))

"""Second visual review correction; retain geometry and packed dependencies."""
from pathlib import Path
import bpy,json
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_refined'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
scene=bpy.context.scene
bpy.context.preferences.filepaths.save_version=0
for n in scene.world.node_tree.nodes:
    if n.type=='BACKGROUND':n.inputs['Strength'].default_value=.065
    if n.type=='TEX_SKY':n.sun_disc=False
scene.view_settings.exposure=.25
sun=bpy.data.objects.get('Sun')
sun.rotation_euler=(-Vector((.6,-.8,1.2))).to_track_quat('-Z','Y').to_euler()
sun.data.energy=2.4
for m in bpy.data.materials:
    if not m.use_nodes:continue
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image and n.image.name.startswith('panel_color'):
            n.image=bpy.data.images.load(str(ROOT/'shinan3_viewer/assets/panel_color.jpg'));n.image.pack()
scene.camera=bpy.data.objects['Aerial_Overview']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
pv=[o for o in scene.objects if o.name.startswith('PV_S3-')]
ids=[mid for o in pv for mid in json.loads(o['module_ids'])]
assert len(pv)==1500 and len(ids)==len(set(ids))==30000
assert all(len(o.data.polygons)==120 for o in pv)
assert all(o.data.attributes.get('module_local_index') is not None for o in pv)
assert len([o for o in scene.objects if 'Closed_Gable' in o.name])==6
assert len([o for o in scene.objects if '600mm_RoofVentilator' in o.name])==12
images=[im for im in bpy.data.images if im.source=='FILE' and im.users>0]
assert all(im.packed_file for im in images)
(OUT/'validation.json').write_text(json.dumps({'reopened_blend':True,'pv_groups':len(pv),'unique_module_ids':len(set(ids)),'closed_gables':6,'roof_ventilators':12,'all_used_texture_images_packed':True,'texture_image_count':len(images)},indent=2),encoding='utf-8')
print('VALIDATION_PASSED',flush=True)
for name,camera in [('building_refined','Electrical_Room_Detail'),('module_refined','PV_Detail'),('aerial_refined','Aerial_Overview')]:
    scene.camera=bpy.data.objects[camera];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    print('RENDERED',name,flush=True)

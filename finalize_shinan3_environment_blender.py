from pathlib import Path
import json
import bpy
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_refined'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
bpy.context.preferences.filepaths.save_version=0
data=json.loads((ROOT/'shinan3_viewer/assets/environment.json').read_text(encoding='utf-8'))
for item in data['meshes']:
    ob=bpy.data.objects[item['name']]
    assert len(ob.data.vertices)==len(item['vertices'])
    ob.data.vertices.foreach_set('co',[c for v in item['vertices'] for c in v])
    ob.data.update()
scene=bpy.context.scene
scene.camera=bpy.data.objects['Aerial_Overview']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
for filename,camera in [('aerial_refined','Aerial_Overview'),('surroundings_refined','Surroundings_Overview'),('building_refined','Electrical_Room_Detail'),('module_refined','PV_Detail')]:
    scene.camera=bpy.data.objects[camera]
    scene.render.filepath=str(OUT/(filename+'.png'))
    bpy.ops.render.render(write_still=True)
    print('RENDERED',filename,flush=True)

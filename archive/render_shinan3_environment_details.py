from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_refined'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
scene=bpy.context.scene
for filename,camera in [('building_refined','Electrical_Room_Detail'),('module_refined','PV_Detail')]:
    scene.camera=bpy.data.objects[camera];scene.render.filepath=str(OUT/(filename+'.png'));bpy.ops.render.render(write_still=True)
    print('RENDERED',filename,flush=True)

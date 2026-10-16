"""Reopen delivered native scene, verify replacement, render an interior view."""
from pathlib import Path
import json
import bpy
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_refined'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
scene=bpy.context.scene;coll=bpy.data.collections['14_Walkable_Electrical_Rooms']
roots=[o for o in coll.objects if 'walkable interior' in o.name]
assert len(roots)==3
for name in ['06_Electrical_Rooms_3','07_Roofs_HIDE_FOR_INTERIOR','11_Drawing_Details_A303_A304']:
    assert bpy.data.collections[name].hide_render and bpy.data.collections[name].hide_viewport
assert len(bpy.data.collections['01_PV_Modules_30000_CAD'].objects)==1500
report=json.loads((OUT/'interior_validation.json').read_text(encoding='utf-8'))
report.update(reopen_passed=True,pv_groups=1500,old_shells_hidden=True)
(OUT/'interior_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
scene.camera=bpy.data.objects['Interior_Aisle_Camera'];scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
scene.render.resolution_x=1200;scene.render.resolution_y=800;scene.render.resolution_percentage=100
scene.render.filepath=str(OUT/'interior_refined.png')
bpy.ops.render.render(write_still=True)
print('INTERIOR_REOPEN_AND_RENDER_PASSED')

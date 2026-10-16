import bpy, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
review=ROOT/'results/shinan2_review'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'results/shinan2_delivery/Models/Shinan2_Review.blend'))
scene=bpy.context.scene
assert scene['modules']==20420
objects=[o for o in scene.objects if o.get('instance_count')]
assert sum(o['instance_count'] for o in objects)==110053
pv=[o for o in objects if o.get('instance_count')==20420]
assert len(pv)==1
points=pv[0].data.vertices
assert len(points)==20420
assert all(i.packed_file or i.source=='GENERATED' for i in bpy.data.images if i.name not in ['Render Result','Viewer Node'])
scene.render.resolution_x=1100;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.cycles.samples=8;scene.cycles.use_denoising=True
scene.render.filepath=str(review/'blender_overview.png')
bpy.ops.render.render(write_still=True)
report=json.loads((review/'blender_validation.json').read_text())
report.update({'reopened':True,'pv_point_count':len(points),'packed_textures':len(bpy.data.images),'rendered':'blender_overview.png'})
(review/'blender_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))

"""Run in Blender background: attach exact drawing IDs and analysis index to a copy."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pv_inspector.site_structures import raised_modules

parser = argparse.ArgumentParser()
parser.add_argument('--source', default=str(ROOT/'results/blender_site/Shinan_Character.blend'))
parser.add_argument('--output', default=str(ROOT/'results/blender_site/Shinan_Module_Results.blend'))
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if Path(args.source).resolve() == Path(args.output).resolve():
    raise ValueError('Use a new output file; preserve the source Blender scene')
index_path = ROOT/'results/module_links/module_links.json'
data = json.loads(index_path.read_text(encoding='utf-8'))
for name, expected in data['fingerprints'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
        raise ValueError('Stale matching source: '+name)
layout = json.loads((ROOT/'results/drawing_site/site_layout.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=args.source)
total = 0
for lane in range(1,5):
    obj = bpy.data.objects.get(f'01_Modules_L{lane}-module')
    if obj is None: raise ValueError('Missing module mesh lane '+str(lane))
    modules = [m for row in layout['rows'] if row['lane']==lane for m in raised_modules(row)]
    mesh = obj.data
    if len(mesh.vertices)!=sum(len(m['vertices']) for m in modules) or len(mesh.polygons)!=sum(len(m['faces']) for m in modules):
        raise ValueError('Blender geometry differs from drawing model')
    vertices = [tuple(v.co) for v in mesh.vertices]
    polygons = [tuple(p.vertices) for p in mesh.polygons]
    face_ids = []
    vertex_offset=face_offset=0
    for i,m in enumerate(modules):
        # Validate geometry and topology before assigning any identity; no nearest-neighbor guesses.
        for j,xyz in enumerate(m['vertices']):
            if max(abs(vertices[vertex_offset+j][k]-xyz[k]) for k in range(3))>0.0001:
                raise ValueError('Vertex identity check failed: '+m['id'])
        for j,face in enumerate(m['faces']):
            if polygons[face_offset+j]!=tuple(vertex_offset+k for k in face):
                raise ValueError('Face identity check failed: '+m['id'])
            face_ids.append(i)
        vertex_offset+=len(m['vertices']);face_offset+=len(m['faces'])
    obj['drawing_module_ids']=json.dumps([m['id'] for m in modules])
    attr = mesh.attributes.get('drawing_module_index') or mesh.attributes.new('drawing_module_index','INT','FACE')
    attr.data.foreach_set('value', face_ids)
    total+=len(modules)
    print('VERIFIED_LANE',lane,len(modules),flush=True)

collection=bpy.data.collections.new('Analysis_Link_Candidates');bpy.context.scene.collection.children.link(collection)
mat=bpy.data.materials.new('Unconfirmed_link_outline');mat.diffuse_color=(1,.55,.03,1)
for module in data['modules'].values():
    if not module['records']:continue
    curve=bpy.data.curves.new('LINK_'+module['id'],'CURVE');curve.dimensions='3D';curve.bevel_depth=.018;curve.bevel_resolution=0
    spline=curve.splines.new('POLY');spline.points.add(3)
    for point,xyz in zip(spline.points,module['polygon']):point.co=(xyz[0],xyz[1],xyz[2]+.035,1)
    spline.use_cyclic_u=True
    obj=bpy.data.objects.new('LINK_'+module['id'],curve);collection.objects.link(obj);curve.materials.append(mat)
    obj['drawing_module_id']=module['id'];obj['link_status']='candidate_or_reviewed_see_records'
    obj['analysis_record_indices']=json.dumps(module['records'])
text=bpy.data.texts.get('MODULE_ANALYSIS_INDEX') or bpy.data.texts.new('MODULE_ANALYSIS_INDEX')
print('CANDIDATE_OUTLINES_READY',flush=True)
text.clear();text.write(json.dumps(data,ensure_ascii=False,indent=1))
print('ANALYSIS_TEXT_READY',flush=True)
bpy.context.scene['module_analysis_count']=len(data['records'])
bpy.context.scene['drawing_module_id_count']=total
bpy.context.scene['module_analysis_scope']='A-zone historical candidates; inspect link_status; no failure confirmation'
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=args.output)
Path(args.output).with_suffix('.links.json').write_text(json.dumps({
    'index_path':str(index_path.relative_to(ROOT)),
    'index_sha256':hashlib.sha256(index_path.read_bytes()).hexdigest(),
    'blend_sha256':hashlib.sha256(Path(args.output).read_bytes()).hexdigest()
},indent=2),encoding='utf-8')
print('LINKED_DRAWING_MODULES',total,'ANALYSIS_RECORDS',len(data['records']),flush=True)

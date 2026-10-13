"""Run with Blender --python after opening Shinan_Module_Results.blend."""
import json
import hashlib
from pathlib import Path
import bpy
import bmesh

DATA = json.loads(bpy.data.texts['MODULE_ANALYSIS_INDEX'].as_string())
ROOT = Path(__file__).resolve().parent
for name, expected in DATA['fingerprints'].items():
    source = ROOT / name
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError('Stale analysis sources; regenerate module links and Blender scene: ' + name)


def selected_id(context):
    obj=context.active_object
    if obj is None:return None
    if obj.get('drawing_module_id'):return obj['drawing_module_id']
    if obj.type=='MESH' and obj.mode=='EDIT' and obj.get('drawing_module_ids'):
        bm=bmesh.from_edit_mesh(obj.data)
        face=bm.faces.active; layer=bm.faces.layers.int.get('drawing_module_index')
        if face is not None and layer is not None:
            return json.loads(obj['drawing_module_ids'])[face[layer]]
    return None


class MODULE_PT_analysis(bpy.types.Panel):
    bl_label='Module analysis links'
    bl_idname='MODULE_PT_analysis'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Analysis'

    def draw(self,context):
        layout=self.layout
        layout.label(text='Orange outline = association candidate')
        layout.label(text='Select outline, or mesh face in Edit Mode')
        mid=selected_id(context)
        if not mid:return
        layout.label(text=mid)
        indices=DATA['modules'].get(mid,{}).get('records',[])
        layout.label(text=f'Observations: {len(indices)}')
        if not indices:layout.label(text='Unassessed (not confirmed normal)')
        for i in indices:
            r=DATA['records'][i];box=layout.box()
            box.label(text=r['link_status']+' / '+r['final'])
            box.label(text=r['image_id'])
            box.label(text='Observation: '+str(r['module_id']))
            box.label(text='Max C: '+str(r.get('max_temp')))
            box.label(text='Delta C: '+str(r.get('delta_temp')))
        if DATA['warnings']:layout.label(text='Evidence incomplete; use review workflow',icon='ERROR')


if hasattr(bpy.types,'MODULE_PT_analysis'):
    bpy.utils.unregister_class(bpy.types.MODULE_PT_analysis)
bpy.utils.register_class(MODULE_PT_analysis)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.show_region_ui=True

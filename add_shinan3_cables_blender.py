from pathlib import Path
import bpy,json,math
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_refined'
data=json.loads((ROOT/'results/shinan3_cables/cable_model.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
name='13_Electrical_Cables_DRAWING_AND_ASSUMED_Z'
old=bpy.data.collections.get(name)
if old:
 for ob in list(old.all_objects):bpy.data.objects.remove(ob,do_unlink=True)
 for c in list(old.children):bpy.data.collections.remove(c)
 bpy.data.collections.remove(old)
parent=bpy.data.collections.new(name);scene.collection.children.link(parent)
colors={'series':(.7,.38,.08),'dc_branch':(.75,.20,.06),'dc_feeder':(.38,.20,.65),'ac_schematic':(.8,.55,.08),'trays':(.32,.4,.44),'equipment':(.22,.4,.46),'negative':(.05,.55,.7)}
materials={}
for k,color in colors.items():
 mat=bpy.data.materials.new('Cable_'+k);mat.diffuse_color=(*color,1);mat.use_nodes=True
 bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=.58;bs.inputs['Metallic'].default_value=.18;materials[k]=mat
cols={}
for k in colors:
 if k=='negative':continue
 coll=bpy.data.collections.new('Cable_'+k);parent.children.link(coll);cols[k]=coll
def curve(name,points,kind,radius,meta=None):
 cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=1;cu.bevel_depth=radius;cu.bevel_resolution=1
 sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
 sp.points.foreach_set('co',[v for p in points for v in (*p,1)])
 ob=bpy.data.objects.new(name,cu);cols[kind].objects.link(ob);cu.materials.append(materials['negative' if name.endswith(' N') else kind])
 ob['evidence']='Connectivity from electrical drawings/schedule; routing, height and visible diameter illustrative'
 if meta:
  for k,v in meta.items():ob[k]=v if isinstance(v,(str,int,float,bool)) else json.dumps(v,ensure_ascii=False)
 return ob
schedule={c['id']:c for c in data['schedule']}
for p in data['paths']:
 c=schedule[p['id']]
 curve(p['id'],p['points'],p['kind'],.045 if p['kind']=='dc_branch' else .065,{'from_equipment':p['from'],'to_equipment':p['to'],'source':'Cable Schedule.xls','source_row':c['row'],'cable_type':c['type'],'size_mm2':c['size_mm2'],'schedule_length_m':c['schedule_length_m'],'route_codes':c['route_codes'],'routing_status':p['status']})
for s,record in zip(data['series'],data['strings']):
 curve(s['id'],s['points'],'series',.035,{'junction_box':record['jb'],'inverter':record['inverter'],'module_ids':record['modules'],'source':record['source'],'source_boundary_handle':record['boundary_handle']})
cu=bpy.data.curves.new('CAD_Tray_Conduit_Plan_Outlines','CURVE');cu.dimensions='3D';cu.bevel_depth=.035;cu.bevel_resolution=0
for r in data['tray_edges']:
 sp=cu.splines.new('POLY');sp.points.add(len(r['points'])-1);sp.points.foreach_set('co',[v for p in r['points'] for v in (*p,.43,1)])
ob=bpy.data.objects.new('CAD_Tray_Conduit_Plan_Outlines',cu);cols['trays'].objects.link(ob);cu.materials.append(materials['trays']);ob['evidence']='CAD plan edges; illustrative Z=0.43m; not full tray solid geometry'
for e in data['equipment']:
 bpy.ops.mesh.primitive_cube_add(size=1,location=e['pos']);ob=bpy.context.object;ob.name=e['id'];ob.scale=(e['size'][0],e['size'][1],e['size'][2]);ob.rotation_euler.z=e['rotation']
 for c in list(ob.users_collection):c.objects.unlink(ob)
 cols['equipment'].objects.link(ob);ob.data.materials.append(materials['equipment'])
 ob['source']=e['source'];ob['source_handle']=e['handle'];ob['evidence']=e['geometry_status']
parent['scope']=data['scope'];parent['source_schedule']='Cable Schedule.xls';parent['module_count']=30000;parent['string_count']=1500
# Preserve regular opening view. Operators can toggle the electrical collections in the Outliner.
parent.hide_render=True
bpy.context.view_layer.update()
bpy.context.view_layer.layer_collection.children[name].hide_viewport=True
cam=bpy.data.objects.get('Cable_Overview')
if not cam:
 cd=bpy.data.cameras.new('Cable_Overview');cam=bpy.data.objects.new('Cable_Overview',cd);scene.collection.objects.link(cam)
cam.location=(172,-222,800);cam.rotation_euler=(Vector((172,-222,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=610;cam.data.clip_end=2000
scene.camera=bpy.data.objects['Aerial_Overview']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Shinan3_Refined.blend'))
assert len([o for o in parent.all_objects if o.name.startswith('SM-')])==1500
assert len([o for o in cols['dc_branch'].objects])==3000
assert len([o for o in cols['dc_feeder'].objects])==164
(OUT/'cable_validation.json').write_text(json.dumps({'strings':1500,'dc_branch':3000,'dc_feeder':164,'ac_schematic':len(cols['ac_schematic'].objects),'equipment':len(cols['equipment'].objects),'module_ids_preserved':len([o for o in scene.objects if o.name.startswith('PV_S3-')])==1500,'physical_routing_verified':False},indent=2),encoding='utf-8')
print('CABLE_BLEND_SAVED',flush=True)
# Render a separate electrical overview, without changing the saved opening state.
parent.hide_render=False;bpy.context.view_layer.layer_collection.children[name].hide_viewport=False
cols['ac_schematic'].hide_render=True
for ob in scene.objects:
 if ob.name.startswith(('PV_S3-','Foundation','Support','ER','Simplified_Forest')):ob.hide_render=True
for coll in scene.collection.children:
 if coll!=parent and any(token in coll.name.lower() for token in ['pv','module','support','building','drawing_details']):coll.hide_render=True
scene.camera=cam;scene.cycles.samples=16;scene.render.resolution_x=1600;scene.render.resolution_y=1200;scene.render.filepath=str(OUT/'cables_refined.png')
bpy.ops.render.render(write_still=True)
print('CABLE_RENDERED',flush=True)

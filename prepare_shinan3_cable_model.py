"""Build a shared Blender/ThreeJS electrical model, with explicit evidence levels."""
from pathlib import Path
import sys,json,re,math,collections
ROOT=Path(__file__).resolve().parent;sys.path[:0]=[str(ROOT/'tmp/pdfdeps')]
import ezdxf,numpy as np,networkx as nx
from ezdxf import bbox
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from shapely.geometry import LineString
from shapely.ops import unary_union
OUT=ROOT/'results/shinan3_cables'
d=json.loads((OUT/'electrical_extracted.json').read_text(encoding='utf-8'))
layout=json.loads((ROOT/'results/shinan3_blender/layout.json').read_text(encoding='utf-8'))
modules=layout['modules'];groups={g['id']:g for g in layout['groups']}
equipment=[]
for i,b in enumerate(layout['buildings'],1):
 code=10100+i*10;doc=ezdxf.readfile(next(OUT.glob(f'*{code}*.dxf')));m=doc.modelspace()
 columns=[e for e in m.query('INSERT') if e.dxf.name=='A$C1B6E01CC'];assert len(columns)==12
 center=np.array(list(bbox.extents(columns).center)[:2]);angle=b['rotation'];rot=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
 rects=[]
 for e in m.query('LWPOLYLINE'):
  if e.dxf.layer!='PANEL':continue
  p=np.array([list(v)[:2] for v in e.vertices_in_wcs()]);size=p.max(axis=0)-p.min(axis=0)
  if size[0]>=750 and size[1]>=900:rects.append((e,(p.max(axis=0)+p.min(axis=0))/2,size))
 labels=[e for e in m.query('TEXT') if re.fullmatch(r'(INV|LV|TR|VCB|DS|PT|MOF|REC|MCCB)\d{3}',e.dxf.text) and abs(e.dxf.insert.y-center[1])<4800]
 cost=[]
 for t in labels:
  row=[]
  for e,c,size in rects:
   valid=(abs(size[0]-2200)<1 and abs(size[1]-990)<1) if t.dxf.text.startswith('INV') else (abs(size[0]-800)<1 if t.dxf.text.startswith(('LV','REC','MCCB')) else abs(size[1]-2500)<1)
   row.append(np.linalg.norm(np.array(list(t.dxf.insert)[:2])-c)+(0 if valid else 1e6))
  cost.append(row)
 rr,cc=linear_sum_assignment(cost)
 for a,j in zip(rr,cc):
  t=labels[a];e,c,size=rects[j];assert cost[a][j]<2500,(t.dxf.text,cost[a][j])
  local=(c-center)/1000;xy=np.array(b['center'])+rot@local
  equipment.append({'id':t.dxf.text,'building':b['id'],'pos':[*xy,1.6],'size':[float(size[0]/1000),float(size[1]/1000),2.12 if t.dxf.text.startswith('INV') else 2.35],'rotation':angle,'source':f'3SA-E-{code}','handle':e.dxf.handle,'geometry_status':'Plan footprint; height illustrative except INV 2.12m; floor alignment by column frame'})
assert len([e for e in equipment if e['id'].startswith('INV')])==15
eq={e['id']:e for e in equipment}
for k,j in d['junction_boxes'].items():
 eq[k]={'id':k,'pos':[*j['pos'],1.1],'size':[1,.45,1.2],'rotation':0,'source':'3SA-E-11230','handle':j['handle'],'geometry_status':'CAD symbol center; cabinet dimensions and mounting height illustrative'}
equipment.extend(eq[k] for k in d['junction_boxes'])
# A centerline approximation follows nearby CAD tray/conduit edges. It is not a surveyed individual cable path.
lines=[]
for r in d['routes']:
 if r['kind']=='tray' and len(r['points'])>=2:lines.append(LineString(r['points']))
union=unary_union(lines);graph=nx.Graph();coords=[];nodeby={}
def node(p):
 key=tuple(round(float(x),3) for x in p)
 if key not in nodeby:nodeby[key]=len(coords);coords.append(key)
 return nodeby[key]
for line in union.geoms:
 pts=list(line.coords)
 for a,b in zip(pts,pts[1:]):
  u,v=node(a),node(b)
  if u!=v:graph.add_edge(u,v,weight=math.dist(a,b))
tree=cKDTree(coords)
for a,b in tree.query_pairs(.85):graph.add_edge(a,b,weight=math.dist(coords[a],coords[b])*2)
component={u:i for i,c in enumerate(nx.connected_components(graph)) for u in c}
def inferred_path(a,b):
 da,ia=tree.query(a,k=16);db,ib=tree.query(b,k=16);candidates=[]
 for x,u in zip(da,ia):
  for y,v in zip(db,ib):
   if component[u]==component[v]:candidates.append((x+y,int(u),int(v)))
 if not candidates:return [list(a),[a[0],b[1]],list(b)],'schematic_gap'
 _,u,v=min(candidates);path=nx.shortest_path(graph,u,v,weight='weight')
 xy=[list(a)]+[list(coords[n]) for n in path]+[list(b)]
 # Drop redundant nearly straight vertices, retaining the actual path bends.
 simplified=list(LineString(xy).simplify(.08).coords)
 return [list(p) for p in simplified],'tray_guided_inferred'
def canonical(s):
 m=re.match(r'(INV|LV|TR|VCB|DS|PT|MOF|REC|MCCB|JB|SM)\s*-?\s*(\d{3}[A-F]?(?:\d{2})?)',str(s))
 if not m:return None
 return m[1]+('-' if m[1] in ('JB','SM') else '')+m[2]
schedule={c['id']:c for c in d['schedule']}
paths=[];series=[];mapping=[None]*30000
for si,s in enumerate(d['strings']):
 indices=s['module_indices']
 if s['shape']=='return10x2':indices=indices[:10]+list(reversed(indices[10:]))
 points=[]
 for idx in indices:
  m=modules[idx];g=groups[m['group_id']];x,n=m['center_xy_m'];height=.8+(n-g['bounds'][1])*math.tan(math.pi/6)-.10
  points.append([x,n,height]);assert mapping[idx] is None;mapping[idx]=si
 s['module_indices']=indices;s['modules']=[modules[i]['id'] for i in indices]
 # Illustrative under-panel jumper shape; electrical sequence follows 11310 typical and string boundary.
 wire=[]
 for a,b in zip(points,points[1:]):
  if not wire:wire.append(a)
  wire.extend([[(a[0]+b[0])/2,(a[1]+b[1])/2,min(a[2],b[2])-.08],b])
 series.append({'id':s['id'],'points':wire,'status':'typical_series_connection'})
 jb=eq[s['jb']]['pos'];first,last=points[0],points[-1]
 for polarity in ('P','N'):
  cid='D'+s['id'][3:]+' '+polarity;c=schedule[cid]
  assert canonical(c['from'])==s['jb'] and canonical(c['to'])==s['id']
  side=-.16 if polarity=='P' else .16
  start=first if polarity=='P' else last
  exit=[first[0]-.65,first[1]+side,.75]
  branch=[start]
  if polarity=='N' and s['shape']=='straight20':branch.extend([[last[0]+.5,last[1]+.55,last[2]-.1],[first[0]-.65,first[1]+.55,first[2]-.1]])
  branch.extend([exit,[jb[0]+side,exit[1],.75],[jb[0]+side,jb[1],.75],jb])
  paths.append({'id':cid,'kind':'dc_branch','points':branch,'from':s['id'],'to':s['jb'],'source_row':c['row'],'status':'schematic_branch_routing'})
for k in d['junction_boxes']:
 inv='INV'+k[3:6]
 xy,status=inferred_path(eq[k]['pos'][:2],eq[inv]['pos'][:2])
 for polarity in ('P','N'):
  cid='D'+k[3:]+'00 '+polarity;c=schedule[cid];assert canonical(c['from'])==inv and canonical(c['to'])==k
  z=.55 if polarity=='P' else .65
  pts=[eq[k]['pos']]+[[*p,z] for p in xy]+[eq[inv]['pos']]
  paths.append({'id':cid,'kind':'dc_feeder','points':pts,'from':k,'to':inv,'source_row':c['row'],'status':status})
# Display equipment-to-equipment AC/HV connections only where both endpoints are located.
for c in d['schedule']:
 if c['id'][0] not in ('H','L'):continue
 a,b=canonical(c['from']),canonical(c['to'])
 if a not in eq or b not in eq or a==b or a.startswith('JB') or b.startswith('JB'):continue
 pa,pb=eq[a]['pos'],eq[b]['pos']
 pts=[pa,[pa[0],pa[1],.35],[pa[0],pb[1],.35],[pb[0],pb[1],.35],pb]
 paths.append({'id':c['id'],'kind':'ac_schematic','points':pts,'from':a,'to':b,'source_row':c['row'],'status':'schematic_terminal_connection'})
assert all(v is not None for v in mapping)
for p in paths:p['points']=[[round(float(c),5) for c in v] for v in p['points']]
for s in series:s['points']=[[round(float(c),5) for c in v] for v in s['points']]
model={'schema':1,'scope':'Electrical connectivity from CAD and Cable Schedule; individual routing, Z and visible cable diameter are illustrative. Not an excavation/as-built survey model.', 'strings':d['strings'],'module_to_string':mapping,'equipment':equipment,'paths':paths,'series':series,'tray_edges':d['routes'],'schedule':d['schedule'],'sources':{'strings':'3SA-E-11320 through 11480','series':'3SA-E-11310','junction_boxes':'3SA-E-11230,11240','trays':'3SA-E-12210 through 12370','equipment':'3SA-E-10110,10120,10130','cable_list':'Cable Schedule.xls'},'assumed':{'cable_heights':True,'individual_cable_routing':True,'visible_diameter_exaggerated':True,'thermal_linked':False}}
raw=json.dumps(model,ensure_ascii=False,separators=(',',':'))
(OUT/'cable_model.json').write_text(raw,encoding='utf-8')
(ROOT/'shinan3_viewer/cable_data.js').write_text('export default '+raw+';\n',encoding='utf-8')
counts=collections.Counter(p['kind'] for p in paths)
validation={'strings':len(model['strings']),'mapped_modules':len(mapping),'junction_boxes':len(d['junction_boxes']),'inverters':15,'equipment_objects':len(equipment),'cables_by_kind':dict(counts),'all_dc_schedule_connections_verified':counts['dc_branch']==3000 and counts['dc_feeder']==164,'source_tray_edges':len(d['routes']),'routing_status':dict(collections.Counter(p['status'] for p in paths)),'schedule_records':len(d['schedule']),'not_spatially_rendered_schedule_records':len(d['schedule'])-len(paths),'physical_routing_verified':False}
(OUT/'model_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=True,indent=2))

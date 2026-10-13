"""Extract electrical identities and plan geometry without modifying source files."""
from pathlib import Path
import sys,json,re,math,collections,hashlib
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tmp/pdfdeps'),str(ROOT/'tmp/cabledeps')]
import ezdxf,numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree
from shapely.geometry import Polygon,Point
OUT=ROOT/'results/shinan3_cables'
layout=json.loads((ROOT/'results/shinan3_blender/layout.json').read_text(encoding='utf-8'))
origin=layout['cad_origin_mm']
group_centers=np.array([[(g['bounds'][0]+g['bounds'][2])/2,(g['bounds'][1]+g['bounds'][3])/2] for g in layout['groups']])
group_tree=cKDTree(group_centers)
def read(code):return ezdxf.readfile(next(OUT.glob('3SA-E-'+str(code)+'_*.dxf')))
def rectangles(m,layer=None):
 out=[]
 for e in m.query('LWPOLYLINE'):
  if layer and e.dxf.layer!=layer:continue
  pts=np.array([list(p)[:2] for p in e.vertices_in_wcs()])
  lo=pts.min(axis=0);hi=pts.max(axis=0)
  out.append({'handle':e.dxf.handle,'center':(lo+hi)/2,'size':hi-lo,'lo':lo,'hi':hi,'points':pts})
 return out
def labels(m,pattern):return [e for e in m.query('TEXT') if re.fullmatch(pattern,e.dxf.text)]
def pair_jb(m):
 rs=rectangles(m,'JB');ts=labels(m,r'JB-\d{3}[A-F]')
 if not ts:return {}
 cost=np.array([[np.linalg.norm(np.array(list(t.dxf.insert)[:2])-r['center']) for r in rs] for t in ts])
 rows,cols=linear_sum_assignment(cost)
 return {ts[a].dxf.text:{'center':rs[b]['center'],'handle':rs[b]['handle'],'label_handle':ts[a].dxf.handle} for a,b in zip(rows,cols)}
master=pair_jb(read(11230).modelspace())
for v in master.values():
 x,y=v.pop('center');v['pos']=[(y-origin[1])/1000,-(x-origin[0])/1000]
def alignment(m):
 pairs=pair_jb(m)
 offsets=np.array([np.array(master[k]['pos'])-v['center']/1000 for k,v in pairs.items() if k in master])
 # Each detail plan is north-up at full millimetre scale; overview has north at CAD -X.
 offset=np.median(offsets,axis=0);residual=np.linalg.norm(offsets-offset,axis=1)
 good=residual<.25
 if good.any():offset=np.median(offsets[good],axis=0)
 # Refine against module rectangles, since JB symbols differ in size between overview and tray plans.
 centers=[]
 for ins in m.query('INSERT'):
  if abs(ins.dxf.xscale-1)>.001 or abs(ins.dxf.yscale-1)>.001:continue
  if ins.dxf.name.startswith('no.') or ins.dxf.name in ('TTT','FFF','F01'):continue
  pts=[];count=0
  for e in ins.virtual_entities():
   if e.dxftype()!='LWPOLYLINE':continue
   p=np.array([list(v)[:2] for v in e.vertices_in_wcs()])
   if len(p)!=4:continue
   lens=sorted(np.linalg.norm(p[i]-p[(i+1)%4]) for i in range(4))
   if abs(lens[0]-983)<.01 and abs(lens[-1]-1425)<.01:pts.extend(p);count+=1
  if count==20:
   pts=np.array(pts);centers.append((pts.min(axis=0)+pts.max(axis=0))/2000)
 centers=np.array(centers)
 assert len(centers)>10,'Insufficient module anchors'
 dist,idx=group_tree.query(centers+offset);keep=dist<1.5
 offset=np.median(group_centers[idx[keep]]-centers[keep],axis=0)
 dist,idx=group_tree.query(centers+offset)
 return offset,{'jb_anchors':len(offsets),'module_anchors':len(centers),'max_module_anchor_error_m':float(dist.max()),'median_module_anchor_error_m':float(np.median(dist))}
modulepts=np.array([m['center_xy_m'] for m in layout['modules']]);moduleids=[m['id'] for m in layout['modules']]
strings={};registrations={};issues=[]
codes=list(range(11320,11490,10))
for code in codes:
 doc=read(code);m=doc.modelspace();offset,stats=alignment(m);registrations[str(code)]={'offset_m':list(offset),**stats}
 rects=[r for r in rectangles(m) if (abs(r['size'][0]-20210)<1 and abs(r['size'][1]-1425)<1) or (abs(r['size'][0]-10055)<1 and abs(r['size'][1]-2850)<1)]
 for text in labels(m,r'SM-\d{3}[A-F]\d{2}'):
  p=np.array(list(text.dxf.insert)[:2]);candidates=[r for r in rects if np.all(p>=r['lo']-.01) and np.all(p<=r['hi']+.01)]
  if len(candidates)!=1:issues.append({'string':text.dxf.text,'issue':'ambiguous string boundary','count':len(candidates)});continue
  r=candidates[0];lo=r['lo']/1000+offset;hi=r['hi']/1000+offset
  indices=np.flatnonzero(np.all(modulepts>=lo-.08,axis=1)&np.all(modulepts<=hi+.08,axis=1)).tolist()
  if len(indices)!=20:issues.append({'string':text.dxf.text,'issue':'module count','count':len(indices)});continue
  indices.sort(key=lambda i:(round(modulepts[i,1],1),modulepts[i,0]))
  key=text.dxf.text
  record={'id':key,'jb':'JB-'+key[3:7],'inverter':'INV'+key[3:6],'modules':[moduleids[i] for i in indices],'module_indices':indices,'bounds':[float(v) for v in [*lo,*hi]],'source':f'3SA-E-{code}','text_handle':text.dxf.handle,'boundary_handle':r['handle'],'shape':'straight20' if r['size'][0]>15000 else 'return10x2'}
  if key in strings and strings[key]['modules']!=record['modules']:issues.append({'string':key,'issue':'conflicting sheets'})
  strings[key]=record
 print(code,'strings',len(strings),'issues',len(issues),stats,flush=True)
# Export only source tray/conduit outlines, not inferred electrical centerlines.
routes=[]
from ezdxf.path import make_path
for code in range(12210,12380,10):
 doc=read(code);m=doc.modelspace();offset,stats=alignment(m);registrations[str(code)]={'offset_m':list(offset),**stats}
 for e in m:
  if e.dxf.layer.lower() not in ('tray','conduit') or e.dxftype() not in ('LINE','LWPOLYLINE','ARC'):continue
  try:pts=[list(p)[:2] for p in make_path(e).flattening(30)]
  except (TypeError,ValueError):continue
  if len(pts)<2:continue
  xy=np.array(pts)/1000+offset
  # Reject legend/key-plan geometry outside the physical site envelope.
  if xy[:,0].min()<-60 or xy[:,0].max()>420 or xy[:,1].min()<-550 or xy[:,1].max()>50:continue
  routes.append({'id':f'{code}-{e.dxf.handle}','kind':e.dxf.layer.lower(),'source':f'3SA-E-{code}','handle':e.dxf.handle,'points':xy.tolist()})
 print(code,'route edges',len(routes),flush=True)
# Read schedule records directly: preserve source row, terminals, route codes and specified lengths.
import xlrd
schedulepath=Path('C:/3호기준공도서CD/전기/1. 도면/Cable Schedule.xls')
book=xlrd.open_workbook(schedulepath);sheet=max(book.sheets(),key=lambda s:s.nrows)
schedule=[]
for row in range(3,sheet.nrows):
 v=sheet.row_values(row)
 if v[1] not in ('D','L','H','S','C') or not str(v[2]).strip() or not str(v[4]).strip() or not str(v[6]).strip():continue
 schedule.append({'id':str(v[1])+str(v[2]).strip(),'from':v[4],'to':v[6],'type':v[10],'cores':v[11],'size_mm2':v[12],'schedule_length_m':v[15],'route_codes':v[16],'row':row+1})
used=[i for s in strings.values() for i in s['module_indices']]
counts=collections.Counter(used)
report={'strings':len(strings),'junction_boxes':len(master),'unique_modules':len(counts),'duplicate_modules':sum(v>1 for v in counts.values()),'missing_modules':len(moduleids)-len(counts),'tray_conduit_edges':len(routes),'schedule_records':len(schedule),'issues':issues,'registrations':registrations}
(OUT/'extraction_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
payload={'strings':list(strings.values()),'junction_boxes':master,'routes':routes,'schedule':schedule,'registrations':registrations,'source_schedule_sha256':hashlib.sha256(schedulepath.read_bytes()).hexdigest()}
(OUT/'electrical_extracted.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('registrations','issues')}),flush=True)

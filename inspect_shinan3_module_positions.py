"""Inspect real observations against map-derived drawing positions, without confirming IDs."""
from pathlib import Path
import csv,json,math,shutil
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
RUN=Path((ROOT/'tmp/shinan3_latest_run.txt').read_text().strip())
OUT=ROOT/'results/shinan3_module_position_review';OUT.mkdir(exist_ok=True)
registration=json.loads((ROOT/'results/shinan3_map_alignment/alignment.json').read_text(encoding='utf-8'))
modules=json.loads((ROOT/'results/shinan3_map_alignment/module_geolocation_candidates.json').read_text(encoding='utf-8'))
package=json.loads((RUN/'threejs_results_v2/inspection_results.json').read_text(encoding='utf-8'))
tile=registration['imagery']['mosaics'][0];world=256*2**tile['zoom'];t=registration['transform_xn_to_pixel']
def pixel(lat,lon):return np.array([(lon+180)/360*world-tile['tile_x0']*256,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*world-tile['tile_y0']*256])
matrix=np.array([[t['a'],t['b']],[t['b'],-t['a']]])
def local(lat,lon):return np.linalg.solve(matrix,pixel(lat,lon)-[t['tx'],t['ty']])
xy=np.array([[m['x'],m['n']] for m in modules]);tree=cKDTree(xy)
base=Image.open(ROOT/'results/shinan3_map_alignment/map_drawing_overlay.png').convert('RGB')
rows=[];by_image={}
for r in package['records']:
    lat,lon=r['estimated_latlon']
    if lat is None or lon is None:continue
    q=local(lat,lon);dist,idx=tree.query(q,k=3)
    r['estimated_local_xn']=q.tolist()
    r['drawing_module_id']=None;r['link_status']='unmatched'
    r['reason']='map_nearest_candidates_only_not_independently_registered'
    r['candidates']=[{'id':modules[i]['id'],'distance_m':float(d)} for d,i in zip(dist,idx) if d<=5]
    by_image.setdefault(r['image_id'],[]).append((r,pixel(lat,lon),idx,dist))
    rows.append({'observation_id':r['observation_id'],'image_id':r['image_id'],'detected_module_id':r['detected_module_id'],'estimated_lat':lat,'estimated_lon':lon,'nearest_drawing_id':modules[idx[0]]['id'],'distance_m':float(dist[0]),'second_distance_m':float(dist[1]),'nearest_gap_m':float(dist[1]-dist[0]),'status':'diagnostic_candidate_only'})
for image_id,items in by_image.items():
    im=base.copy();draw=ImageDraw.Draw(im)
    for r,p,idx,dist in items:
        x,y=p;draw.ellipse((x-2,y-2,x+2,y+2),fill='yellow')
    ps=np.array([v[1] for v in items]);x0,y0=np.floor(ps.min(axis=0)-35).astype(int);x1,y1=np.ceil(ps.max(axis=0)+35).astype(int)
    x0,y0,x1,y1=max(0,x0),max(0,y0),min(im.width,x1),min(1280,y1)
    zoom=base.crop((x0,y0,x1,y1));factor=1000/max(zoom.size);zoom=zoom.resize((round(zoom.width*factor),round(zoom.height*factor)))
    zd=ImageDraw.Draw(zoom)
    for r,p,idx,dist in items:
        x,y=(p-[x0,y0])*factor
        target=matrix@xy[idx[0]]+[t['tx'],t['ty']];u,v=(target-[x0,y0])*factor
        zd.line((x,y,u,v),fill='#ff9840',width=1)
        zd.ellipse((x-2,y-2,x+2,y+2),fill='yellow')
        zd.rectangle((u-2,v-2,u+2,v+2),outline='white')
    zoom.save(OUT/(image_id+'_map_positions.png'))
    for r,p,idx,dist in items:
        x,y=p;ImageDraw.Draw(base).ellipse((x-2,y-2,x+2,y+2),fill='yellow')
base.save(OUT/'all_observation_positions.png')
with (OUT/'position_candidates.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
shutil.copytree(RUN/'threejs_results_v2/images',OUT/'images',dirs_exist_ok=True)
package['registration']={'status':'visual_map_nearest_candidate_review','method':'3 roof centres + approximate camera ray, not surveyed','confirmed':False}
package['limitations'].append('Nearest ID and distance are diagnostics; small distance does not verify module identity.')
(OUT/'inspection_results.json').write_text(json.dumps(package,ensure_ascii=False,allow_nan=False),encoding='utf-8')
report={'observations':len(rows),'confirmed':0,'by_image':{},'notes':['Distances to nearest repeating module do not measure absolute registration accuracy.','No RGB-to-thermal or RGB-to-map homography has been established.','Same-image duplicate nearest IDs are evidence of ambiguity, not fused physical modules.']}
for image_id,items in by_image.items():
    ds=[float(v[3][0]) for v in items];ids=[int(v[2][0]) for v in items]
    report['by_image'][image_id]={'observations':len(ds),'nearest_distance_median_m':float(np.median(ds)),'nearest_distance_max_m':max(ds),'unique_nearest_ids':len(set(ids)),'duplicate_nearest_assignments':len(ids)-len(set(ids))}
(OUT/'position_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))

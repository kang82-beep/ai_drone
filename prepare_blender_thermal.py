"""Prepare real inspection data in the orthomosaic coordinate frame, not drawing IDs."""
import csv,json,math
from pathlib import Path
from collections import Counter
import numpy as np
import rasterio
from rasterio.enums import Resampling
from pyproj import Transformer
from scipy.spatial import cKDTree
from PIL import Image
from shapely.geometry import Point, shape
import re
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/blender_site'
OFFSET=400

def validation_zone(lon, lat, zones):
    """Accept only unambiguous A polygons, using module GPS rather than camera zone."""
    if lon is None or lat is None or not math.isfinite(lon) or not math.isfinite(lat):
        return None
    point=Point(lon,lat)
    matches=[name for name, polygon in zones if polygon.covers(point)]
    return matches[0] if len(matches)==1 and re.fullmatch(r'A\d*',matches[0]) else None

def numeric(row,key):
    try:
        v=float(row.get(key,''));return v if math.isfinite(v) else None
    except (ValueError,TypeError):return None

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    zone_file=ROOT/'model/zones shinan2 .geojson'
    zones=[(f['properties']['zone_id'],shape(f['geometry'])) for f in json.loads(zone_file.read_text(encoding='utf-8'))['features']]
    catalog=json.loads((ROOT/'results/module_split_site/modules.json').read_text(encoding='utf-8'))
    modules=catalog['modules']
    with rasterio.open(ROOT/'3d/result (1).tif') as src:
        assert src.width==catalog['width'] and src.height==catalog['height']
        transformer=Transformer.from_crs('EPSG:4326',src.crs,always_xy=True)
        inv=~src.transform;sx=src.transform.a;sy=-src.transform.e
        width=4096;height=round(width*src.height/src.width)
        rgb=src.read([1,2,3],out_shape=(3,height,width),resampling=Resampling.bilinear)
        Image.fromarray(rgb.transpose(1,2,0)).save(OUT/'thermal_orthomosaic.jpg',quality=92)
        bounds=[src.width*sx,src.height*sy]
        transform=list(src.transform)
        to_geo=Transformer.from_crs(src.crs,'EPSG:4326',always_xy=True)
        modules=[m for m in modules if validation_zone(*to_geo.transform(*(src.transform*tuple(m['center']))),zones)]
    if not modules:raise ValueError('No RGB candidates in validation zone A')
    centers=np.array([[m['center'][0]*sx,m['center'][1]*sy] for m in modules]);tree=cKDTree(centers)
    rows=list(csv.DictReader((ROOT/'re/modules_dedup.csv').open(encoding='utf-8-sig')))
    source_counts=dict(Counter(r['final'] for r in rows));source_total=len(rows)
    selected=[]
    for row in rows:
        zone=validation_zone(numeric(row,'mod_lon'),numeric(row,'mod_lat'),zones)
        if zone:
            row['validation_zone']=zone;selected.append(row)
    rows=selected
    counts=Counter(r['final'] for r in rows);records=[];by_module={}
    for r in rows:
        if r['final'] not in ('abnormal','attention'):continue
        lat,lon=numeric(r,'mod_lat'),numeric(r,'mod_lon')
        entry={k:r.get(k,'') for k in ['module_uid','image_id','module_id','final','geo_status','association_status','observation_count']}
        entry.update({k:numeric(r,k) for k in ['mean_temp','max_temp','delta_temp','prob_abnormal','prob_attention']})
        entry.update(source_csv='re/modules_dedup.csv',validation_zone=r['validation_zone'],position=None,candidate_id=None,matching_status='unlocated')
        for key,choices in [('crop',[r.get('dst_path',''),r.get('crop_path','')]),('thermal',[r.get('overlay_base',''),str(ROOT/'image'/(r['image_id']+'.JPG'))])]:
            entry[key]=next((str(Path(p).resolve()) for p in choices if p and Path(p).is_file()),None)
        if lat is not None and lon is not None:
            east,north=transformer.transform(lon,lat);px,py=inv*(east,north);x,y=px*sx,py*sy
            if 0<=x<=bounds[0] and 0<=y<=bounds[1]:
                entry['position']=[OFFSET+x,y,.25];dist,index=tree.query([x,y]);entry['nearest_distance_m']=round(float(dist),3)
                # Nearest-neighbour gate limits visual candidates, never certifies the physical module.
                if dist<=.9:
                    m=modules[int(index)];entry['candidate_id']=m['id'];entry['matching_status']='provisional_nearest_RGB_candidate'
                    target=by_module.setdefault(m['id'],{'id':m['id'],'polygon':[[OFFSET+p[0]*sx,p[1]*sy,.15] for p in m['polygon']],'records':[]})
                    target['records'].append(len(records))
                else:entry['matching_status']='approximate_GPS_only'
            else:entry['matching_status']='outside_orthomosaic'
        records.append(entry)
    records_order=sorted(range(len(records)),key=lambda i:(records[i]['final']!='abnormal',-(records[i]['delta_temp'] or 0)))
    for m in by_module.values():m['severity']='abnormal' if any(records[i]['final']=='abnormal' for i in m['records']) else 'attention'
    payload={'source':'re/modules_dedup.csv','validation_scope':{'zone':'A','zone_file':str(zone_file.relative_to(ROOT)),'method':'module GPS inside one A polygon; RGB candidate center inside one A polygon','excluded_records':source_total-len(rows),'included_records':len(rows),'source_counts':source_counts,'candidate_count':len(modules)},'counts':dict(counts),'records':records,'navigation_order':[i for i in records_order if records[i]['final']=='abnormal' and records[i]['position'] is not None],
        'highlight_modules':list(by_module.values()),'orthomosaic':{'file':'thermal_orthomosaic.jpg','size_m':bounds,'offset_x':OFFSET,'crs':'EPSG:32652','transform':transform},
        'notes':['All locations are approximate_flat_plane drone geolocation. No surveyed accuracy is asserted.','RGB candidate IDs are not drawing module IDs. Nearest match within 0.9m is provisional, not confirmed.','Temporary IDs may still duplicate physical modules. Counts are result records, not confirmed unique faulty modules.','Unhighlighted modules are unassessed here, not declared normal.','Inspection area is placed beside the drawing model at X+400m; this is a separate coordinate frame, not a registered overlay on the drawing.']}
    (OUT/'thermal_review.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':dict(counts),'matching':dict(Counter(r['matching_status'] for r in records)),'abnormal_matching':dict(Counter(r['matching_status'] for r in records if r['final']=='abnormal')),'highlight_candidates':len(by_module)},indent=2))

if __name__=='__main__':main()

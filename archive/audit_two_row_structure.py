"""Replay two-row geometry on existing detections without changing original IDs/data."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from affine import Affine
from pyproj import Transformer
from shapely.geometry import Point,shape
from pv_inspector.module_review import digest,atomic_json
from pv_inspector.two_row_structure import assess_two_rows,COLORS,VERSION

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/two_row_structure'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog_path=ROOT/'results/module_split_site/modules.json';catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    rgb=assess_two_rows(catalog['modules'],(catalog['width'],catalog['height']))
    review=json.loads((ROOT/'results/blender_site/thermal_review_registered_a.json').read_text(encoding='utf-8'))
    ortho=review['orthomosaic'];affine=Affine(*ortho['transform'][:6]);to_geo=Transformer.from_crs(ortho['crs'],'EPSG:4326',always_xy=True)
    zones=[(f['properties']['zone_id'],shape(f['geometry'])) for f in json.loads((ROOT/'model/zones shinan2 .geojson').read_text(encoding='utf-8'))['features']]
    a_counts=Counter();a_ids=set()
    for m,result in zip(catalog['modules'],rgb):
        point=Point(*to_geo.transform(*(affine*tuple(m['center']))))
        matches=[name for name,p in zones if p.covers(point)]
        if len(matches)==1 and matches[0].startswith('A'):
            a_counts[result['status']]+=1;a_ids.add(m['id'])
    atomic_json(OUT/'rgb_structure.json',{'version':VERSION,'source_sha256':digest(catalog_path),
                 'results':{m['id']:r for m,r in zip(catalog['modules'],rgb)},'a_zone_counts':dict(a_counts),
                 'scope':'Rule assessment over RGB candidates; validation/report focus is A. Not a probability or physical module count.'})
    image=Image.open(ROOT/'results/module_split_site/overview_rgb.jpg').convert('RGB')
    draw=ImageDraw.Draw(image);sx=image.width/catalog['width'];sy=image.height/catalog['height']
    for m,r in zip(catalog['modules'],rgb):
        if m['id'] not in a_ids:continue
        points=[(x*sx,y*sy) for x,y in m['polygon']]
        draw.line(points+[points[0]],fill=COLORS[r['status']],width=2 if r['status']=='low' else 1)
    image.save(OUT/'a_rgb_structure.jpg',quality=95)
    anomalies=[r for r in review['records'] if r['final']=='abnormal'];frames={r['image_id'] for r in anomalies}
    observations=ROOT/'re/module_observations.csv';groups=defaultdict(list)
    with observations.open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['image_id'] in frames:groups[r['image_id']].append(r)
    thermal={};frame_stats={};case_results={}
    for name,rows in groups.items():
        items=[{'id':r['module_id'],'polygon':json.loads(r['quad'])} for r in rows]
        size=(int(rows[0]['img_w']),int(rows[0]['img_h']))
        result=assess_two_rows(items,size);thermal[name]={item['id']:{**res,'polygon':item['polygon']} for item,res in zip(items,result)}
        frame_stats[name]=dict(Counter(r['status'] for r in result))
        image=Image.open(ROOT/'image'/(name+'.JPG')).convert('RGB');draw=ImageDraw.Draw(image)
        for item,res in zip(items,result):
            points=[tuple(p) for p in item['polygon']];draw.line(points+[points[0]],fill=COLORS[res['status']],width=3)
            if res['status']!='supported':draw.text(points[0],item['id'],fill=COLORS[res['status']],stroke_width=1,stroke_fill='black')
        for r in anomalies:
            if r['image_id']==name:
                case_results[r['module_uid']]=thermal[name].get(str(r['module_id']))
                p=thermal[name][str(r['module_id'])]['polygon'];draw.line([tuple(x) for x in p]+[tuple(p[0])],fill='white',width=5)
        image.save(OUT/(name+'_structure.jpg'),quality=95)
    atomic_json(OUT/'thermal_structure.json',{'version':VERSION,'source_sha256':digest(observations),'frames':thermal,'frame_counts':frame_stats,'anomalies':case_results})
    summary={'rgb_a_counts':dict(a_counts),'rgb_total_counts':dict(Counter(r['status'] for r in rgb)),
             'thermal_frame_counts':frame_stats,'anomalies':case_results,'meaning':'supported = two-row geometry evidence, not verified identity; low = review flag, not deletion or normal diagnosis'}
    atomic_json(OUT/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=True,indent=2))


if __name__=='__main__':main()

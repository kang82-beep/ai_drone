"""Map-reference alignment candidate, not surveyed module registration."""
from pathlib import Path
import json, math, hashlib
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_map_alignment';OUT.mkdir(exist_ok=True)
layout_path=ROOT/'shinan3_viewer/assets/layout.json'
data=json.loads(layout_path.read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'results/shinan3_satellite/plant_manifest.json').read_text(encoding='utf-8'))
tile=manifest['mosaics'][0];world=256*2**tile['zoom']
def ll(px,py):
    u=(tile['tile_x0']*256+px)/world;v=(tile['tile_y0']*256+py)/world
    return [math.degrees(math.atan(math.sinh(math.pi*(1-2*v)))),u*360-180]
# Roof centres read visually from the georeferenced, north-up map image.
# Roof centre vs floor centre offset/parallax remains unresolved.
pixels={'S3-ER1':[379,728],'S3-ER2':[834,531],'S3-ER3':[899,531]}
rows=[];targets=[];anchors=[]
for b in data['buildings']:
    x,n=b['center'];px,py=pixels[b['id']]
    rows.extend([[x,n,1,0],[-n,x,0,1]]);targets.extend([px,py])
    anchors.append({'id':b['id'],'x':x,'n':n,'pixel':[px,py],'latlon':ll(px,py),'evidence':'visually picked roof centre; floor/roof displacement uncorrected'})
a,b,tx,ty=np.linalg.lstsq(np.array(rows),np.array(targets),rcond=None)[0]
def pixel(x,n):return [a*x+b*n+tx,b*x-a*n+ty]
for item in anchors:
    item['fit_residual_m']=float(np.linalg.norm(np.array(pixel(item['x'],item['n']))-item['pixel'])*tile['meters_per_pixel_at_address'])
im=Image.open(ROOT/'results/shinan3_satellite/plant_overview.jpg').convert('RGB')
draw=ImageDraw.Draw(im,'RGBA')
for g in data['groups']:
    x0,n0,x1,n1=g['bounds'];draw.line([tuple(pixel(x0,n0)),tuple(pixel(x1,n0)),tuple(pixel(x1,n1)),tuple(pixel(x0,n1)),tuple(pixel(x0,n0))],fill=(0,255,255,130),width=1)
for item in anchors:
    x,y=item['pixel'];draw.ellipse((x-6,y-6,x+6,y+6),outline='red',width=2);draw.text((x+8,y),item['id'],fill='red')
im.save(OUT/'map_drawing_overlay.png')
modules=[]
for g in data['groups']:
    for row in range(2):
        for col in range(10):
            x=g['bounds'][0]+col*1.008+.4915;n=g['bounds'][1]+row*1.425+.7125
            lat,lon=ll(*pixel(x,n))
            modules.append({'id':f"{g['id']}-R{row+1}-M{col+1:02}",'x':x,'n':n,'latitude':lat,'longitude':lon,'status':'map_alignment_candidate'})
report={'status':'visual_map_alignment_candidate','anchors':anchors,'transform_xn_to_pixel':{'a':a,'b':b,'tx':tx,'ty':ty},'layout_sha256':hashlib.sha256(layout_path.read_bytes()).hexdigest(),'imagery':manifest,'layout_source_sha256':data['source_sha256'],'module_count':len(modules),'limitations':['Three roof centres used; two are close together. Not independent surveyed control points.','Map acquisition date unknown; building parallax and map absolute error unresolved.','Do not auto-assign thermal observations to individual modules using this registration.']}
(OUT/'alignment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'module_geolocation_candidates.json').write_text(json.dumps(modules,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report['anchors'],ensure_ascii=False,indent=2))

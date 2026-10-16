"""Recover array strips from scanned SA-E-11210. Original PDF stays read-only."""
from pathlib import Path
import cv2, numpy as np, json
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan2_review';SRC=OUT/'page_14.png'
im=np.array(Image.open(SRC).convert('RGB'));h,w=im.shape[:2]
print('image',w,h)
sx=w/1863;sy=h/1312
# Dimensioned upper array baseline: 344.320 m spans x=503..1520 in review raster.
scale=(1520-503)*sx/344.320
gray=cv2.cvtColor(im,cv2.COLOR_RGB2GRAY);mask=(gray<165).astype('uint8')*255
roi=np.zeros_like(mask);roi[int(120*sy):int(1010*sy),int(498*sx):int(1528*sx)]=mask[int(120*sy):int(1010*sy),int(498*sx):int(1528*sx)]
horizontal=cv2.morphologyEx(roi,cv2.MORPH_OPEN,np.ones((1,28),np.uint8))
close=cv2.morphologyEx(horizontal,cv2.MORPH_CLOSE,np.ones((7,1),np.uint8))
num,labels,stats,centers=cv2.connectedComponentsWithStats(close)
rows=[]
for x,y,rw,rh,area in stats[1:]:
    if 55*sx<rw<255*sx and 5*sy<rh<15*sy and area/(rw*rh)>.25:
        count=round((rw/scale+.1)/10.335)
        if count not in [2,3,4,5,6,7,8]:continue
        rows.append({'box':[int(x),int(y),int(rw),int(rh)],'groups':count,'length_error_m':round(rw/scale-(count*10.335-.1),3)})
rows.sort(key=lambda r:(r['box'][1],r['box'][0]))
preview=Image.fromarray(im);draw=ImageDraw.Draw(preview)
for i,r in enumerate(rows):
    x,y,rw,rh=r['box'];draw.rectangle((x,y,x+rw,y+rh),outline='red',width=2);draw.text((x+2,y-9),f'{i+1}:{r["groups"]}',fill='blue')
preview.save(OUT/'array_extraction_overlay.png')
(OUT/'array_strips.json').write_text(json.dumps({'image_size':[w,h],'pixels_per_metre':scale,'rows':rows,'groups':sum(r['groups'] for r in rows)},indent=2),encoding='utf-8')
print('strips',len(rows),'groups',sum(r['groups'] for r in rows),'modules',sum(r['groups'] for r in rows)*20)
print('worst',sorted(rows,key=lambda r:abs(r['length_error_m']),reverse=True)[:8])

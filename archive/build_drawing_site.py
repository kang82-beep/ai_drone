"""Extract and review the full PDF panel layout; RGB is deliberately not an input."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results'/'drawing_site'


def main():
    source=ROOT/'tmp'/'pdfs'/'shinan-page-14.png'
    if not source.exists():
        from pypdf import PdfReader
        source.parent.mkdir(parents=True,exist_ok=True)
        reader=PdfReader(r'C:\Users\kangw\Downloads\신안군 태양광 발전단지 2차 (5MW) 조성공사.pdf')
        reader.pages[13].images[0].image.save(source)
    im=cv2.imread(str(source),0)
    binary=cv2.threshold(im,170,255,cv2.THRESH_BINARY_INV)[1]
    binary=cv2.dilate(binary,np.ones((5,3),np.uint8))
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,200),np.uint8))
    _,_,stats,_=cv2.connectedComponentsWithStats(horizontal)
    lines=[(int(x),float(y+h/2),int(w)) for x,y,w,h,a in stats[1:]
           if 280<w<1400 and 3<h<25 and 2500<x<8100 and 630<y<5350]
    rows=[]
    for x,y,w in lines:
        middle=[q for q in lines if abs(q[0]-x)<7 and abs(q[2]-w)<15 and 20<q[1]-y<30]
        end=[q for q in lines if abs(q[0]-x)<7 and abs(q[2]-w)<15 and 44<q[1]-y<58]
        if middle and end:rows.append({'pixel_box':[x,y,w,end[0][1]-y],'method':'three_grid_lines'})
    # Traced against full page and surviving grid lines, in 1862x1312 review coordinates.
    # These 18 rows cross construction/dimension lines and fail the three-line detector.
    repairs=[(1398,129,122),(1020,199,245),(502,423,245),(758,424,245),
             (624,445,123),(758,446,245),(623,617,123),(757,618,245),(1274,620,123),
             (623,649,123),(756,650,245),(1141,651,123),(1274,652,123),
             (622,757,123),(756,758,245),(650,784,95),(756,784,245),(1018,785,245)]
    sx,sy=im.shape[1]/1862,im.shape[0]/1312
    for x,y,w in repairs:rows.append({'pixel_box':[x*sx,y*sy,w*sx,9.5*sy],'method':'visually_traced_grid'})
    lanes_px=[503,758,1020,1275]
    lanes_m=[0,86.58,175.16,261.74]
    for r in rows:
        x,y,w,h=r['pixel_box'];px=x/sx
        lane=min(range(4),key=lambda i:abs(px-lanes_px[i]) if px>=lanes_px[i]-5 else 10000)
        offset=round((px-lanes_px[lane])/30.65)
        groups=round(w/(161.4))
        if groups not in (2,3,4,8):raise ValueError(f'Unexpected row width: {r}')
        r.update(lane=lane+1,groups=groups,columns=groups*10,
                 x=lanes_m[lane]+offset*10.335,
                 y=(y/sy-130)*292.077/876,
                 width=groups*10.235+(groups-1)*.100)
    rows.sort(key=lambda r:(r['lane'],r['y'],r['x']))
    for i,r in enumerate(rows,1):r['id']=f'DRAW-STRIP-{i:03d}'
    count=sum(r['columns']*2 for r in rows)
    payload={'schema_version':1,'units':'m','basis':'PDF only; no RGB coordinates',
             'source':'PDF p.14 SA-E-11210 + p.10 SA-E-11110 + p.11 SA-E-11120',
             'extent_width_m':344.32,'rows':rows,'module_count':count,'rated_kwp':count*.245,
             'position_status':'X aligned to dimension chains; Y digitized from scan using 292077mm chain',
             'clearance_m':None,'terrain':None,'support_structure':None,
             'lane_note':'L1–L4 are spatial lanes, NOT inverter A–E assignments',
             'boundary_review_px':[[322,345],[1587,88],[1585,285],[1455,374],[1450,445],[1410,445],[1460,720],[1420,1015],[1250,1055],[810,1090],[660,1050]],
             'footprints_review_px':[[513,541,35,62],[1053,672,54,30]],
             'review_canvas':[1862,1312],'pending':['Scan digitization tolerance','Supports/foundations and ground clearance','Building height','Inverter A–E mapping','Absolute site coordinates']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'site_layout.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    review=Image.fromarray(im).convert('RGB').resize((1862,1312));d=ImageDraw.Draw(review)
    for r in rows:
        x,y,w,h=r['pixel_box'];color='#ef9700' if r['method']=='visually_traced_grid' else '#009b68'
        d.rectangle((x/sx,y/sy,(x+w)/sx,(y+h)/sy),outline=color,width=2)
    review.save(OUT/'drawing_layout_review.png')
    print(f'{len(rows)} strips / {count} modules / {count*.245:.2f} kWp')


if __name__=='__main__':main()

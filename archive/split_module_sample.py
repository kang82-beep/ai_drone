"""Produce a reviewable, bounded RGB module segmentation pilot (not a full-site detector)."""
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform
from PIL import Image, ImageDraw

SOURCE = Path(__file__).resolve().parent / '3d' / 'result (1).tif'
OUTPUT = Path(__file__).resolve().parent / 'results' / 'module_split_pilot'
WINDOW = (18000, 13780, 1000, 1050)


def segment(rgb):
    """Blue surfaces separated by frames; thresholds calibrated only for this pilot."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (85,55,35), (130,255,255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3,3), np.uint8))
    contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if x<=2 or y<=2 or x+w>=rgb.shape[1]-2 or y+h>=rgb.shape[0]-2:
            continue  # Exclude clipped modules, do not invent their boundaries.
        if not (80<=w<=110 and 125<=h<=170 and cv2.contourArea(contour)/(w*h)>0.8):
            continue
        (cx,cy),(rw,rh),angle=cv2.minAreaRect(contour)
        # Blue surface boundary only: outer frame is not claimed to be surveyed.
        polygon=cv2.boxPoints(((cx,cy),(rw,rh),angle)).tolist()
        candidates.append({'center':[cx,cy],'polygon':polygon})
    # Order spatial rows first; frames across a row have slight image slope.
    candidates.sort(key=lambda m:m['center'][1])
    rows=[]
    for item in candidates:
        if not rows or abs(item['center'][1]-rows[-1][0]['center'][1])>45:
            rows.append([])
        rows[-1].append(item)
    result=[]
    for row_index,row in enumerate(rows,1):
        for column,item in enumerate(sorted(row,key=lambda m:m['center'][0]),1):
            item.update(id=f'P01-R{row_index:02d}-M{column:02d}',row=row_index,column=column)
            result.append(item)
    return result


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    x,y,w,h=WINDOW
    with rasterio.open(SOURCE) as src:
        rgb=src.read([1,2,3],window=Window(*WINDOW)).transpose(1,2,0)
        modules=segment(rgb)
        features=[]
        for module in modules:
            pixel_polygon=[[x+px,y+py] for px,py in module['polygon']]
            projected=[src.transform*(px,py) for px,py in pixel_polygon]
            lons,lats=transform(src.crs,'EPSG:4326',[p[0] for p in projected],[p[1] for p in projected])
            ring=[list(p) for p in zip(lons,lats)];ring.append(ring[0])
            cx,cy=module['center']
            east,north=src.transform*(x+cx,y+cy)
            module.update(source_pixel_center=[x+cx,y+cy],easting=east,northing=north)
            features.append({'type':'Feature','properties':{'id':module['id'],'review_status':'candidate','boundary':'blue_surface','source_crs':str(src.crs)},'geometry':{'type':'Polygon','coordinates':[ring]}})
        metadata={'source':str(SOURCE),'window':WINDOW,'crs':str(src.crs),'pixel_size':src.res,'status':'pilot_candidates_not_surveyed','modules':modules}
    original=Image.fromarray(rgb)
    original.save(OUTPUT/'original.png')
    overlay=original.copy();draw=ImageDraw.Draw(overlay)
    for index,module in enumerate(modules,1):
        points=[tuple(p) for p in module['polygon']]
        draw.line(points+[points[0]],fill='#00ff91',width=3)
        cx,cy=module['center']
        label=f'{index:02d}'
        draw.rectangle((cx-13,cy-9,cx+13,cy+9),fill='#092d25')
        draw.text((cx-6,cy-6),label,fill='white')
        module['display_number']=index
    overlay.save(OUTPUT/'modules_numbered.png')
    (OUTPUT/'modules.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'modules.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUTPUT/'modules.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['number','temporary_id','source_pixel_x','source_pixel_y','easting','northing','status'])
        for m in modules:writer.writerow([m['display_number'],m['id'],*m['source_pixel_center'],m['easting'],m['northing'],'candidate'])
    # Existing overview is for location context only, not for coordinate extraction.
    preview=OUTPUT.parents[1]/'tmp'/'ortho'/'preview.jpg'
    if preview.exists():
        locator=Image.open(preview).convert('RGB');d=ImageDraw.Draw(locator)
        with rasterio.open(SOURCE) as src:
            sx,sy=locator.width/src.width,locator.height/src.height
        d.rectangle((x*sx,y*sy,(x+w)*sx,(y+h)*sy),outline='#ff3030',width=4)
        d.text((x*sx+5,y*sy-15),'PILOT 01',fill='#ff3030')
        locator.save(OUTPUT/'location.jpg')
    print(f'{len(modules)} candidates saved to {OUTPUT}')


if __name__=='__main__':
    main()

"""Extend the reviewed RGB segmentation pilot over the orthomosaic in bounded tiles."""
import json
from pathlib import Path
import cv2
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform
from PIL import Image, ImageDraw

SOURCE=Path(__file__).resolve().parent/'3d'/'result (1).tif'
OUTPUT=Path(__file__).resolve().parent/'results'/'module_split_site'
CORE=3584
MARGIN=256


def detect(rgb):
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    mask=cv2.inRange(hsv,(85,55,35),(130,255,255))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    found=[]
    for c in contours:
        x,y,w,h=cv2.boundingRect(c)
        if x<2 or y<2 or x+w>=rgb.shape[1]-2 or y+h>=rgb.shape[0]-2:continue
        fill=cv2.contourArea(c)/(w*h)
        if not (65<=w<=125 and 105<=h<=190 and fill>=0.65):continue
        rect=cv2.minAreaRect(c)
        status='candidate' if 80<=w<=110 and 125<=h<=170 and fill>0.8 else 'review'
        found.append({'center':list(rect[0]),'polygon':cv2.boxPoints(rect).tolist(),'status':status,'fill':round(fill,3)})
    return found


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    modules=[]
    with rasterio.open(SOURCE) as src:
        overview=Image.new('RGB',(2200,round(src.height/src.width*2200)))
        sx,sy=overview.width/src.width,overview.height/src.height
        total=((src.width+CORE-1)//CORE)*((src.height+CORE-1)//CORE)
        tile=0
        for y in range(0,src.height,CORE):
            for x in range(0,src.width,CORE):
                x0,y0=max(0,x-MARGIN),max(0,y-MARGIN)
                x1,y1=min(src.width,x+CORE+MARGIN),min(src.height,y+CORE+MARGIN)
                rgb=src.read([1,2,3],window=Window(x0,y0,x1-x0,y1-y0)).transpose(1,2,0)
                for item in detect(rgb):
                    cx,cy=item['center'];cx+=x0;cy+=y0
                    # Each center belongs to exactly one core, including seam modules.
                    if not (x<=cx<min(x+CORE,src.width) and y<=cy<min(y+CORE,src.height)):continue
                    item['center']=[cx,cy]
                    item['polygon']=[[px+x0,py+y0] for px,py in item['polygon']]
                    modules.append(item)
                crop=Image.fromarray(rgb[y-y0:min(y+CORE,src.height)-y0,x-x0:min(x+CORE,src.width)-x0])
                box=(round(x*sx),round(y*sy),round(min(x+CORE,src.width)*sx),round(min(y+CORE,src.height)*sy))
                overview.paste(crop.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.LANCZOS),box[:2])
                tile+=1
                print(f'Tile {tile}/{total}: {len(modules)} candidates',flush=True)
        modules.sort(key=lambda m:(round(m['center'][1]/50),m['center'][0]))
        features=[]
        for i,m in enumerate(modules,1):
            m['id']=f'S01-M{i:05d}'
            coords=[src.transform*tuple(p) for p in m['polygon']]
            lon,lat=transform(src.crs,'EPSG:4326',[p[0] for p in coords],[p[1] for p in coords])
            ring=[list(p) for p in zip(lon,lat)];ring.append(ring[0])
            features.append({'type':'Feature','properties':{'id':m['id'],'status':m['status'],'boundary':'blue_surface'},'geometry':{'type':'Polygon','coordinates':[ring]}})
        data={'source':str(SOURCE),'width':src.width,'height':src.height,'crs':str(src.crs),'pixel_size':src.res,'method':'RGB threshold, overlapping tiles, center ownership','modules':modules}
    overview.save(OUTPUT/'overview_rgb.jpg',quality=93)
    draw=ImageDraw.Draw(overview)
    for m in modules:
        ps=[(px*sx,py*sy) for px,py in m['polygon']]
        draw.line(ps+[ps[0]],fill='#00ff91' if m['status']=='candidate' else '#ffad32',width=1)
    overview.save(OUTPUT/'overview_modules.jpg',quality=95)
    (OUTPUT/'modules.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    (OUTPUT/'modules.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
    summary={'total':len(modules),'candidate':sum(m['status']=='candidate' for m in modules),'review':sum(m['status']=='review' for m in modules),'tiles':total}
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(summary,flush=True)


if __name__=='__main__':main()

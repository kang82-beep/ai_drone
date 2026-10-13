"""Locate the supplied address and save a small VWorld imagery reference mosaic."""
from pathlib import Path
import json, math, datetime, sys
import requests
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_satellite';OUT.mkdir(exist_ok=True)
key=json.loads((ROOT/'config.local.json').read_text(encoding='utf-8-sig'))['VWORLD_API_KEY']
addresses=[('ROAD','전남광주통합특별시 신안군 팔금면 오림진고길 167'),('ROAD','전라남도 신안군 팔금면 오림진고길 167'),('PARCEL','전라남도 신안군 팔금면 진고리 55-8')]
responses=[]
site_only='--site-only' in sys.argv
if site_only:
    responses=json.loads((OUT/'geocode.json').read_text(encoding='utf-8'))
    payload=responses[-1]['response'];address=responses[-1]['query']
for kind,address in ([] if site_only else addresses):
    try:
        r=requests.get('https://api.vworld.kr/req/address',params={'service':'address','request':'getcoord','version':'2.0','crs':'epsg:4326','address':address,'format':'json','type':kind,'key':key},timeout=30)
        payload=r.json().get('response',{})
    except Exception as e:
        print('NETWORK_OR_RESPONSE_ERROR',type(e).__name__);raise SystemExit(2)
    responses.append({'query':address,'type':kind,'response':payload})
    print(json.dumps({'query':address,'status':payload.get('status'),'result':payload.get('result'),'error':payload.get('error')},ensure_ascii=False))
    if payload.get('status')=='OK':break
(OUT/'geocode.json').write_text(json.dumps(responses,ensure_ascii=False,indent=2),encoding='utf-8')
if payload.get('status')!='OK':raise SystemExit(3)
point=payload['result']['point'];lon,lat=float(point['x']),float(point['y'])
manifest={'address':address,'longitude':lon,'latitude':lat,'provider':'VWorld / NGII','retrieved_at':datetime.datetime.now().astimezone().isoformat(),'imagery_capture_date':'not supplied by WMTS tile response','address_point_is_not_verified_phase3_boundary':True,'mosaics':[]}
if site_only:
    lon+=.00265;lat+=.00060
    manifest['visual_overview_center']={'longitude':lon,'latitude':lat,'method':'Visual selection of array area from z17 mosaic, not surveyed control point'}
for z,radius in ([(18,2)] if site_only else [(17,2),(19,2)]):
    n=2**z;tx=(lon+180)/360*n;ty=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n
    x0,y0=math.floor(tx)-radius,math.floor(ty)-radius;size=2*radius+1
    mosaic=Image.new('RGB',(size*256,size*256+44),'white')
    for dy in range(size):
        for dx in range(size):
            url=f'https://api.vworld.kr/req/wmts/1.0.0/{key}/Satellite/{z}/{y0+dy}/{x0+dx}.jpeg'
            try:
                response=requests.get(url,timeout=30)
                if response.status_code!=200 or not response.content.startswith(b'\xff\xd8'):raise ValueError('not JPEG')
                import io
                tile=Image.open(io.BytesIO(response.content)).convert('RGB')
            except Exception as e:
                print('TILE_ERROR',z,dx,dy,type(e).__name__);raise SystemExit(2)
            mosaic.paste(tile,(dx*256,dy*256))
    d=ImageDraw.Draw(mosaic);px,py=(tx-x0)*256,(ty-y0)*256
    if not site_only:
        d.ellipse((px-10,py-10,px+10,py+10),outline='#ff4040',width=3)
        d.line((px-15,py,px+15,py),fill='#ff4040',width=2);d.line((px,py-15,px,py+15),fill='#ff4040',width=2)
    d.text((12,size*256+6),f'VWorld / NGII | z{z} | N up | '+('Array area selected visually; no surveyed alignment' if site_only else 'red cross = address point (not site boundary)'),fill='black')
    d.text((12,size*256+22),'Retrieved '+manifest['retrieved_at'][:10]+' | imagery acquisition date unverified',fill='black')
    name='plant_overview.jpg' if site_only else f'surroundings_z{z}.jpg';mosaic.save(OUT/name,quality=94)
    manifest['mosaics'].append({'file':name,'zoom':z,'tile_x0':x0,'tile_y0':y0,'tiles_per_side':size,'meters_per_pixel_at_address':156543.03392804097*math.cos(math.radians(lat))/n})
    print('SAVED',name)
(OUT/('plant_manifest.json' if site_only else 'imagery_manifest.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

"""Reviewable RGB array refinement, per window or tiled over the orthomosaic.

Writes a NEW directory. Does not replace existing module IDs or review evidence.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform

from pv_inspector.array_refinement import VERSION, refine_arrays

ROOT = Path(__file__).resolve().parent


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def render(rgb, result, path):
    image=Image.fromarray(rgb); draw=ImageDraw.Draw(image)
    for a in result['arrays']:
        p=[tuple(x) for x in a['polygon']];draw.line(p+[p[0]],fill='#00baff',width=2)
    for slot in result['slots']:
        if slot['status']=='unconfirmed':
            p=[tuple(x) for x in slot['expected_polygon']];draw.line(p+[p[0]],fill='#ffae32',width=2)
    for m in result['modules']:
        p=[tuple(x) for x in m['polygon']];draw.line(p+[p[0]],fill='#00ff91',width=2)
        x,y=m['center'];draw.text((x-12,y-5),f"{m['row']}-{m['column']}",fill='white',stroke_width=1,stroke_fill='black')
    image.save(path)


def globalize(result, x, y, prefix, core_bounds=None):
    """Tile ownership uses center, not intersection. IDs explicitly remain local."""
    def shift(poly):return [[float(px+x),float(py+y)] for px,py in poly]
    def owns(center):
        if core_bounds is None:return True
        left,top,right,bottom=core_bounds
        return left<=center[0]+x<right and top<=center[1]+y<bottom
    modules=[];review=[];slots=[]
    for m in result['modules']:
        if owns(m['center']):
            modules.append({**m,'id':prefix+m['id'],'array_id':prefix+m['array_id'],
                            'polygon':shift(m['polygon']),'center':[m['center'][0]+x,m['center'][1]+y],
                            'source_ids':[prefix+s for s in m['source_ids']]})
    for m in result['unresolved']:
        center=np.mean(m['polygon'],axis=0)
        if owns(center):review.append({**m,'id':prefix+m['id'],'polygon':shift(m['polygon']),
                                       'center':[float(center[0]+x),float(center[1]+y)]})
    for s in result['slots']:
        center=np.mean(s['expected_polygon'],axis=0)
        if owns(center):
            evidence=dict(s['evidence'])
            if 'polygon' in evidence:evidence['polygon']=shift(evidence['polygon'])
            slots.append({**s,'id':prefix+s['id'],'array_id':prefix+s['array_id'],
                          'expected_polygon':shift(s['expected_polygon']),'evidence':evidence})
    return modules,review,slots


def write_report(out, summary, images):
    figures=''.join(f'<figure><img src="{html.escape(name)}"><figcaption>{html.escape(title)}</figcaption></figure>' for name,title in images)
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>배열 기반 모듈 검토</title>
<style>body{background:#101b28;color:#e6edf5;font:16px system-ui;max-width:1450px;margin:30px auto;padding:20px}img{max-width:100%}figure{margin:24px 0}pre{white-space:pre-wrap;background:#192b40;padding:16px}a{color:#68d5ff}</style>
<h1>배열 기반 모듈 검토</h1><p>청록: 배열 · 초록: 원본 경계 지지 · 주황: 미확인 예상 칸. 색은 고장/정상 판정이 아닙니다.</p>
<p>네 경계가 확인된 칸만 모듈 후보로 출력합니다. 미확인 칸과 원본 미해결 후보는 별도 보존합니다. 임시 번호는 실제 설비 번호가 아닙니다.</p>'''
    page+='<pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'+figures
    page+='<p><a href="modules.json">전체 판정 JSON</a> · <a href="modules.geojson">지도용 후보</a></p></html>'
    (out/'review.html').write_text(page,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'3d'/'result (1).tif')
    parser.add_argument('--window',type=int,nargs=4,metavar=('X','Y','W','H'),default=[18000,13780,1000,1050])
    parser.add_argument('--full-site',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true',help='Reuse matching tile evidence after verifying version and pixel fingerprints')
    args=parser.parse_args();out=args.output
    if out.exists() and any(out.iterdir()) and not args.resume:raise FileExistsError('Use a new empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    all_modules=[];all_review=[];all_slots=[];summaries=[];images=[]
    with rasterio.open(args.source) as src:
        if src.count<3 or src.dtypes[0]!='uint8':raise ValueError('An 8-bit RGB orthomosaic is required')
        if args.full_site:
            core=3584;margin=256
            windows=[]
            for y in range(0,src.height,core):
                for x in range(0,src.width,core):
                    x0,y0=max(0,x-margin),max(0,y-margin)
                    x1,y1=min(src.width,x+core+margin),min(src.height,y+core+margin)
                    windows.append((x0,y0,x1-x0,y1-y0,(x,y,min(x+core,src.width),min(y+core,src.height))))
        else:
            x,y,w,h=args.window
            if min(x,y)<0 or min(w,h)<=0 or x+w>src.width or y+h>src.height:raise ValueError('Window outside source')
            windows=[(x,y,w,h,None)]
        for index,(x,y,w,h,bounds) in enumerate(windows):
            rgb=src.read([1,2,3],window=Window(x,y,w,h)).transpose(1,2,0)
            fingerprint=hashlib.sha256(rgb.tobytes()).hexdigest()
            tile_path=out/f'tile_{index:03d}.json'
            cached=json.loads(tile_path.read_text(encoding='utf-8')) if args.resume and tile_path.exists() else None
            if cached and (cached.get('window')!=[x,y,w,h] or cached.get('pixel_sha256')!=fingerprint or cached.get('version')!=VERSION):
                raise ValueError(f'Tile {index} source or algorithm version changed; use a new directory')
            result=cached or refine_arrays(rgb)
            modules,review,slots=globalize(result,x,y,f'T{index:03d}-',bounds)
            all_modules.extend(modules);all_review.extend(review);all_slots.extend(slots)
            summary=dict(tile=index,window=[x,y,w,h],**result['summary'],owned_modules=len(modules))
            summaries.append(summary)
            # Detailed provenance is separated per tile to bound memory use.
            if cached is None:dump(tile_path,dict(window=[x,y,w,h],pixel_sha256=fingerprint,**result))
            if not args.full_site:
                Image.fromarray(rgb).save(out/'original.png');render(rgb,result,out/'refined.png')
                images=[('original.png','원본'),('refined.png','배열 및 원본 경계 검토')]
            print(f'{index+1}/{len(windows)}: {summary}',flush=True)
        # Remove only near-identical accepted seam proposals. Never merge by GPS.
        from scipy.spatial import cKDTree
        import cv2
        seam_duplicates=set()
        if all_modules:
            tree=cKDTree([m['center'] for m in all_modules])
            for i,j in sorted(tree.query_pairs(20)):
                a=np.float32(all_modules[i]['polygon']);b=np.float32(all_modules[j]['polygon'])
                overlap=cv2.intersectConvexConvex(a,b)[0]
                if overlap/max(cv2.contourArea(a)+cv2.contourArea(b)-overlap,1)>.72:
                    if i not in seam_duplicates:seam_duplicates.add(j)
        seam_audit=[dict(id=all_modules[i]['id'],reason='near_identical_tile_seam') for i in sorted(seam_duplicates)]
        all_modules=[m for i,m in enumerate(all_modules) if i not in seam_duplicates]
        features=[]
        for m in all_modules:
            coords=[src.transform*tuple(p) for p in m['polygon']]
            lon,lat=transform(src.crs,'EPSG:4326',[p[0] for p in coords],[p[1] for p in coords])
            ring=[list(p) for p in zip(lon,lat)];ring.append(ring[0])
            features.append(dict(type='Feature',properties={k:m[k] for k in ('id','status','origin','array_id','row','column')},
                                 geometry=dict(type='Polygon',coordinates=[ring])))
        stat=args.source.stat()
        summary=dict(tiles=len(windows),image_supported_candidates=len(all_modules),
                     unconfirmed_slots=sum(s['status']=='unconfirmed' for s in all_slots),
                     unresolved_candidates=len(all_review),seam_duplicates=len(seam_duplicates),
                     meaning='Image-supported proposals, not surveyed modules or fault diagnoses')
        data=dict(version=VERSION,source=str(args.source.resolve()),source_size=stat.st_size,source_mtime_ns=stat.st_mtime_ns,
                  width=src.width,height=src.height,crs=str(src.crs),method='local two-row grids with four image boundaries',
                  modules=all_modules,review_candidates=all_review,slots=all_slots,tiles=summaries,
                  seam_audit=seam_audit,summary=summary)
        if args.full_site:
            from rasterio.enums import Resampling
            width=2200;height=round(width*src.height/src.width)
            rgb=src.read([1,2,3],out_shape=(3,height,width),resampling=Resampling.bilinear).transpose(1,2,0)
            overview=Image.fromarray(rgb);overview.save(out/'overview_rgb.jpg',quality=93)
            draw=ImageDraw.Draw(overview)
            for m in all_modules:
                pts=[(px*width/src.width,py*height/src.height) for px,py in m['polygon']]
                draw.line(pts+[pts[0]],fill='#00ff91',width=1)
            overview.save(out/'overview_modules.jpg',quality=95)
            images=[('overview_rgb.jpg','전체 원본'),('overview_modules.jpg','원본 경계가 지지하는 모듈 후보')]
    dump(out/'modules.json',data);dump(out/'summary.json',summary)
    dump(out/'modules.geojson',dict(type='FeatureCollection',features=features))
    write_report(out,summary,images)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

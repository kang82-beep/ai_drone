"""Evidence-based A-zone review. Coordinates are native pixels unless stated otherwise."""
from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from shapely.geometry import Point, Polygon, shape

from .files import parse_tv_and_key5
from .site_structures import raised_modules
from .thermal import _load_raw_float32_auto, measure_module_raw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/a_module_review'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if Path(name).exists(): Path(name).unlink()


def project(points, matrix):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or not np.isfinite(p).all():
        raise ValueError('유효한 2차원 좌표가 필요합니다.')
    q = np.c_[p, np.ones(len(p))] @ np.asarray(matrix, dtype=float).T
    if not np.isfinite(q).all() or np.any(np.abs(q[:, 2]) < 1e-9):
        raise ValueError('투영할 수 없는 좌표입니다.')
    return q[:, :2] / q[:, 2, None]


def valid_hull(points):
    p = np.asarray(points, dtype=np.float32)
    return len(p) >= 3 and cv2.contourArea(cv2.convexHull(p)) > 1


def inside_hull(points, support):
    if not valid_hull(support): return False
    hull = cv2.convexHull(np.asarray(support, dtype=np.float32))
    return all(cv2.pointPolygonTest(hull, tuple(map(float, p)), False) >= 0 for p in points)


def fit_landmarks(pairs, max_error):
    """Leave-one-out validation; never call an exact four-point fit validated."""
    p = np.asarray(pairs, dtype=float)
    if p.ndim != 3 or p.shape[1:] != (2, 2) or len(p) < 6 or not np.isfinite(p).all():
        raise ValueError('같은 위치의 대응점이 최소 6쌍 필요합니다.')
    src, dst = p[:, 0], p[:, 1]
    if not valid_hull(src) or not valid_hull(dst):
        raise ValueError('대응점을 한 줄이 아닌 넓은 영역에 분산해 주세요.')
    if len(np.unique(src, axis=0)) != len(src) or len(np.unique(dst, axis=0)) != len(dst):
        raise ValueError('중복 대응점은 사용할 수 없습니다.')
    errors = []
    for i in range(len(p)):
        keep = np.arange(len(p)) != i
        h, _ = cv2.findHomography(src[keep], dst[keep], 0)
        if h is None: raise ValueError('대응점 배치가 불안정합니다.')
        errors.append(float(np.linalg.norm(project(src[i:i+1], h)[0] - dst[i])))
    if max(errors) > max_error:
        raise ValueError(f'별도 검토점 최대 오차 {max(errors):.1f}px > {max_error:.1f}px. 대응점을 수정해 주세요.')
    h, _ = cv2.findHomography(src, dst, 0)
    if h is None or abs(np.linalg.det(h)) < 1e-12:
        raise ValueError('정합 계산에 실패했습니다.')
    return {'matrix': h.tolist(), 'method': 'manual_landmarks_leave_one_out', 'pairs': p.tolist(),
            'support': src.tolist(), 'loo_max_px': max(errors), 'loo_median_px': float(np.median(errors)),
            'status': 'geometry_checked_identity_unconfirmed'}


def rgb_registration(rgb_file, ortho_file):
    """Generate a reviewable RGB/ortho proposal, never an identity confirmation."""
    cv2.setNumThreads(4); cv2.setRNGSeed(42)
    def load(path, width):
        im = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if im is None: raise ValueError('영상을 읽을 수 없습니다.')
        scale = min(1., width/im.shape[1])
        return cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), scale
    a, sa = load(str(rgb_file), 1600); b, sb = load(str(ortho_file), 1800)
    sift = cv2.SIFT_create(nfeatures=9000)
    ka, da = sift.detectAndCompute(a, None); kb, db = sift.detectAndCompute(b, None)
    if da is None or db is None: return {'status': 'needs_landmarks', 'reason': '특징점 부족'}
    matcher = cv2.BFMatcher()
    forward = [x[0] for x in matcher.knnMatch(da, db, k=2) if len(x)==2 and x[0].distance < .68*x[1].distance]
    backward = {(x[0].trainIdx, x[0].queryIdx) for x in matcher.knnMatch(db, da, k=2)
                if len(x)==2 and x[0].distance < .68*x[1].distance}
    matches = [m for m in forward if (m.queryIdx, m.trainIdx) in backward]
    if len(matches) < 30: return {'status': 'needs_landmarks', 'reason': f'상호 일치 특징점 {len(matches)}개'}
    src = np.float32([ka[m.queryIdx].pt for m in matches]); dst = np.float32([kb[m.trainIdx].pt for m in matches])
    order = np.random.default_rng(42).permutation(len(src)); cut = int(.75*len(src))
    train, test = order[:cut], order[cut:]
    h, mask = cv2.findHomography(src[train], dst[train], cv2.RANSAC, 3)
    count = int(mask.sum()) if mask is not None else 0
    if h is None or count < 25 or count/len(train) < .35:
        return {'status': 'needs_landmarks', 'reason': f'정합 지지점 부족 ({count})'}
    held = np.linalg.norm(project(src[test], h)-dst[test], axis=1)
    good = mask.ravel().astype(bool); support = src[train][good]
    coverage = cv2.contourArea(cv2.convexHull(support))/(a.shape[0]*a.shape[1])
    if (held <= 3).sum() < 8 or (held <= 3).mean() < .5 or coverage < .15:
        return {'status': 'needs_landmarks', 'reason': '별도 검토점 또는 특징점 분포 부족'}
    native = np.diag([1/sb, 1/sb, 1.]) @ h @ np.diag([sa, sa, 1.])
    return {'status': 'geometry_checked_identity_unconfirmed', 'method': 'SIFT_mutual_RANSAC_train_holdout',
            'matrix': native.tolist(), 'support': (support/sa).tolist(), 'inliers': count,
            'holdout_count': len(test), 'holdout_within_3px_fraction': float((held <= 3).mean()),
            'coverage': coverage, 'holdout_median_px': float(np.median(held)),
            'pairs': np.stack([support/sa, dst[train][good]/sb], axis=1).tolist()}


def pairing_lookup(folder):
    result = {}
    for path in sorted(Path(folder).glob('*')):
        if path.suffix.lower() not in ('.jpg', '.jpeg'): continue
        _, kind, key = parse_tv_and_key5(str(path))
        if kind == 'V': result.setdefault(key, []).append(path)
    return result


def build_bundle(root=ROOT, output=OUT, auto=True):
    """Prepare native thermal, paired RGB, local orthomosaic and frozen provenance."""
    import rasterio
    from rasterio.windows import Window
    from rasterio.enums import Resampling
    root, output = Path(root), Path(output); output.mkdir(parents=True, exist_ok=True)
    review_path = root/'results/blender_site/thermal_review_registered_a.json'
    review = read_json(review_path)
    if review['validation_scope']['zone'] != 'A': raise ValueError('A구역 데이터만 지원합니다.')
    sources = [review_path, root/'re/modules_dedup.csv', root/'results/drawing_site/site_layout.json', root/'model/zones shinan2 .geojson']
    source_hashes = {str(p.relative_to(root)): digest(p) for p in sources}
    for name, value in review['registration']['fingerprints'].items():
        if digest(root/name)!=value:raise ValueError('도면 정합 기준 자료가 바뀌었습니다. 정합을 먼저 갱신해 주세요.')
    dataset = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()[:20]
    previous = read_json(output/'manifest.json') if (output/'manifest.json').exists() else None
    if previous and previous['dataset_id'] == dataset and all(Path(p).exists() and digest(p)==v for p,v in previous['asset_hashes'].items()):
        return previous
    if previous:
        raise ValueError('원본 또는 기준 자료가 바뀌었습니다. 새 --output 폴더로 검토 자료를 생성하세요.')
    selected = [r for r in review['records'] if r['final']=='abnormal']
    with (root/'re/modules_dedup.csv').open(encoding='utf-8-sig') as f:
        rows = {r['module_uid']: r for r in csv.DictReader(f) if r['module_uid'] in {x['module_uid'] for x in selected}}
    lookup = pairing_lookup(root/'image'); cases=[]; asset_hashes={}
    with rasterio.open(root/'3d/result (1).tif') as src:
        expected = review['orthomosaic']
        if list(src.transform) != expected['transform'] or str(src.crs) != expected['crs']:
            raise ValueError('정사영상 좌표계가 기존 정합과 다릅니다.')
        for r in selected:
            row = rows[r['module_uid']]; case_dir = output/dataset/r['module_uid']; case_dir.mkdir(parents=True, exist_ok=True)
            thermal = root/'image'/(r['image_id']+'.JPG')
            matches = lookup.get(parse_tv_and_key5(str(thermal))[2], [])
            rgb = matches[0] if len(matches)==1 else None
            raw = Path(row['temp_raw']); crop = Path(r['crop']) if r.get('crop') else None
            pos = r['orthomosaic_position']; cx = (pos[0]-expected['offset_x'])/src.res[0]; cy = pos[1]/src.res[1]
            radius=30/src.res[0]
            x0=max(0,int(cx-radius)); y0=max(0,int(cy-radius))
            x1=min(src.width,int(cx+radius)); y1=min(src.height,int(cy+radius))
            width=1800; height=round((y1-y0)/(x1-x0)*width)
            tile=src.read([1,2,3],window=Window(x0,y0,x1-x0,y1-y0),out_shape=(3,height,width),resampling=Resampling.bilinear)
            ortho=case_dir/'orthomosaic.jpg'; Image.fromarray(tile.transpose(1,2,0)).save(ortho,quality=95)
            # Tile pixels -> full orthomosaic local metres, without the display +400 offset.
            tile_to_local=[[((x1-x0)/width)*src.res[0],0,x0*src.res[0]],
                           [0,((y1-y0)/height)*src.res[1],y0*src.res[1]],[0,0,1]]
            case=copy.deepcopy(r)
            case.update(key=r['module_uid'],thermal=str(thermal),rgb=str(rgb) if rgb else None,
                        raw=str(raw) if raw.is_file() else None,ortho=str(ortho),tile_to_local=tile_to_local,
                        bbox=[float(row[k]) for k in ('bbox_x1','bbox_y1','bbox_x2','bbox_y2')],
                        thermal_size=list(Image.open(thermal).size),pairing_status='paired_by_date_sequence' if rgb else 'missing_or_ambiguous_RGB',
                        temperature_note='기존 ΔT는 최고−평균 온도이며 주변 모듈 대비 온도차가 아닙니다.')
            case['rgb_alignment']=rgb_registration(rgb,ortho) if auto and rgb else {'status':'needs_landmarks','reason':'수동 대응점 필요'}
            print(r['module_uid'],case['pairing_status'],case['rgb_alignment']['status'],flush=True)
            for p in [thermal,rgb,raw if raw.is_file() else None,ortho,crop]:
                if p and p.is_file():asset_hashes[str(p.resolve())]=digest(p)
            # Nearby captures are context only; no assertion that they show the same module.
            seq=int(r['image_id'].split('_')[-2]); day=r['image_id'].split('_')[1][:8]
            neighbors=[]
            for p in sorted((root/'image').glob('*_T.JPG')):
                parts=p.stem.split('_')
                if parts[1][:8]==day and 0<abs(int(parts[-2])-seq)<=2:
                    pair=lookup.get(parse_tv_and_key5(str(p))[2],[])
                    neighbors.append({'thermal':str(p),'rgb':str(pair[0]) if len(pair)==1 else None,'status':'context_only_unverified'})
            case['neighbor_captures']=neighbors; cases.append(case)
    rows=read_json(root/'results/drawing_site/site_layout.json')['rows']
    modules=[m for r in rows for m in raised_modules(r)]
    manifest={'schema_version':1,'dataset_id':dataset,'zone':'A','source_hashes':source_hashes,
              'asset_hashes':asset_hashes,'registration':review['registration'],'cases':cases,
              'modules':[{'id':m['id'],'polygon':m['vertices'][:4]} for m in modules]}
    atomic_json(output/'manifest.json',manifest)
    return manifest


class ReviewSession:
    def __init__(self, output=OUT, root=ROOT, verify=True):
        self.output=Path(output); self.root=Path(root)
        self.manifest=read_json(self.output/'manifest.json')
        if verify:
            for name, value in self.manifest['source_hashes'].items():
                if digest(self.root/name)!=value: raise ValueError('기준 자료가 변경되어 기존 확인 결과를 적용할 수 없습니다.')
            for name, value in self.manifest['asset_hashes'].items():
                if not Path(name).is_file() or digest(name)!=value: raise ValueError(f'검토 영상이 변경되거나 없습니다: {name}')
        self.cases={c['key']:c for c in self.manifest['cases']}
        self.modules={m['id']:m for m in self.manifest['modules']}
        self.module_list=list(self.modules.values())
        self.centers=np.array([np.mean(m['polygon'],axis=0)[:2] for m in self.module_list])
        self.tree=cKDTree(self.centers)
        self.state_path=self.output/'review_state.json'
        self.state=read_json(self.state_path) if self.state_path.exists() else {
            'schema_version':1,'dataset_id':self.manifest['dataset_id'],'revision':0,'cases':{},'audit':[]}
        if self.state['dataset_id']!=self.manifest['dataset_id']:raise ValueError('검토 상태의 데이터셋이 다릅니다.')

    def evidence(self,key):
        return copy.deepcopy(self.state['cases'].get(key,{'status':'pending','thermal_rgb_pairs':[],
            'rgb_ortho_pairs':[],'rgb_alignment':self.cases[key]['rgb_alignment'],'note':'','thermal_polygon':[]}))

    def propose(self,key,evidence):
        case=self.cases[key]
        if not case['rgb']:raise ValueError('같은 촬영의 RGB 영상이 필요합니다.')
        tr=fit_landmarks(evidence.get('thermal_rgb_pairs',[]), max_error=12)
        ro=fit_landmarks(evidence['rgb_ortho_pairs'],max_error=7.5) if evidence.get('rgb_ortho_pairs') else evidence.get('rgb_alignment')
        if not ro or 'matrix' not in ro:raise ValueError('RGB와 정사영상의 대응점을 먼저 설정해 주세요.')
        x1,y1,x2,y2=case['bbox']
        region=evidence.get('thermal_polygon') or [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        width,height=case['thermal_size']
        if any(not (0<=p[0]<width and 0<=p[1]<height) for p in region):
            raise ValueError('모듈 영역이 열화상 범위를 벗어났습니다.')
        poly=Polygon(region)
        if len(region)!=4 or not poly.is_valid or poly.area<16:raise ValueError('열화상 모듈의 네 모서리를 순서대로 선택해 주세요.')
        if not poly.covers(Point((x1+x2)/2,(y1+y2)/2)):
            raise ValueError('선택한 모듈 영역에 원래 검출 중심이 없습니다. 다른 모듈을 선택하지 않았는지 확인해 주세요.')
        if not inside_hull(region,tr['support']):raise ValueError('열화상 모듈 주변을 둘러싸도록 대응점을 추가해 주세요.')
        rgb=project(region,tr['matrix'])
        if not inside_hull(rgb,ro['support']):raise ValueError('RGB 모듈이 정합 지지 영역 밖입니다. 주변 대응점을 추가해 주세요.')
        local=project(project(rgb,ro['matrix']),case['tile_to_local'])
        matrix=np.asarray(self.manifest['registration']['matrix_3x2'])
        drawing=np.c_[local,np.ones(len(local))]@matrix
        center=drawing.mean(axis=0); distances,indices=self.tree.query(center,k=2)
        module=self.module_list[int(indices[0])]
        if distances[0]>.6 or distances[1]-distances[0]<.15:
            raise ValueError(f'모듈 대응이 불확실합니다 (최근접 {distances[0]:.2f}m). 정합 또는 모듈 모서리를 확인해 주세요.')
        footprint=Polygon(drawing); target=Polygon(np.array(module['polygon'])[:,:2])
        if not footprint.is_valid or footprint.area<=0:raise ValueError('투영된 모듈 영역이 유효하지 않습니다.')
        overlap=footprint.intersection(target).area / max(footprint.area,1e-9)
        if overlap<.5:raise ValueError('투영 영역과 모듈의 겹침이 부족합니다.')
        # Recheck A boundaries after visual projection; source GPS alone cannot authorize a moved point.
        from affine import Affine
        from pyproj import Transformer
        meta=self.manifest['registration']['orthomosaic']; transform=Affine(*meta['transform'][:6])
        to_geo=Transformer.from_crs(meta['crs'],'EPSG:4326',always_xy=True)
        point=local.mean(axis=0); lon,lat=to_geo.transform(*(transform*(point[0]/transform.a,point[1]/-transform.e)))
        zones=read_json(self.root/'model/zones shinan2 .geojson')['features']
        hits=[f['properties']['zone_id'] for f in zones if shape(f['geometry']).covers(Point(lon,lat))]
        if len(hits)!=1 or not hits[0].startswith('A'):raise ValueError('시각 정합 위치가 단일 A구역 안에 있지 않습니다.')
        temperature=None
        if evidence.get('thermal_polygon') and case.get('raw'):
            raw=_load_raw_float32_auto(case['raw']); width,height=case['thermal_size']
            mask=np.zeros((height,width),dtype=np.uint8);cv2.fillPoly(mask,[np.rint(region).astype(np.int32)],1)
            temperature=measure_module_raw(raw,mask)
        return {'module_id':module['id'],'position':[float(center[0]),float(center[1]),3.],
                'projected_polygon':drawing.tolist(),'distance_m':float(distances[0]),'overlap_fraction':float(overlap),
                'thermal_rgb':tr,'rgb_ortho':ro,'temperature':temperature,
                'status':'visual_candidate_requires_review','gps_position':case['position']}

    def save(self,key,evidence,status='pending',reviewer='',note=''):
        if key not in self.cases:raise ValueError('알 수 없는 검토 항목')
        if status not in ('pending','confirmed','rejected'):raise ValueError('잘못된 검토 상태')
        evidence=copy.deepcopy(evidence)
        if status=='confirmed':
            if not reviewer.strip() or not note.strip():raise ValueError('검토자와 연결 확인 근거를 입력해 주세요.')
            if not evidence.get('thermal_polygon'):raise ValueError('확인 전에 열화상 모듈의 네 모서리를 지정해 주세요.')
            evidence['proposal']=self.propose(key,evidence)
        else:
            evidence.pop('proposal',None)
        lock=self.output/'review_state.lock'
        try: fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise ValueError('다른 창에서 저장 중입니다. 잠시 후 다시 시도하세요.')
        os.close(fd)
        try:
            current=read_json(self.state_path) if self.state_path.exists() else self.state
            if current['revision']!=self.state['revision']:raise ValueError('다른 창에서 변경했습니다. 창을 다시 열어 주세요.')
            updated=copy.deepcopy(self.state);updated['revision']+=1
            evidence.update(status=status,reviewer=reviewer.strip(),note=note.strip(),updated_at=datetime.now(timezone.utc).isoformat())
            updated['cases'][key]=evidence
            updated['audit'].append({'revision':updated['revision'],'case':key,'decision':copy.deepcopy(evidence)})
            atomic_json(self.state_path,updated);self.state=updated
        finally:lock.unlink()
        return evidence

    def export(self):
        # Revalidate sources before applying decisions to a fresh Blender payload.
        verified=ReviewSession(self.output,self.root,verify=True)
        review=read_json(self.root/'results/blender_site/thermal_review_registered_a.json')
        marks={}; history=[]
        for i,record in enumerate(review['records']):
            record['review_status']='pending'
            evidence=verified.state['cases'].get(record['module_uid'])
            if not evidence:continue
            record['review_status']=evidence['status']
            if evidence['status']!='confirmed':continue
            proposal=verified.propose(record['module_uid'],evidence)
            record['gps_registered_position']=record['position'];record['position']=proposal['position']
            record['confirmed_module_id']=proposal['module_id'];record['reviewer']=evidence['reviewer']
            record['review_note']=evidence['note'];record['review_temperature']=proposal['temperature']
            module=verified.modules[proposal['module_id']]
            item=marks.setdefault(module['id'],{'id':module['id'],'polygon':[[x,y,z+.03] for x,y,z in module['polygon']],
                       'records':[],'severity':record['final'],'review_status':'confirmed'})
            item['records'].append(i)
            history.append({'module_id':module['id'],'dataset_id':self.manifest['dataset_id'],'record':record['module_uid'],
                            'image_id':record['image_id'],'reviewer':evidence['reviewer'],'reviewed_at':evidence['updated_at']})
        # Existing guesses become orange outlines. Only reviewed links receive a red surface.
        confirmed_indices={i for item in marks.values() for i in item['records']}
        guesses=[]
        for old in review['highlight_modules']:
            pending=[i for i in old['records'] if i not in confirmed_indices and review['records'][i]['review_status']!='rejected']
            if pending:
                guesses.append({**old,'records':pending,'review_status':'pending'})
        review['highlight_modules']=guesses+list(marks.values())
        review['review_dataset_id']=self.manifest['dataset_id'];review['review_revision']=verified.state['revision']
        review['module_history']=history
        review['notes'].append('Red panel surfaces require an explicit visual association review. Orange = pending; rejection rejects the link, not the thermal anomaly.')
        path=self.root/'results/blender_site/thermal_review_verified_a.json';atomic_json(path,review)
        atomic_json(self.output/'module_history.json',{'dataset_id':self.manifest['dataset_id'],'records':history})
        return path

"""Export geolocated observations as conservative Shinan3 drawing-ID candidates.

Never assigns a field-confirmed identity. Calibration points must reference
the drawing's local x/n metre coordinates, not the solar preview origin.
"""
import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def export_results(master, layout, output, calibration=None, source_base=None):
    master, layout, output = map(Path, (master, layout, output))
    if output.exists() and any(output.iterdir()):
        raise ValueError('새 폴더 또는 빈 결과 폴더를 지정하세요.')
    data = json.loads(layout.read_text(encoding='utf-8-sig'))
    modules = []
    for g in data['groups']:
        if not g['id'].startswith('S3-G'):
            raise ValueError('신안3호기 배치만 지원합니다.')
        for row in range(2):
            for col in range(10):
                modules.append((f"{g['id']}-R{row+1}-M{col+1:02}",
                                g['bounds'][0]+col*1.008+.4915,
                                g['bounds'][1]+row*1.425+.7125))
    xy = np.array([m[1:] for m in modules])
    tree = cKDTree(xy)
    transform = None
    registration = {'status': 'missing_control_points'}
    if calibration:
        c = json.loads(Path(calibration).read_text(encoding='utf-8-sig'))
        if c.get('site_id') != 'shinan3' or c.get('layout_sha256') != digest(layout):
            raise ValueError('발전소 또는 도면 지문이 기준점 자료와 다릅니다.')
        points = c['control_points']
        if len(points) < 4:
            raise ValueError('분산 배치된 기준점이 4개 이상 필요합니다.')
        ll = np.array([[p['lat'], p['lon']] for p in points], dtype=float)
        target = np.array([[p['x'], p['n']] for p in points], dtype=float)
        if not np.isfinite(ll).all() or not np.isfinite(target).all() or np.any(np.abs(ll[:,0]) >= 90) or np.any(np.abs(ll[:,1]) > 180):
            raise ValueError('기준점 좌표가 유효하지 않습니다.')
        origin = ll.mean(axis=0)
        scale = np.array([111320., 111320.*math.cos(math.radians(origin[0]))])
        def design(latlon):
            en = (np.asarray(latlon)-origin)*scale
            return np.column_stack((en[:,1], en[:,0], np.ones(len(en))))
        a = design(ll)
        if np.linalg.matrix_rank(a) < 3 or np.linalg.cond(a) > 1e6:
            raise ValueError('기준점이 일직선이거나 정합 조건이 불안정합니다.')
        transform = np.linalg.lstsq(a, target, rcond=None)[0]
        residual = float(np.max(np.linalg.norm(a@transform-target, axis=1)))
        uncertainty = number(c.get('position_uncertainty_m'))
        if uncertainty is None or uncertainty <= 0 or residual > 1:
            raise ValueError('양수 위치 오차 범위가 필요하며 기준점 최대 잔차는 1m 이하여야 합니다.')
        registration = {'status': 'control_point_affine_approximation', 'max_residual_m': residual,
                        'position_uncertainty_m': uncertainty, 'calibration_sha256': digest(calibration),
                        'note': '기준점 적합 잔차는 현장 정확도 또는 독립 검증값이 아닙니다.'}
        # Outside the control-point hull is not a supported registration region.
        from scipy.spatial import Delaunay
        hull = Delaunay(a[:,:2])
    output.mkdir(parents=True, exist_ok=True)
    base = Path(source_base) if source_base else master.parent
    copied = {}
    def asset(raw):
        if not raw:
            return None
        p = Path(raw)
        if not p.is_absolute():
            p = base / p
        if not p.is_file() or p.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            return None
        key = str(p.resolve())
        if key not in copied:
            rel = 'images/' + digest(p) + p.suffix.lower()
            (output/'images').mkdir(exist_ok=True)
            shutil.copy2(p, output/rel)
            copied[key] = rel
        return copied[key]
    records, seen = [], set()
    dataset = digest(master)
    with master.open(encoding='utf-8-sig', newline='') as stream:
        for r in csv.DictReader(stream):
            identity = (r.get('image_id'), r.get('module_id'))
            if identity in seen:
                raise ValueError('중복 관측 ID: '+str(identity))
            seen.add(identity)
            oid = 'OBS-' + hashlib.sha256((dataset+json.dumps(identity)).encode()).hexdigest()[:24]
            rec = {'observation_id': oid, 'image_id': identity[0], 'detected_module_id': identity[1],
                   'drawing_module_id': None, 'link_status': 'unmatched', 'candidates': [],
                   'decision': r.get('final') or 'unknown',
                   'temperature': {k: number(r.get(k)) for k in ('max_temp','mean_temp','delta_temp')},
                   'geo_status': r.get('geo_status'), 'position_source': r.get('position_source'),
                   'projection_evidence': {k:r.get(k) for k in ('img_w','img_h','centroid_u','centroid_v','camera_to_surface_m','height_source','gimbal_yaw','gimbal_pitch','gimbal_roll','footprint_w_m','footprint_h_m')},
                   'temperature_status': r.get('thermal_status') or r.get('temperature_status'),
                   'images': {'thermal':asset(r.get('det_base')), 'rgb':asset(r.get('rgb_path')),
                              'crop':asset(r.get('crop_path')) or asset(r.get('dst_path'))},
                   'reason': 'missing_control_points'}
            lat, lon = number(r.get('mod_lat')), number(r.get('mod_lon'))
            rec['estimated_latlon'] = [lat, lon]
            if lat is None or lon is None or abs(lat)>=90 or abs(lon)>180:
                rec['reason'] = 'missing_or_invalid_projected_module_position'
            elif r.get('geo_status') != 'approximate_flat_plane':
                rec['reason'] = 'unverified_projection_method'
            elif transform is not None:
                projected = design([[lat,lon]])
                if hull.find_simplex(projected[:,:2])[0] < 0:
                    rec['reason'] = 'outside_control_point_coverage'
                else:
                    local = (projected@transform)[0]
                    rec['estimated_local_xn'] = local.tolist()
                    radius = uncertainty + residual
                    candidates = tree.query_ball_point(local, radius)
                    ordered = sorted(candidates, key=lambda i: float(np.linalg.norm(xy[i]-local)))
                    rec['candidate_count'] = len(ordered)
                    rec['candidates'] = [{'id':modules[i][0], 'distance_m':float(np.linalg.norm(xy[i]-local))} for i in ordered[:8]]
                    if len(ordered) == 1:
                        rec.update(drawing_module_id=modules[ordered[0]][0], link_status='candidate', reason='single_candidate_within_declared_uncertainty')
                    else:
                        rec['reason'] = 'ambiguous_nearby_modules' if ordered else 'no_module_within_uncertainty'
            records.append(rec)
    # Two detections from one image cannot silently become the same physical ID.
    counts = Counter((r['image_id'],r['drawing_module_id']) for r in records if r['drawing_module_id'])
    for r in records:
        if r['drawing_module_id'] and counts[(r['image_id'],r['drawing_module_id'])] > 1:
            r.update(drawing_module_id=None, link_status='unmatched', reason='same_image_assignment_collision')
    result = {'schema':'pv-inspector-threejs-v1','site_id':'shinan3','layout_source_sha256':data['source_sha256'],
              'layout_sha256':digest(layout), 'dataset_id':dataset, 'registration':registration,
              'records':records,'counts':dict(Counter(r['link_status'] for r in records)),
              'limitations':['자동 확정 없음','RGB는 촬영 쌍 비교용이며 픽셀 정합은 별도 필요',
                              '평면 투영·GPS 오차 및 기준점 범위를 현장에서 확인해야 합니다.']}
    (output/'inspection_results.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True);p.add_argument('--layout',default='shinan3_viewer/assets/layout.json')
    p.add_argument('--output',required=True);p.add_argument('--calibration');p.add_argument('--source-base')
    a=p.parse_args()
    result=export_results(a.master,a.layout,a.output,a.calibration,a.source_base)
    print(json.dumps(result['counts'],ensure_ascii=False))


if __name__=='__main__':
    main()

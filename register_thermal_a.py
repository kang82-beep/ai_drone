"""Fit/reuse an A-only RGB-to-drawing registration; never calibrate thermal GPS by snapping."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from affine import Affine
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import shape
from sklearn.cluster import DBSCAN

from prepare_blender_thermal import validation_zone
from pv_inspector.site_model import strip_modules
from pv_inspector.site_structures import raised_modules

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/blender_site'
CALIBRATION = OUT / 'a_registration.json'
INPUTS = ['results/module_split_site/modules.json', 'results/drawing_site/site_layout.json',
          'model/zones shinan2 .geojson']


def transform_points(points, matrix):
    points = np.asarray(points, dtype=float)
    return np.c_[points, np.ones(len(points))] @ np.asarray(matrix)


def fingerprints():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUTS}


def check_sources(calibration, review):
    if calibration['fingerprints'] != fingerprints() or calibration['orthomosaic'] != review['orthomosaic']:
        raise ValueError('Registration sources changed. Inspect correspondences and run --refit before reuse.')


def summary(errors):
    return {'count': len(errors), 'median_m': float(np.median(errors)),
            'p95_m': float(np.percentile(errors, 95)), 'max_m': float(np.max(errors))}


def fit(catalog, rows, review):
    # Windows and strip ordering reviewed against this site's RGB and PDF layout.
    # Coordinates are normalized to a 6000-pixel-wide overview; not a generic auto-registration.
    pixels = np.array([m['center'] for m in catalog['modules']]) * 6000 / catalog['width']
    geo = Affine(*review['orthomosaic']['transform'][:6])
    to_geo = Transformer.from_crs(review['orthomosaic']['crs'], 'EPSG:4326', always_xy=True)
    zones = [(f['properties']['zone_id'], shape(f['geometry'])) for f in
             json.loads((ROOT / INPUTS[2]).read_text(encoding='utf-8'))['features']]
    source, target, ids, module_ids = [], [], [], []
    for lane, xlo, xhi, ylo, yhi in [(1, 370, 1710, 1130, 1800), (2, 1710, 3080, 750, 1810)]:
        selected = pixels[(pixels[:, 0] > xlo) & (pixels[:, 0] < xhi) &
                          (pixels[:, 1] > ylo) & (pixels[:, 1] < yhi)]
        labels = DBSCAN(eps=28, min_samples=4).fit_predict(selected[:, 1, None])
        groups = sorted([selected[labels == i] for i in set(labels) if i >= 0], key=lambda a: a[:, 1].mean())
        strips = [r for r in rows if r['lane'] == lane and r['y'] < 100]
        if len(groups) != len(strips):
            raise ValueError('Observed strip count changed; review correspondence windows.')
        for points, strip in zip(groups, strips):
            columns = np.rint((points[:, 0] - points[:, 0].min()) / 16.0).astype(int)
            detrended = points[:, 1] - .013 * points[:, 0]
            threshold = (detrended.min() + detrended.max()) / 2
            for _ in range(8):
                threshold = (detrended[detrended < threshold].mean() + detrended[detrended >= threshold].mean()) / 2
            south = (detrended > threshold).astype(int)
            modules = strip_modules(strip)
            seen = set()
            for point, column, low in zip(points, columns, south):
                if column >= strip['columns']:
                    raise ValueError('Column correspondence outside drawing strip')
                module = modules[(1 - low) * strip['columns'] + column]
                px = point * catalog['width'] / 6000
                if not validation_zone(*to_geo.transform(*(geo * tuple(px))), zones):
                    continue
                if module['id'] in seen:
                    raise ValueError('Ambiguous repeated module correspondence')
                seen.add(module['id'])
                source.append(px * [geo.a, -geo.e])
                target.append(np.mean(module['vertices'][:4], axis=0)[:2])
                ids.append(strip['id']); module_ids.append(module['id'])
    source, target, ids = np.array(source), np.array(target), np.array(ids)
    holdout = np.isin(ids, sorted(set(ids))[1::3])
    design = np.c_[source, np.ones(len(source))]
    matrix = np.linalg.lstsq(design[~holdout], target[~holdout], rcond=None)[0]
    errors = np.linalg.norm(design @ matrix - target, axis=1)
    if np.percentile(errors[holdout], 95) > .8:
        raise ValueError('Holdout residual exceeds 0.8m; registration not exported')
    calibration = {'schema_version': 1, 'zone': 'A', 'status': 'provisional_visual_registration',
                   'matrix_3x2': matrix.tolist(), 'source_frame': 'orthomosaic local metres, X east / Y south; no +400 offset',
                   'target_frame': 'drawing Blender XY metres', 'fingerprints': fingerprints(),
                   'orthomosaic': review['orthomosaic'], 'training': summary(errors[~holdout]),
                   'holdout': summary(errors[holdout]), 'training_strips': sorted(set(ids[~holdout])),
                   'holdout_strips': sorted(set(ids[holdout])),
                   'limitations': ['Correspondences inferred from reviewed strip order and module grid, not surveyed control points.',
                                   'Holdout measures RGB/drawing consistency, not thermal GPS accuracy.',
                                   'No E-zone calibration or validation. No per-flight GPS correction.']}
    CALIBRATION.write_text(json.dumps(calibration, indent=2), encoding='utf-8')
    with (OUT / 'a_registration_pairs.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f); writer.writerow(['strip', 'drawing_module', 'source_x', 'source_y', 'target_x', 'target_y', 'holdout', 'residual_m'])
        for i in range(len(source)):
            writer.writerow([ids[i], module_ids[i], *source[i], *target[i], bool(holdout[i]), errors[i]])
    return calibration


def project(review, calibration, rows):
    matrix = calibration['matrix_3x2']
    offset = review['orthomosaic']['offset_x']
    modules = [m for r in rows for m in raised_modules(r)]
    centers = np.array([np.mean(m['vertices'][:4], axis=0) for m in modules])
    tree = cKDTree(centers[:, :2])
    highlighted = {}
    for candidate in review['highlight_modules']:
        rgb_center = np.mean(candidate['polygon'], axis=0)[:2] - [offset, 0]
        xy = transform_points([rgb_center], matrix)[0]
        distances, indices = tree.query(xy, k=2)
        if distances[0] > .6 or distances[1] - distances[0] < .15:
            continue
        module = modules[indices[0]]
        item = highlighted.setdefault(module['id'], {'id': module['id'], 'records': [],
                    'polygon': [[x, y, z + .025] for x, y, z in module['vertices'][:4]],
                    'severity': 'attention', 'source_candidate_ids': []})
        item['records'].extend(candidate['records']); item['source_candidate_ids'].append(candidate['id'])
        if candidate['severity'] == 'abnormal': item['severity'] = 'abnormal'
        for index in candidate['records']:
            review['records'][index]['drawing_candidate_id'] = module['id']
            review['records'][index]['rgb_to_drawing_distance_m'] = float(distances[0])
    for record in review['records']:
        record['orthomosaic_position'] = record['position']
        if record['position']:
            xy = transform_points([np.array(record['position'][:2]) - [offset, 0]], matrix)[0]
            # Preserve unsnapped GPS XY. Elevated markers do not imply a confirmed module.
            record['position'] = [*xy.tolist(), 3.0]
    review['highlight_modules'] = list(highlighted.values())
    review['registration'] = calibration
    review['notes'] = ['A-only provisional RGB-to-drawing registration. Thermal GPS XY remains unsnapped.',
                      'Highlighted drawing modules are gated RGB candidates, not confirmed thermal module IDs.',
                      'Per-flight thermal GPS offset is not calibrated. Unhighlighted modules are unassessed.']
    (OUT / 'thermal_review_registered_a.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
    return review


def plot_review(calibration, rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from PIL import Image
    matrix = np.asarray(calibration['matrix_3x2'])
    inverse = np.linalg.inv(matrix[:2])
    im = Image.open(OUT / 'thermal_orthomosaic.jpg')
    w, h = calibration['orthomosaic']['size_m']
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.imshow(im, extent=(0, w, h, 0))
    lines = []
    for r in rows:
        if r['id'] not in calibration['training_strips'] + calibration['holdout_strips']: continue
        for m in strip_modules(r):
            polygon = np.asarray(m['vertices'][:4])[:, :2]
            points = (polygon - matrix[2]) @ inverse
            lines.append(np.vstack([points, points[0]]))
    ax.add_collection(LineCollection(lines, colors='#00ffb0', linewidths=.35))
    ax.set_xlim(18, 201); ax.set_ylim(124, 44)
    ax.set_title('A zone: drawing module outlines over RGB | provisional affine registration\n'
                 f"Held-out strips: median {calibration['holdout']['median_m']:.2f} m; P95 {calibration['holdout']['p95_m']:.2f} m (not thermal GPS error)")
    ax.set_xlabel('Orthomosaic local X (m)'); ax.set_ylabel('Orthomosaic local Y (m)')
    fig.tight_layout(); fig.savefig(OUT / 'a_registration_overlay.png', dpi=160); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--refit', action='store_true'); args = parser.parse_args()
    review = json.loads((OUT / 'thermal_review.json').read_text(encoding='utf-8'))
    if review['validation_scope']['zone'] != 'A': raise ValueError('A-only review required')
    catalog = json.loads((ROOT / INPUTS[0]).read_text(encoding='utf-8'))
    rows = json.loads((ROOT / INPUTS[1]).read_text(encoding='utf-8'))['rows']
    calibration = fit(catalog, rows, review) if args.refit or not CALIBRATION.exists() else json.loads(CALIBRATION.read_text())
    check_sources(calibration, review)
    result = project(review, calibration, rows); plot_review(calibration, rows)
    print(json.dumps({'training': calibration['training'], 'holdout': calibration['holdout'],
                      'drawing_highlights': len(result['highlight_modules']),
                      'abnormal': [{k: r.get(k) for k in ['module_uid', 'drawing_candidate_id', 'position']} for r in result['records'] if r['final'] == 'abnormal']}, indent=2))


if __name__ == '__main__': main()

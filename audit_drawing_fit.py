"""Find where the site differs from the drawing, after registration.

Three kinds of evidence, each repeated over several frames before it is listed:
- a drawing group (one table of 2 x 10 modules) whose observations sit consistently
  off its drawn position: the table is built somewhere else than drawn;
- detected modules with no drawing module near them: modules that are not drawn;
- drawing modules inside a registered frame that no frame ever detected: modules that
  are drawn but missing, or that the detector keeps missing (dirt, shade, damage).
These are candidates for a drawing or field check, not corrections.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import Delaunay, cKDTree

from pv_inspector.site_registration import load_site

GROUP_OFFSET_M = 0.15
MIN_FRAMES = 2


def group_offsets(linked, site):
    pos = site.set_index('drawing_module_id').loc[linked.drawing_module_id, ['x', 'n']].to_numpy()
    work = linked.assign(rx=linked.drawing_x.to_numpy() - pos[:, 0], rn=linked.drawing_n.to_numpy() - pos[:, 1],
                         group=linked.drawing_module_id.str.rsplit('-', n=2).str[0])
    table = work.groupby('group').agg(observations=('rx', 'size'), frames=('image_id', 'nunique'),
                                      offset_x_m=('rx', 'median'), offset_n_m=('rn', 'median'),
                                      string_id=('string_id', 'first'))
    table['offset_m'] = np.hypot(table.offset_x_m, table.offset_n_m)
    flagged = table[(table.frames >= MIN_FRAMES) & (table.offset_m > GROUP_OFFSET_M)]
    return table, flagged.sort_values('offset_m', ascending=False)


def undrawn_detections(work, registered, site):
    rows = work[work.image_id.isin(registered) & (work.link_reason == 'no_drawing_module_within_tolerance')].copy()
    rows['cell_x'] = np.round(rows.drawing_x / 1.008).astype(int)
    rows['cell_n'] = np.round(rows.drawing_n / 1.425).astype(int)
    cells = rows.groupby(['cell_x', 'cell_n']).agg(frames=('image_id', 'nunique'), x=('drawing_x', 'median'),
                                                   n=('drawing_n', 'median')).reset_index()
    cells['nearest_drawing_module_m'] = cKDTree(site[['x', 'n']].to_numpy()).query(cells[['x', 'n']].to_numpy())[0]
    return cells[cells.frames >= MIN_FRAMES].sort_values('frames', ascending=False)


def never_detected(work, registered, site):
    xy = site[['x', 'n']].to_numpy()
    tree = cKDTree(xy)
    covered = np.zeros(len(site), int)
    matched = set(work.drawing_module_id.dropna())
    for image, g in work[work.image_id.isin(registered)].groupby('image_id'):
        points = g[['drawing_x', 'drawing_n']].dropna().to_numpy()
        if len(points) < 8:
            continue
        try:
            hull = Delaunay(points)
        except Exception:
            continue
        near = tree.query_ball_point(points.mean(axis=0), np.ptp(points, axis=0).max())
        inside = [i for i in near if hull.find_simplex(xy[i]) >= 0]
        covered[inside] += 1
    out = site.assign(covered_frames=covered)
    out = out[(out.covered_frames >= MIN_FRAMES) & ~out.drawing_module_id.isin(matched)]
    return out.sort_values('covered_frames', ascending=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', default='results/shinan3_full_20261030/reg')
    parser.add_argument('--layout', default='shinan3_viewer/assets/layout.json')
    parser.add_argument('--cable-model', default='results/shinan3_cables/cable_model.json')
    parser.add_argument('--output', default='results/drawing_audit')
    args = parser.parse_args()
    reg, output = Path(args.registration), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    site = load_site(args.layout, args.cable_model if Path(args.cable_model).is_file() else None)
    work = pd.read_csv(reg / 'master_linked.csv', encoding='utf-8-sig', low_memory=False)
    frames = pd.read_csv(reg / 'frame_registration.csv', encoding='utf-8-sig')
    registered = set(frames.loc[frames.status == 'registered', 'image_id'])
    linked = work[work.link_status.astype(str).str.startswith('module_candidate') & work.drawing_x.notna()]

    groups, shifted = group_offsets(linked, site)
    undrawn = undrawn_detections(work, registered, site)
    missing = never_detected(work, registered, site)
    shifted.to_csv(output / 'groups_off_drawing.csv', encoding='utf-8-sig')
    undrawn.to_csv(output / 'detections_without_drawing_module.csv', index=False, encoding='utf-8-sig')
    missing.to_csv(output / 'drawing_modules_never_detected.csv', index=False, encoding='utf-8-sig')
    summary = dict(
        groups_observed=int(len(groups)), group_offset_median_m=round(float(groups.offset_m.median()), 3),
        groups_off_drawing=int(len(shifted)), groups_off_drawing_threshold_m=GROUP_OFFSET_M,
        detections_without_drawing_module=int(len(undrawn)),
        drawing_modules_never_detected=int(len(missing)),
        never_detected_by_group=missing.drawing_module_id.str.rsplit('-', n=2).str[0].value_counts().head(20).to_dict(),
        note='도면 확인·현장 확인 후보이며 확정이 아닙니다. 여러 영상에서 반복된 것만 넣었습니다.')
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

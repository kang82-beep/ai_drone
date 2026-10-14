"""Link projected observations to drawing modules, strings, junction boxes and inverters.

The drawing-to-GPS transform starts from a map alignment and is refined on the
array pattern seen by the drone itself. Row ends and roads decide between
positions that differ by a whole module or row pitch; that decision and its
margin are written to the report. Every link is a candidate: this is a
self-consistency fit, not a survey, and nothing here is field-confirmed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

MODULE_MATCH_M = 0.35    # under half of the 1.008 m module pitch
FRAME_SHIFT_MAX_M = 0.45
MIN_FRAME_MODULES = 8


def load_site(layout_path, cable_model_path=None):
    layout = json.loads(Path(layout_path).read_text(encoding='utf-8-sig'))
    ids, xy = [], []
    for g in layout['groups']:
        for row in range(2):
            for col in range(10):
                ids.append(f"{g['id']}-R{row + 1}-M{col + 1:02}")
                xy.append((g['bounds'][0] + col * 1.008 + .4915, g['bounds'][1] + row * 1.425 + .7125))
    site = pd.DataFrame({'drawing_module_id': ids, 'x': [p[0] for p in xy], 'n': [p[1] for p in xy]})
    site['string_id'] = site['jb_id'] = site['inverter_id'] = None
    if cable_model_path:
        cable = json.loads(Path(cable_model_path).read_text(encoding='utf-8-sig'))
        lookup = {m: (s['id'], s['jb'], s['inverter']) for s in cable['strings'] for m in s['modules']}
        found = [lookup.get(i, (None, None, None)) for i in ids]
        for k, name in enumerate(('string_id', 'jb_id', 'inverter_id')):
            site[name] = [f[k] for f in found]
    return site


def _similarity(source, target):
    """Least-squares a,b,tx,ty with target = [[a,-b],[b,a]] source + t."""
    design = np.zeros((2 * len(source), 4))
    design[0::2] = np.column_stack((source[:, 0], -source[:, 1], np.ones(len(source)), np.zeros(len(source))))
    design[1::2] = np.column_stack((source[:, 1], source[:, 0], np.zeros(len(source)), np.ones(len(source))))
    return np.linalg.lstsq(design, target.ravel(), rcond=None)[0]


def _apply(params, points):
    a, b, tx, ty = params
    return np.column_stack((a * points[:, 0] - b * points[:, 1] + tx, b * points[:, 0] + a * points[:, 1] + ty))


class GeoTransform:
    """Latitude/longitude to drawing x/north metres through a local tangent plane."""

    def __init__(self, reference):
        ll = np.array([[m['latitude'], m['longitude']] for m in reference], float)
        self.origin = ll.mean(axis=0)
        self.scale = np.array([110950.0, 111320.0 * math.cos(math.radians(self.origin[0]))])
        self.params = _similarity(self.local(ll), np.array([[m['x'], m['n']] for m in reference], float))
        self.centre = np.array([[m['x'], m['n']] for m in reference], float).mean(axis=0)
        self.shift = np.zeros(2)
        # Correction that grows linearly across the site: the map alignment carries a
        # small scale/rotation error that one shift cannot absorb over a whole flight.
        self.gradient = np.zeros((2, 2))

    def local(self, latlon):
        d = (np.asarray(latlon, float) - self.origin) * self.scale
        return np.column_stack((d[:, 1], d[:, 0]))

    def base(self, latlon):
        return _apply(self.params, self.local(latlon))

    def __call__(self, latlon):
        p = self.base(latlon)
        return p + self.shift + (p - self.centre) @ self.gradient.T


def fit_frame(points, tree, xy, max_shift=FRAME_SHIFT_MAX_M):
    """Scale/rotation/shift of one frame onto the drawing; None when unsupported.

    Height above the tilted modules and focal length are only nominal, so each
    frame gets its own scale. The shift is bounded so a frame cannot slide onto
    the neighbouring module.
    """
    if len(points) < MIN_FRAME_MODULES:
        return None
    centre = points.mean(axis=0)
    local = points - centre
    moved, params = points.copy(), np.array([1.0, 0.0, 0.0, 0.0])
    for radius in (0.7, 0.55, 0.45, 0.4, 0.4):
        dist, idx = tree.query(moved)
        keep = dist <= radius
        if keep.sum() < MIN_FRAME_MODULES:
            return None
        params = _similarity(local[keep], xy[idx[keep]] - centre)
        scale, rotation = math.hypot(params[0], params[1]), math.degrees(math.atan2(params[1], params[0]))
        if abs(scale - 1) > 0.12 or abs(rotation) > 4 or math.hypot(params[2], params[3]) > max_shift:
            return None
        moved = _apply(params, local) + centre
    dist, idx = tree.query(moved)
    return dict(points=moved, index=idx, distance=dist, scale=scale, rotation_deg=rotation,
                shift=(float(params[2]), float(params[3])))


def refine_correction(transform, frames, tree, xy, rounds=8):
    """Fit shift + linear gradient to the shifts of well-supported frames.

    Frames far from where the map alignment is good start outside the shift bound,
    so the correction is grown over several rounds from the frames that already fit.
    """
    for _ in range(rounds):
        centres, shifts = [], []
        for latlon in frames:
            fit = fit_frame(transform(latlon), tree, xy)
            if fit and (fit['distance'] <= MODULE_MATCH_M).mean() >= 0.6:
                centres.append(transform.base(latlon).mean(axis=0) - transform.centre)
                shifts.append(fit['shift'])
        if not shifts:
            return
        centres, shifts = np.array(centres), np.array(shifts)
        spread = np.ptp(centres, axis=0) if len(centres) > 1 else np.zeros(2)
        if len(shifts) < 20 or spread.min() < 30:
            transform.shift += np.median(shifts, axis=0)
            continue
        design = np.column_stack((centres, np.ones(len(centres))))
        keep = np.ones(len(shifts), bool)
        for _ in range(2):  # drop frames that snapped onto a neighbouring row
            coef = np.linalg.lstsq(design[keep], shifts[keep], rcond=None)[0]
            residual = np.hypot(*(design @ coef - shifts).T)
            keep = residual <= max(0.15, 2.5 * np.median(residual[keep]))
        transform.gradient += coef[:2].T
        transform.shift += coef[2]


def _score(frames, transform, tree, xy, offset=(0.0, 0.0)):
    inliers = total = 0
    for latlon in frames:
        total += len(latlon)
        fit = fit_frame(transform(latlon) + offset, tree, xy)
        if fit:
            inliers += int((fit['distance'] <= MODULE_MATCH_M).sum())
    return inliers / total if total else 0.0


def register(master, site, reference, pitch=(1.008, 5.82)):
    """Return annotated observations and a report. `pitch` is the module pitch and paired-row period."""
    xy = site[['x', 'n']].to_numpy(float)
    tree = cKDTree(xy)
    transform = GeoTransform(reference)
    work = master.reset_index(drop=True).copy()
    usable = work['mod_lat'].notna() & work['mod_lon'].notna()
    groups = {k: g.index.to_numpy() for k, g in work[usable].groupby('image_id', sort=True)}
    frames = [work.loc[i, ['mod_lat', 'mod_lon']].to_numpy(float) for i in groups.values()]
    # Centre on the nearest self-consistent position, then test whole-pitch alternatives.
    refine_correction(transform, frames, tree, xy)
    hypotheses = []
    for kx in range(-3, 4):
        for kn in (-1, 0, 1):
            offset = (kx * pitch[0], kn * pitch[1])
            hypotheses.append(dict(module_pitches_east=kx, row_periods_north=kn,
                                   inlier_fraction=_score(frames, transform, tree, xy, offset)))
    # Ties keep the map alignment: without row ends in view a whole-pitch move is not evidence.
    hypotheses.sort(key=lambda h: (-round(h['inlier_fraction'], 4), h['module_pitches_east'] ** 2 + h['row_periods_north'] ** 2))
    best = hypotheses[0]
    margin = best['inlier_fraction'] - hypotheses[1]['inlier_fraction']
    total = sum(len(f) for f in frames)
    resolved = margin >= 0.003 and margin * total >= 15
    if resolved:
        transform.shift += (best['module_pitches_east'] * pitch[0], best['row_periods_north'] * pitch[1])
    candidate = 'module_candidate' if resolved else 'module_candidate_pitch_unresolved'

    for name in ('drawing_module_id', 'string_id', 'jb_id', 'inverter_id', 'link_reason'):
        work[name] = None
    work['link_status'] = 'unmatched'
    work['link_distance_m'] = np.nan
    work.loc[~usable, 'link_reason'] = 'no_projected_position'
    frame_rows = []
    for (image, index), latlon in zip(groups.items(), frames):
        fit = fit_frame(transform(latlon), tree, xy)
        if not fit:
            work.loc[index, 'link_reason'] = 'frame_not_registered'
            frame_rows.append(dict(image_id=image, observations=len(index), status='not_registered'))
            continue
        near = fit['distance'] <= MODULE_MATCH_M
        # Two detections in one frame cannot be the same module: the closer keeps it.
        order = np.argsort(fit['distance'])
        taken, unique = set(), np.zeros(len(index), bool)
        for i in order:
            if near[i] and fit['index'][i] not in taken:
                taken.add(fit['index'][i]); unique[i] = True
        status = 'registered' if unique.mean() >= 0.6 else 'low_support'
        frame_rows.append(dict(image_id=image, observations=len(index), status=status,
                               matched=int(unique.sum()), scale=fit['scale'], rotation_deg=fit['rotation_deg'],
                               shift_east_m=fit['shift'][0], shift_north_m=fit['shift'][1],
                               median_distance_m=float(np.median(fit['distance'][unique])) if unique.any() else None))
        work.loc[index, 'link_distance_m'] = fit['distance']
        if status != 'registered':
            work.loc[index, 'link_reason'] = 'frame_low_support'
            continue
        matched = site.iloc[fit['index']].reset_index(drop=True)
        for i, row in enumerate(index):
            if unique[i]:
                for name in ('drawing_module_id', 'string_id', 'jb_id', 'inverter_id'):
                    work.at[row, name] = matched.at[i, name]
                work.at[row, 'link_status'] = candidate
                work.at[row, 'link_reason'] = 'within_module_tolerance_of_refined_drawing'
            else:
                work.at[row, 'link_reason'] = 'same_frame_collision' if near[i] else 'no_drawing_module_within_tolerance'
    frame_table = pd.DataFrame(frame_rows)
    linked = work[work.link_status == candidate]
    registered = frame_table[frame_table.status == 'registered'] if len(frame_table) else frame_table
    report = dict(
        status='self_consistent_candidate_registration_not_surveyed',
        observations=len(work), module_candidates=len(linked), link_status_used=candidate,
        frames=len(frame_table), frames_registered=len(registered),
        drawing_modules=len(site), drawing_modules_observed=int(linked.drawing_module_id.nunique()),
        strings_observed=int(linked.string_id.nunique()), strings_total=int(site.string_id.nunique()),
        global_shift_from_map_alignment_m=transform.shift.round(3).tolist(),
        correction_gradient_m_per_100m=(transform.gradient * 100).round(3).tolist(),
        whole_pitch_test=dict(resolved=bool(resolved), best=best, runner_up=hypotheses[1], margin=margin,
                              observations_deciding=int(round(margin * total)), alternatives=hypotheses[:6],
                              note='차이가 작으면 모듈 한 칸 어긋남을 배제할 수 없습니다.'),
        frame_shift_std_m=[float(registered.shift_east_m.std()), float(registered.shift_north_m.std())] if len(registered) > 1 else None,
        frame_scale_median=float(registered['scale'].median()) if len(registered) else None,
        limitations=['도면·지도 정합과 드론 투영을 서로 맞춘 결과이며 측량 기준점으로 검증하지 않았습니다.',
                     '도면과 현장 시공이 다른 구간은 잘못 연결될 수 있습니다.',
                     '모든 연결은 후보이며 현장 확인 전에는 확정 ID가 아닙니다.'])
    return work, frame_table, report


def visual_link_agreement(work, links):
    """Independent check: thermal image registration pairs should land on one drawing module."""
    if links is None or links.empty:
        return None
    ids = work['drawing_module_id']
    pairs = links[links['accepted'].astype(str).str.lower() == 'true']
    both = [(ids.get(a), ids.get(b)) for a, b in zip(pairs.source_index, pairs.target_index)]
    both = [(a, b) for a, b in both if a and b]
    same = sum(a == b for a, b in both)
    return dict(pairs_with_both_linked=len(both), same_drawing_module=same,
                agreement=same / len(both) if both else None)


def summarise(work):
    """One row per drawing module and per string, worst finding first."""
    linked = work[work.link_status.astype(str).str.startswith('module_candidate')].copy()
    rank = {'abnormal': 0, 'attention': 1, 'normal': 2}
    linked['rank'] = linked['final'].map(rank).fillna(3)
    numeric = lambda name: pd.to_numeric(linked[name], errors='coerce') if name in linked else np.nan
    linked['delta_temp'], linked['neighbor_delta_mean'] = numeric('delta_temp'), numeric('neighbor_delta_mean')
    keys = ['inverter_id', 'jb_id', 'string_id', 'drawing_module_id']
    modules = linked.groupby(keys, dropna=False).agg(
        observations=('image_id', 'size'), worst_rank=('rank', 'min'),
        flagged_observations=('rank', lambda s: int((s < 2).sum())),
        max_delta_temp=('delta_temp', 'max'), max_neighbor_delta=('neighbor_delta_mean', 'max'),
        images=('image_id', lambda s: ';'.join(sorted(set(s))[:6]))).reset_index()
    names = {0: 'abnormal', 1: 'attention', 2: 'normal', 3: 'unknown'}
    modules['worst_final'] = modules.pop('worst_rank').map(names)
    # A finding seen in only one of several passes is weaker evidence than a repeated one.
    modules['repeatability'] = np.where(modules.observations > 1, modules.flagged_observations / modules.observations, np.nan)
    flagged = modules[modules.worst_final.isin(['abnormal', 'attention'])]
    strings = modules.groupby(['inverter_id', 'jb_id', 'string_id'], dropna=False).agg(
        modules_observed=('drawing_module_id', 'size'),
        modules_flagged=('worst_final', lambda s: int(s.isin(['abnormal', 'attention']).sum())),
        modules_abnormal=('worst_final', lambda s: int((s == 'abnormal').sum())),
        max_delta_temp=('max_delta_temp', 'max'), max_neighbor_delta=('max_neighbor_delta', 'max')).reset_index()
    flagged_ids = flagged.groupby('string_id').drawing_module_id.apply(lambda s: ';'.join(sorted(s)))
    strings['flagged_modules'] = strings.string_id.map(flagged_ids).fillna('')
    strings = strings.sort_values(['modules_abnormal', 'modules_flagged', 'max_delta_temp'], ascending=False)
    return modules, strings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master', required=True)
    p.add_argument('--layout', default='shinan3_viewer/assets/layout.json')
    p.add_argument('--cable-model', default='results/shinan3_cables/cable_model.json')
    p.add_argument('--reference', default='results/shinan3_map_alignment/module_geolocation_candidates.json',
                   help='지도 정합에서 만든 모듈 위경도 후보 (초기값)')
    p.add_argument('--links', help='association_links.csv (선택, 독립 일치 검사)')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    output = Path(a.output); output.mkdir(parents=True, exist_ok=True)
    site = load_site(a.layout, a.cable_model)
    reference = json.loads(Path(a.reference).read_text(encoding='utf-8-sig'))[::50]
    master = pd.read_csv(a.master, encoding='utf-8-sig', low_memory=False)
    work, frames, report = register(master, site, reference)
    if a.links:
        report['visual_link_agreement'] = visual_link_agreement(work, pd.read_csv(a.links, encoding='utf-8-sig'))
    modules, strings = summarise(work)
    work.to_csv(output / 'master_linked.csv', index=False, encoding='utf-8-sig')
    frames.to_csv(output / 'frame_registration.csv', index=False, encoding='utf-8-sig')
    modules.to_csv(output / 'module_summary.csv', index=False, encoding='utf-8-sig')
    strings.to_csv(output / 'string_summary.csv', index=False, encoding='utf-8-sig')
    (output / 'registration_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

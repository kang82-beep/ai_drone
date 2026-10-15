"""Link projected observations to drawing modules, strings, junction boxes and inverters.

The drawing-to-GPS transform starts from a map alignment and is refined on the
array pattern seen by the drone itself. Along a row the pattern repeats every
module, so frames are chained into flight lines and each line is placed by its
row ends and roads, or by the trend of the lines that see them; each decision and
its margin are written to the report. Every link is a candidate: this is a
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

from .camera_calibration import ground_offsets
from .geolocation import parse_camera_model

MODULE_MATCH_M = 0.35    # under half of the 1.008 m module pitch
FRAME_SHIFT_MAX_M = 0.45
MIN_FRAME_MODULES = 8
LINE_GAP_S = 3           # a longer pause or a turn starts a new flight line
LINE_TURN_DEG = 15
TIE_MIN_RESPONSE = 0.15  # weaker phase correlation locks onto the repeating module grid
TIE_MAX_M = 1.0
LINE_MIN_MARGIN = 5      # inliers the best whole-module position of a line must win by


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


def flight_lines(work, groups):
    """Frames in capture order, split where the camera turns or the capture pauses.

    Returns None when capture times or gimbal yaw are missing (each frame then stands alone).
    """
    if 'gimbal_yaw' not in work:
        return None
    names = pd.Series(list(groups))
    time = pd.to_datetime(names.str.extract(r'DJI_(\d{14})_')[0], format='%Y%m%d%H%M%S', errors='coerce')
    seq = pd.to_numeric(names.str.extract(r'DJI_\d{14}_(\d+)_')[0], errors='coerce')
    yaw = names.map(work.groupby('image_id').gimbal_yaw.first())
    if time.isna().any() or yaw.isna().any():
        return None
    order = pd.DataFrame(dict(name=names, time=time, seq=seq, yaw=yaw)).sort_values(['time', 'seq'])
    lines, previous = [], None
    for row in order.itertuples():
        if previous is None or (row.time - previous.time).total_seconds() > LINE_GAP_S \
                or abs((row.yaw - previous.yaw + 180) % 360 - 180) > LINE_TURN_DEG:
            lines.append([])
        lines[-1].append(row.name)
        previous = row
    return lines


def tie_lookup(ties, transform, latlon):
    """Image-measured motion between consecutive frames, in drawing metres."""
    if ties is None or ties.empty:
        return {}
    good = ties[(ties.response >= TIE_MIN_RESPONSE) & (np.hypot(ties.tie_north_m, ties.tie_east_m) <= TIE_MAX_M)]
    lat, lon = latlon
    base = transform(np.array([[lat, lon]]))[0]
    north = transform(np.array([[lat + 1 / 110950.0, lon]]))[0] - base
    east = transform(np.array([[lat, lon + 1 / (111320.0 * math.cos(math.radians(lat)))]]))[0] - base
    jacobian = np.column_stack((north, east))
    return {(r.source, r.target): jacobian @ np.array([r.tie_north_m, r.tie_east_m]) for r in good.itertuples()}


def chain_lines(lines, fits, ties, tree, pitch_e, heading=None):
    """Correction per frame that is continuous along each flight line.

    One frame on a row cannot tell which module it sees, and its GPS error drifts by more
    than half a module along a line. Consecutive frames differ by little (and by the image
    tie when one was measured), so the whole-module count is carried from frame to frame.
    Each line is then placed by two independent kinds of evidence: its row ends against
    the drawing, and the trend of the lines whose row ends are decisive (an along-track
    offset that flips with flight direction, plus a slow change across the site).
    `heading` maps image to sin(yaw), the along-row part of the flight direction.
    Returns ({image: correction (x, n)}, {image: (line, resolved)}, line report rows,
    {line: {image: correction before the whole-line move}}, trend).
    """
    supported = lambda f: f is not None and (f['distance'] <= MODULE_MATCH_M).mean() >= 0.6
    heading = heading or {}
    info, unwrapped = {}, {}
    for number, line in enumerate(lines):
        delta, carried, previous, absolute, tied = None, np.zeros(2), None, {}, 0
        for image in line:
            if previous is not None:
                step = ties.get((previous, image))
                tied += step is not None
                carried = carried + (step if step is not None else 0)
            previous = image
            fit = fits.get(image)
            if not supported(fit):
                continue
            shift = np.array(fit['shift'])
            k = 0 if delta is None else int(round((delta[0] + carried[0] - shift[0]) / pitch_e))
            delta = shift + (k * pitch_e, 0.0)
            absolute[image], carried = delta, np.zeros(2)
        if not absolute:
            continue
        unwrapped[number] = absolute
        scores = []
        for whole in range(-3, 4):
            inliers = 0
            for image, delta in absolute.items():
                moved = fits[image]['points'] + (delta[0] - fits[image]['shift'][0] + whole * pitch_e, 0.0)
                inliers += int((tree.query(moved)[0] <= MODULE_MATCH_M).sum())
            scores.append((inliers, whole))
        scores.sort(key=lambda t: -t[0])
        info[number] = dict(
            mean=float(np.mean([d[0] for d in absolute.values()])), tied=tied,
            heading=float(np.mean([heading.get(i, 0.0) for i in absolute])),
            north=float(np.mean([fits[i]['points'][:, 1].mean() - fits[i]['shift'][1] for i in absolute])),
            ends=scores[0][1], margin=scores[0][0] - scores[1][0])

    # Trend of the decisive lines: correction = c + a * heading + g * north.
    decisive = [k for k, v in info.items() if v['margin'] >= LINE_MIN_MARGIN and len(unwrapped[k]) >= 5]
    trend = None
    if len(decisive) >= 4:
        design = np.array([[1.0, info[k]['heading'], info[k]['north']] for k in decisive])
        value = np.array([info[k]['mean'] + info[k]['ends'] * pitch_e for k in decisive])
        weight = np.sqrt([len(unwrapped[k]) for k in decisive])
        keep = np.ones(len(decisive), bool)
        for _ in range(3):  # a line placed a whole module off by its row ends must not steer the trend
            coef = np.linalg.lstsq(design[keep] * weight[keep, None], value[keep] * weight[keep], rcond=None)[0]
            residual = np.abs(design @ coef - value)
            keep = residual <= 0.3
        trend = dict(offset_m=float(coef[0]), along_track_m=float(coef[1]), per_north_m=float(coef[2]),
                     spread_m=float(np.std((design @ coef - value)[keep])), lines=int(keep.sum()))

    start, line_of, rows = {}, {}, []
    for number, line in enumerate(lines):
        if number not in info:
            continue
        v = info[number]
        by_trend, residual = None, None
        if trend:
            predicted = trend['offset_m'] + trend['along_track_m'] * v['heading'] + trend['per_north_m'] * v['north']
            by_trend = int(round((predicted - v['mean']) / pitch_e))
            residual = predicted - (v['mean'] + by_trend * pitch_e)
        decisive_ends = v['margin'] >= LINE_MIN_MARGIN
        trend_clear = residual is not None and abs(residual) <= 0.3
        if decisive_ends and (by_trend is None or by_trend == v['ends'] or not trend_clear):
            best, how = v['ends'], 'row_ends'
        elif decisive_ends:
            best, how = v['ends'], 'conflict'   # row ends and trend disagree: keep, but unresolved
        elif trend_clear:
            best, how = by_trend, 'trend'
        else:
            best, how = v['ends'], 'unresolved'
        resolved = how in ('row_ends', 'trend')
        # Frames without their own fit start from the nearest supported neighbour.
        absolute = unwrapped[number]
        corrections, last = {}, None
        for image in line:
            if image in absolute:
                last = absolute[image] + (best * pitch_e, 0.0)
            if last is not None:
                corrections[image] = last
        last = None
        for image in reversed(line):
            if image in absolute:
                last = absolute[image] + (best * pitch_e, 0.0)
            if image not in corrections and last is not None:
                corrections[image] = last
        for image, value in corrections.items():
            start[image], line_of[image] = value, (number, resolved)
        rows.append(dict(line=number, frames=len(line), supported_frames=len(absolute), image_ties=v['tied'],
                         whole_modules=best, decided_by=how, resolved=bool(resolved), margin_inliers=int(v['margin']),
                         row_ends_choice=v['ends'], trend_choice=by_trend,
                         trend_residual_m=None if residual is None else round(float(residual), 3),
                         first=line[0], last=line[-1]))
    return start, line_of, rows, unwrapped, trend


def along_row_gradient(unwrapped, fits, min_frames=5):
    """Change of the correction per metre along the rows, from inside each line.

    Wrapped per-frame shifts hide a trend of more than half a module; unwrapped along a
    line it shows as a slope. Each line keeps its own intercept (its whole-module place
    is still open), so only the slope is shared. Returns (d correction / d x) or None.
    """
    xs, ys = [], []
    for corrections in unwrapped.values():
        if len(corrections) < min_frames:
            continue
        x = np.array([fits[i]['points'][:, 0].mean() - fits[i]['shift'][0] for i in corrections])
        y = np.array(list(corrections.values()))
        xs.append(x - x.mean()); ys.append(y - y.mean(axis=0))
    if not xs:
        return None
    x, y = np.concatenate(xs), np.vstack(ys)
    keep = np.ones(len(x), bool)
    for _ in range(3):  # a slipped frame sits a whole module off the line's trend
        slope = (x[keep, None] * y[keep]).sum(axis=0) / (x[keep] ** 2).sum()
        residual = np.hypot(*(y - x[:, None] * slope).T)
        keep = residual <= max(0.25, 3 * np.median(residual[keep]))
    return slope


def nadir_offsets(work):
    """Drawing x/n metres from each detection to the point below the camera, or None.

    Used to undo the height of a module row: a row higher than the assumed surface
    shows up displaced outward from the nadir, in proportion to that distance.
    """
    needed = ['centroid_u', 'centroid_v', 'img_w', 'img_h', 'camera_to_surface_m', 'gimbal_yaw', 'gimbal_pitch', 'gimbal_roll']
    if any(c not in work for c in needed):
        return None
    out = np.full((len(work), 2), np.nan)
    rows = work[needed].notna().all(axis=1).to_numpy()
    models = work['geo_camera_model'] if 'geo_camera_model' in work else pd.Series('', index=work.index)
    for text in pd.unique(models[rows].fillna('')):
        idx = np.flatnonzero(rows & (models.fillna('') == text).to_numpy())
        off = ground_offsets(work.iloc[idx], parse_camera_model(text))
        out[idx] = off[:, ::-1]  # (north, east) -> drawing (x east, n north)
    return out


def row_heights(work, site, nadir):
    """Height of each module row (R1, R2 of a table) against the fitted surface, in metres."""
    linked = work.link_status.astype(str).str.startswith('module_candidate') & work.drawing_x.notna()
    if not linked.any():
        return {}
    ids = work.loc[linked, 'drawing_module_id']
    pos = site.set_index('drawing_module_id').loc[ids, ['x', 'n']].to_numpy()
    residual = work.loc[linked, ['drawing_x', 'drawing_n']].to_numpy() - pos
    offset = nadir[linked.to_numpy()]
    rng = work.loc[linked, 'camera_to_surface_m'].to_numpy(float)
    label = ids.str.extract(r'-(R\d+)-')[0].to_numpy()
    heights = {}
    for row in pd.unique(label):
        m = (label == row) & np.isfinite(offset).all(axis=1)
        if m.sum() < 200:
            continue
        k = (residual[m] * offset[m]).sum() / (offset[m] ** 2).sum()
        heights[str(row)] = round(float(k * np.median(rng[m])), 3)
    return heights


def _score(frames, transform, tree, xy, offset=(0.0, 0.0)):
    inliers = total = 0
    for latlon in frames:
        total += len(latlon)
        fit = fit_frame(transform(latlon) + offset, tree, xy)
        if fit:
            inliers += int((fit['distance'] <= MODULE_MATCH_M).sum())
    return inliers / total if total else 0.0


def register(master, site, reference, pitch=(1.008, 5.82), ties=None):
    """Return annotated observations and a report. `pitch` is the module pitch and paired-row period.

    `ties` (frame_ties.compute output) joins consecutive frames by their image motion;
    without it consecutive frames are assumed to share their GPS error.
    """
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
    lines = flight_lines(work, groups)
    start, line_of, line_rows, row_scale, trend = {}, {}, [], np.zeros(2), None
    if lines:
        centre = np.nanmean(np.vstack(frames), axis=0)
        steps = tie_lookup(ties, transform, centre)
        yaw = work.groupby('image_id').gimbal_yaw.first()
        heading = {image: math.sin(math.radians(yaw[image])) for image in groups}
        for _ in range(3):  # the along-row slope and the chaining sharpen each other
            fits = {image: fit_frame(transform(latlon), tree, xy) for image, latlon in zip(groups, frames)}
            start, line_of, line_rows, unwrapped, trend = chain_lines(lines, fits, steps, tree, pitch[0], heading)
            slope = along_row_gradient(unwrapped, fits)
            if slope is None or np.abs(slope).max() < 2e-4:
                break
            transform.gradient[:, 0] += slope
            row_scale += slope

    nadir = nadir_offsets(work)
    heights = {}
    for attempt in range(2 if nadir is not None else 1):
        # Second pass: rows are known from the first, so each row's height is undone.
        lift = np.zeros((len(work), 2))
        if heights:
            label = work['drawing_module_id'].astype(str).str.extract(r'-(R\d+)-')[0]
            dh = label.map(heights).fillna(0.0).to_numpy(float)
            lift = np.nan_to_num(nadir * (dh / work['camera_to_surface_m'].to_numpy(float))[:, None])
        for name in ('drawing_module_id', 'string_id', 'jb_id', 'inverter_id', 'link_reason'):
            work[name] = None
        work['link_status'] = 'unmatched'
        work['link_distance_m'] = np.nan
        work['drawing_x'] = work['drawing_n'] = np.nan  # corrected position, also for unmatched detections
        work.loc[~usable, 'link_reason'] = 'no_projected_position'
        frame_rows = []
        for (image, index), latlon in zip(groups.items(), frames):
            offset = start.get(image, np.zeros(2))
            fit = fit_frame(transform(latlon) + offset - lift[index], tree, xy)
            line, line_resolved = line_of.get(image, (None, None))
            label = candidate if line_resolved is None else ('module_candidate' if line_resolved else 'module_candidate_pitch_unresolved')
            if not fit:
                work.loc[index, 'link_reason'] = 'frame_not_registered'
                frame_rows.append(dict(image_id=image, observations=len(index), status='not_registered', line=line))
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
                                   shift_east_m=fit['shift'][0] + offset[0], shift_north_m=fit['shift'][1] + offset[1],
                                   median_distance_m=float(np.median(fit['distance'][unique])) if unique.any() else None,
                                   line=line, line_resolved=line_resolved))
            work.loc[index, 'link_distance_m'] = fit['distance']
            work.loc[index, 'drawing_x'], work.loc[index, 'drawing_n'] = fit['points'][:, 0], fit['points'][:, 1]
            if status != 'registered':
                work.loc[index, 'link_reason'] = 'frame_low_support'
                continue
            matched = site.iloc[fit['index']].reset_index(drop=True)
            for i, row in enumerate(index):
                if unique[i]:
                    for name in ('drawing_module_id', 'string_id', 'jb_id', 'inverter_id'):
                        work.at[row, name] = matched.at[i, name]
                    work.at[row, 'link_status'] = label
                    work.at[row, 'link_reason'] = 'within_module_tolerance_of_refined_drawing'
                else:
                    work.at[row, 'link_reason'] = 'same_frame_collision' if near[i] else 'no_drawing_module_within_tolerance'
        if attempt == 0 and nadir is not None:
            heights = row_heights(work, site, nadir)
            if not heights:
                break
    frame_table = pd.DataFrame(frame_rows)
    linked = work[work.link_status.astype(str).str.startswith('module_candidate')]
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
        flight_lines=None if not line_rows else dict(
            lines=len(line_rows), resolved=sum(r['resolved'] for r in line_rows),
            decided_by=pd.Series([r['decided_by'] for r in line_rows]).value_counts().to_dict(),
            trend=trend,
            frames_on_resolved_lines=sum(r['frames'] for r in line_rows if r['resolved']),
            image_ties_used=sum(r['image_ties'] for r in line_rows), detail=line_rows,
            note='줄 단위로 몇 번째 모듈인지 정했습니다. 해결되지 않은 줄은 한 칸 어긋남을 배제할 수 없습니다.'),
        row_height_above_surface_m=heights or None,
        along_row_correction_per_100m=(row_scale * 100).round(3).tolist(),
        module_candidates_line_unresolved=int((work.link_status == 'module_candidate_pitch_unresolved').sum()),
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
    p.add_argument('--ties', help='frame_ties.csv (선택, 연속 영상 사이 실제 이동)')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    output = Path(a.output); output.mkdir(parents=True, exist_ok=True)
    site = load_site(a.layout, a.cable_model)
    reference = json.loads(Path(a.reference).read_text(encoding='utf-8-sig'))[::50]
    master = pd.read_csv(a.master, encoding='utf-8-sig', low_memory=False)
    ties = pd.read_csv(a.ties, encoding='utf-8-sig') if a.ties else None
    work, frames, report = register(master, site, reference, ties=ties)
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

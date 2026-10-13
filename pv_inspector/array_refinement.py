"""Image-backed two-row grids. All IDs are local proposals, never asset identities.

Arrays are inferred locally from compatible oriented rectangles. Expected cells
are proposals until four image boundaries support them. Unresolved observations
are retained separately; a lattice alone cannot create a module.
"""
from collections import defaultdict
import math

import cv2
import numpy as np
from scipy.spatial import cKDTree

VERSION = 'array_refinement_v2'


def blue_mask(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return cv2.inRange(hsv, (85, 30, 20), (135, 255, 255))


def rgb_candidates(rgb):
    """Scale-adaptive surface proposals, including merged rectangular components."""
    mask = blue_mask(rgb)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for c in contours:
        rect = cv2.minAreaRect(c)
        w, h = rect[1]
        if min(w, h) < 12 or w*h < 200:
            continue
        fill = cv2.contourArea(c) / max(w*h, 1)
        if fill < .60 or max(w, h)/min(w, h) > 5:
            continue
        found.append(dict(polygon=cv2.boxPoints(rect).tolist(), score=float(fill)))
    found.sort(key=lambda c: (np.mean(c['polygon'], axis=0)[1], np.mean(c['polygon'], axis=0)[0]))
    for i, item in enumerate(found):
        item['id'] = f'input-{i:05d}'
    return found


def _geometry(candidate):
    p = np.asarray(candidate['polygon'], dtype=np.float32)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('Invalid polygon')
    p = cv2.convexHull(p).reshape(-1, 2)
    box = cv2.boxPoints(cv2.minAreaRect(p))
    edges = np.roll(box, -1, axis=0)-box
    lengths = np.linalg.norm(edges, axis=1)
    k = int(np.argmin(lengths)); short = float(lengths[k]); long = float(max(lengths))
    if short < 2:
        raise ValueError('Degenerate polygon')
    axis = edges[k]/short
    return dict(poly=p, center=box.mean(axis=0), short=short, long=long, axis=axis,
                area=float(cv2.contourArea(p)))


def _intersection(a, b):
    return float(cv2.intersectConvexConvex(np.asarray(a, np.float32), np.asarray(b, np.float32))[0])


def _deduplicate(candidates, geometry):
    """Suppress near-identical polygons, preserving provenance; not merged boxes."""
    keep = []; duplicates = {}
    for i in sorted(geometry, key=lambda i: (-float(candidates[i].get('score', 0)), i)):
        a = geometry[i]
        match = None
        for j in keep:
            b = geometry[j]
            if np.linalg.norm(a['center']-b['center']) > max(a['long'], b['long']):
                continue
            overlap = _intersection(a['poly'], b['poly'])
            if overlap/max(a['area']+b['area']-overlap, 1) > .72:
                match = j
                break
        if match is None:
            keep.append(i)
        else:
            duplicates[i] = match
    return sorted(keep), duplicates


def infer_arrays(candidates):
    geometry = {}
    for i, c in enumerate(candidates):
        try:
            geometry[i] = _geometry(c)
        except (KeyError, ValueError, cv2.error):
            pass
    unique, duplicates = _deduplicate(candidates, geometry)
    # A single module has a distinct short edge. Square/merged proposals are not seeds.
    seeds = [i for i in unique if 1.2 < geometry[i]['long']/geometry[i]['short'] < 2.3]
    parent = {i: i for i in seeds}

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    if not seeds:
        return [], geometry, duplicates
    tree = cKDTree([geometry[i]['center'] for i in seeds])
    for ii, i in enumerate(seeds):
        a = geometry[i]
        for jj in tree.query_ball_point(a['center'], 3.2*a['long']):
            j = seeds[jj]
            if j <= i:
                continue
            b = geometry[j]
            if not (.75 < a['short']/b['short'] < 1.33 and .75 < a['long']/b['long'] < 1.33):
                continue
            if abs(float(a['axis'] @ b['axis'])) < math.cos(math.radians(12)):
                continue
            delta = b['center']-a['center']; axis = a['axis']; cross = np.array([-axis[1], axis[0]])
            du, dv = abs(delta @ axis), abs(delta @ cross)
            s, l = (a['short']+b['short'])/2, (a['long']+b['long'])/2
            along = .7*s < du < 2.5*s and dv < .25*l
            across = du < .3*s and .75*l < dv < 1.35*l
            if along or across:
                parent[root(j)] = root(i)
    groups = defaultdict(list)
    for i in seeds:
        groups[root(i)].append(i)
    arrays = []
    for group in groups.values():
        if len(group) < 6:
            continue
        angles = [math.atan2(*geometry[i]['axis'][::-1]) for i in group]
        theta = .5*np.angle(np.mean(np.exp(2j*np.asarray(angles))))
        basis = np.array([[math.cos(theta), math.sin(theta)], [-math.sin(theta), math.cos(theta)]])
        centers = np.array([geometry[i]['center'] for i in group]) @ basis.T
        s = float(np.median([geometry[i]['short'] for i in group]))
        l = float(np.median([geometry[i]['long'] for i in group]))
        # Remove common image slope before splitting the two rows.
        rows = []
        for index in np.argsort(centers[:, 1]):
            if not rows or centers[index, 1]-np.median(centers[rows[-1], 1]) > .5*l:
                rows.append([])
            rows[-1].append(int(index))
        if len(rows) != 2 or min(map(len, rows)) < 3:
            continue
        lines = []
        reliable = True
        for row in rows:
            xy = centers[row]
            fit = np.polyfit(xy[:, 0], xy[:, 1], 1)
            if max(abs(np.polyval(fit, xy[:, 0])-xy[:, 1])) > .18*l:
                reliable = False
            lines.append(fit)
        mid_u = float(np.median(centers[:, 0]))
        if not reliable or not .8*l < abs(np.polyval(lines[1], mid_u)-np.polyval(lines[0], mid_u)) < 1.35*l:
            continue
        columns = []
        for u in sorted(centers[:, 0]):
            if not columns or u-np.mean(columns[-1]) > .4*s:
                columns.append([])
            columns[-1].append(float(u))
        positions = [float(np.median(c)) for c in columns]
        gaps = np.diff(positions)
        near = gaps[(gaps > .75*s) & (gaps < 1.4*s)]
        if len(near) < 2:
            continue
        pitch = float(np.median(near))
        # Insert only internal gaps; never extend past observed array endpoints.
        slots = [positions[0]]
        for x in positions[1:]:
            gap = x-slots[-1]; steps = int(round(gap/pitch))
            if 2 <= steps <= 3 and abs(gap/steps-pitch) < .15*pitch:
                slots.extend(np.linspace(slots[-1], x, steps+1)[1:-1].tolist())
            slots.append(x)
        array = dict(id=f'array-{len(arrays)+1:03d}', basis=basis, lines=lines,
                     short=s, long=l, pitch=pitch, columns=slots, seeds=group)
        arrays.append(array)
    return arrays, geometry, duplicates


def _cell_polygon(array, row, u):
    s, l = array['short'], array['long']; slope, intercept = array['lines'][row]
    pts = [[x, slope*x+intercept+dy] for x, dy in
           ((u-s/2, -l/2), (u+s/2, -l/2), (u+s/2, l/2), (u-s/2, l/2))]
    return np.asarray(pts) @ array['basis']


def inspect_cell(rgb, polygon, mode='rgb'):
    """Search near expected edges at native scale; require all four boundaries."""
    if mode not in ('rgb', 'thermal'):
        raise ValueError('mode must be rgb or thermal')
    p = np.asarray(polygon, np.float32)
    h_img, w_img = rgb.shape[:2]
    if p[:, 0].min() < 2 or p[:, 1].min() < 2 or p[:, 0].max() > w_img-3 or p[:, 1].max() > h_img-3:
        return dict(accepted=False, reason='clipped_cell')
    w = max(8, round(np.linalg.norm(p[1]-p[0]))); h = max(8, round(np.linalg.norm(p[3]-p[0])))
    pad = max(4, round(.22*min(w, h)))
    target = np.float32([[pad, pad], [pad+w, pad], [pad+w, pad+h], [pad, pad+h]])
    transform = cv2.getPerspectiveTransform(p, target)
    patch = cv2.warpPerspective(rgb, transform, (w+2*pad+1, h+2*pad+1))
    if mode == 'rgb':
        signal = blue_mask(patch).astype(np.float32)/255
    else:
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY).astype(np.float32)
        signal = gray/max(float(np.percentile(gray, 95)-np.percentile(gray, 5)), 25)
    # Broad edge support rejects thin cell busbars and isolated bright pixels.
    step = max(2, round(min(w, h)*.025))
    edges = []; scores = []
    for axis, expected, inward, span in ((0, pad, 1, (pad+.15*h, pad+.85*h)),
                                         (0, pad+w, -1, (pad+.15*h, pad+.85*h)),
                                         (1, pad, 1, (pad+.15*w, pad+.85*w)),
                                         (1, pad+h, -1, (pad+.15*w, pad+.85*w))):
        radius = max(2, round(.12*(w if axis == 0 else h)))
        choices = []
        for pos in range(max(step, expected-radius), min(signal.shape[1-axis]-step, expected+radius+1)):
            start, end = map(int, span)
            if axis == 0:
                inside = signal[start:end, pos+inward*step]; outside = signal[start:end, pos-inward*step]
            else:
                inside = signal[pos+inward*step, start:end]; outside = signal[pos-inward*step, start:end]
            diff = inside-outside
            score = float(np.mean(np.maximum(diff, 0))) if mode == 'rgb' else float(np.mean(np.abs(diff)))
            choices.append((score-.05*abs(pos-expected)/max(radius, 1), score, pos))
        _, score, pos = max(choices)
        edges.append(pos); scores.append(round(score, 4))
    left, right, top, bottom = edges
    fill = float(blue_mask(patch[top:bottom, left:right]).mean()/255) if right>left and bottom>top else 0
    threshold = .30 if mode == 'rgb' else .20
    valid = min(scores) >= threshold and .75*w < right-left < 1.3*w and .75*h < bottom-top < 1.3*h
    if mode == 'rgb':
        valid = valid and fill >= .60
    refined = cv2.perspectiveTransform(np.float32([[[left, top], [right, top], [right, bottom], [left, bottom]]]), np.linalg.inv(transform))[0]
    return dict(accepted=bool(valid), reason='four_image_edges' if valid else 'insufficient_image_edges',
                edge_scores=scores, surface_fill=round(fill, 4), polygon=refined.tolist())


def refine_arrays(rgb, candidates=None, mode='rgb'):
    """Return supported cells plus preserved unresolved candidates and full audit."""
    # Rasterio's HWC transpose is strided. Otherwise OpenCV copies the entire tile
    # for EVERY small cell warp (tens of GB of unnecessary copies per tile).
    rgb = np.ascontiguousarray(rgb)
    if candidates is None:
        if mode != 'rgb':
            raise ValueError('Thermal refinement requires detector proposals')
        candidates = rgb_candidates(rgb)
    if len({str(c.get('id', i)) for i, c in enumerate(candidates)}) != len(candidates):
        raise ValueError('Candidate IDs must be unique')
    arrays, geometry, duplicates = infer_arrays(candidates)
    geometry_ids = list(geometry)
    geometry_tree = cKDTree([geometry[i]['center'] for i in geometry_ids]) if geometry_ids else None
    slots = []; source_slots = defaultdict(list)
    for a in arrays:
        for row in range(2):
            for column, u in enumerate(a['columns']):
                polygon = _cell_polygon(a, row, u)
                area = cv2.contourArea(np.asarray(polygon, np.float32))
                nearby = geometry_tree.query_ball_point(polygon.mean(axis=0), 2*a['long']) if geometry_tree else []
                sources = [geometry_ids[j] for j in nearby if geometry_ids[j] not in duplicates and
                           geometry[geometry_ids[j]]['area'] <= 3.2*max(area, 1) and
                           _intersection(polygon, geometry[geometry_ids[j]]['poly'])/max(area, 1) >= .45]
                evidence = inspect_cell(rgb, polygon, mode)
                slot = dict(id=f"{a['id']}-R{row+1}-C{column+1:03d}", array_id=a['id'], row=row+1,
                            column=column+1, expected_polygon=polygon.tolist(), source_indices=sources,
                            status='image_supported' if evidence['accepted'] else 'unconfirmed', evidence=evidence)
                slots.append(slot)
                if evidence['accepted']:
                    for i in sources:
                        source_slots[i].append(slot['id'])
    modules = []
    for slot in slots:
        if slot['status'] != 'image_supported':
            continue
        sources = slot['source_indices']
        origin = 'gap_reinspection' if not sources else 'merged_split' if any(len(source_slots[i])>1 for i in sources) else 'boundary_refined'
        modules.append(dict(id=slot['id'], polygon=slot['evidence']['polygon'],
                            center=np.mean(slot['evidence']['polygon'], axis=0).tolist(),
                            status='image_supported', origin=origin,
                            source_ids=[str(candidates[i].get('id', i)) for i in sources],
                            array_id=slot['array_id'], row=slot['row'], column=slot['column']))
    # A partly explained merged box is still unresolved. Never silently lose it.
    unresolved = []; audit = []
    for i, source in enumerate(candidates):
        explained = source_slots.get(i, [])
        if i in duplicates:
            action = 'duplicate_suppressed'
        elif explained:
            g = geometry[i]
            covered = sum(_intersection(g['poly'], m['polygon']) for m in modules if m['id'] in explained)
            action = 'replaced_by_cells' if covered/max(g['area'], 1) >= .70 else 'partly_explained_review'
        else:
            action = 'unconfirmed_preserved'
        if action in ('unconfirmed_preserved', 'partly_explained_review'):
            unresolved.append({**source, 'status': 'review', 'reason': action})
        audit.append(dict(source_id=str(source.get('id', i)), action=action, cell_ids=explained,
                          duplicate_of=str(candidates[duplicates[i]].get('id', duplicates[i])) if i in duplicates else None))
    serial_arrays = [dict(id=a['id'], seed_indices=a['seeds'], columns=len(a['columns']),
                         module_size=[a['short'], a['long']], pitch=a['pitch'],
                         polygon=np.concatenate([_cell_polygon(a, 0, a['columns'][0])[:1],
                                                 _cell_polygon(a, 0, a['columns'][-1])[1:2],
                                                 _cell_polygon(a, 1, a['columns'][-1])[2:3],
                                                 _cell_polygon(a, 1, a['columns'][0])[3:]]).tolist()) for a in arrays]
    return dict(version=VERSION, mode=mode, arrays=serial_arrays, modules=modules,
                unresolved=unresolved, slots=slots, source_audit=audit,
                summary=dict(input_candidates=len(candidates), arrays=len(arrays), image_supported=len(modules),
                             unconfirmed_slots=sum(s['status']=='unconfirmed' for s in slots),
                             unresolved_candidates=len(unresolved), duplicates=len(duplicates),
                             split_sources=sum(len(v)>1 for v in source_slots.values()),
                             recovered_cells=sum(m['origin']=='gap_reinspection' for m in modules)))

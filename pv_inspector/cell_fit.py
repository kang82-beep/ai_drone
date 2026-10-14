"""How well a detection sits on the two-row array grid, and re-measurement on the grid cell.

array_refinement already rebuilds each frame's two-row grid and finds the four boundaries
of every module cell it can confirm in the image (array_review/<image>.json, "modules").
Observations are classified against those cells:

* aligned        the detector box matches its cell (IoU >= ALIGNED_IOU)
* shifted        it has a cell but the box sits off it, typically across a module gap
* straddle       no cell, but the box covers parts of two or more confirmed cells
* clipped        no cell and the box touches the frame border: the module is cut off
* unconfirmed    no cell and no clear overlap; the grid could not confirm this spot
* off_structure  no cell, outside every cell, weak two-row evidence and not on the drawing

Only aligned and unconfirmed views are trusted to vote on a module verdict; shifted and
straddling boxes mix a module gap or a neighbour into the measurement, and a module cut
off by the frame border is only partly measured. On the first 49 frames these views were
flagged at 55 % (shifted) and 17 % (no cell, half of them clipped) against 5 % aligned.

Re-measuring temperature on the cell was tried (compare_cell_measurement.py) and is not
used: detector masks already gave the same temperatures (median change 0.08 °C), while
re-cropping for the classifier flipped 3.7 % of decisions.
"""
import numpy as np
import cv2

ALIGNED_IOU = .6
STRADDLE_SHARE = .25
BORDER_PX = 15
TRUSTED_FITS = {'aligned', 'unconfirmed'}


def _mask(shape, polygon):
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.round(np.asarray(polygon, float)).astype(np.int32)], 1)
    return mask.astype(bool)


def _window_mask(polygon, window, shape):
    """Polygon rasterised as _mask does, but only inside window (x0, y0, x1, y1) of the frame."""
    x0, y0, x1, y1 = window
    points = np.round(np.asarray(polygon, float)).astype(np.int32) - (x0, y0)
    mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(mask, [points], 1)
    return mask.astype(bool)


def _bounds(polygon, shape):
    """Frame-clipped pixel window that holds every pixel of the rasterised polygon."""
    points = np.round(np.asarray(polygon, float)).astype(int)
    height, width = shape
    return (min(max(points[:, 0].min(), 0), width), min(max(points[:, 1].min(), 0), height),
            min(max(points[:, 0].max() + 1, 0), width), min(max(points[:, 1].max() + 1, 0), height))


def fit(box, cell_polygon, frame_cells, structure_status=None, on_drawing=True, shape=(1024, 1280)):
    """Return (fit label, IoU with own cell or None) for one detection box (x1, y1, x2, y2).

    Masks are drawn only in the window around the box and cell: a full-frame mask per
    cell made a whole flight (77 k views x ~80 cells) take hours.
    """
    x1, y1, x2, y2 = (int(round(v)) for v in box)
    height, width = shape
    bx = (min(max(x1, 0), width), min(max(y1, 0), height), min(max(x2, 0), width), min(max(y2, 0), height))
    box_area = max(bx[2] - bx[0], 0) * max(bx[3] - bx[1], 0)
    if cell_polygon is not None:
        cb = _bounds(cell_polygon, shape)
        window = (min(bx[0], cb[0]), min(bx[1], cb[1]), max(bx[2], cb[2]), max(bx[3], cb[3]))
        cell = _window_mask(cell_polygon, window, shape)
        inside = cell[bx[1] - window[1]:bx[3] - window[1], bx[0] - window[0]:bx[2] - window[0]].sum()
        union = box_area + cell.sum() - inside
        iou = float(inside / union) if union else 0.0
        return ('aligned' if iou >= ALIGNED_IOU else 'shifted'), round(iou, 3)
    covered = 0
    touched = False
    for polygon in frame_cells:
        cb = _bounds(polygon, shape)
        if box_area == 0 or cb[0] >= bx[2] or cb[2] <= bx[0] or cb[1] >= bx[3] or cb[3] <= bx[1]:
            continue  # no shared pixel: neither touches nor covers
        overlap = _window_mask(polygon, bx, shape).sum()
        touched |= overlap > 0
        if overlap >= STRADDLE_SHARE * _window_mask(polygon, cb, shape).sum():
            covered += 1
    if covered >= 2:
        return 'straddle', None
    height, width = shape
    if x1 < BORDER_PX or y1 < BORDER_PX or x2 > width - BORDER_PX or y2 > height - BORDER_PX:
        return 'clipped', None
    if not touched and structure_status == 'low' and not on_drawing:
        return 'off_structure', None
    return 'unconfirmed', None


def fit_observations(linked, resolve):
    """cell_fit label per row of a linked table; resolve maps a stored path to a local Path."""
    import json
    labels, cache = [], {}
    for row in linked.to_dict('records'):
        path = row.get('array_review_path')
        if isinstance(path, str) and path not in cache:
            local = resolve(path)
            cache[path] = ({m['id']: m['polygon'] for m in json.loads(local.read_text(encoding='utf-8'))['modules']
                            if m.get('status') == 'image_supported'} if local.is_file() else {})
        cells = cache.get(path, {}) if isinstance(path, str) else {}
        ids = json.loads(row['array_proposed_cells']) if isinstance(row.get('array_proposed_cells'), str) else []
        box = (row['bbox_x1'], row['bbox_y1'], row['bbox_x2'], row['bbox_y2'])
        label, _ = fit(box, cells.get(ids[0]) if ids else None, list(cells.values()), row.get('structure_status'),
                       row.get('link_status') != 'unmatched')
        labels.append(label)
    return labels


def cell_mask(polygon, shape=(1024, 1280)):
    return _mask(shape, polygon)


def cell_crop(image, polygon):
    """Axis-aligned crop around a cell, the same way the pipeline crops a detector box."""
    points = np.asarray(polygon, float)
    x1, y1 = np.floor(points.min(0)).astype(int)
    x2, y2 = np.ceil(points.max(0)).astype(int)
    h, w = image.shape[:2]
    return image[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]

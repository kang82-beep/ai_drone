"""Shape rules for thermal anomaly types (과제_기획서 3.4) plus shading and viewing-angle cautions.

Each observation's module is cut from the radiometric array (640x512 float32, the
detection boxes are in the 1280x1024 display frame) and rotated into a canonical
patch: long side horizontal, the low (south) edge of the tilted module on the right.
On that patch simple rules separate a single hot cell, several hot cells, a bypass
diode third, a whole hot module, a hot band along the low edge (shading by grass or
the row in front) and a long diagonal streak (shadow of a pole or structure).
Results are candidates for inspection, never confirmed faults.
"""
import math
import cv2
import numpy as np

SHORT, LONG = 30, 50          # canonical patch: 6 x 10 cells of 5 x 5 px
CELL = (SHORT / 6) * (LONG / 10)
RAW_SCALE = .5                # raw array pixels per display pixel
EDGE_RADIUS = .7              # normalised distance from the image centre treated as the periphery
TYPES = {
    'single_cell': '단일 셀 핫스팟', 'multi_cell': '다중 셀 핫스팟', 'diode': '바이패스 다이오드 의심 (1/3 띠)',
    'whole_module': '모듈 전체 발열', 'low_edge_band': '하단 띠 (낮은 쪽, 음영 의심)', 'high_edge_band': '상단 띠 (높은 쪽)',
    'linear_streak': '선형 띠 (구조물 그림자 의심)', 'partial_shade': '부분 그늘 (음영 의심)',
    'none': '뚜렷한 패턴 없음', 'unreadable': '판독 불가 (윤곽 불확실)',
}
SHADOW_TYPES = {'low_edge_band', 'linear_streak', 'partial_shade'}


def load_raw(path):
    data = np.fromfile(str(path), dtype=np.float32)
    return data.reshape(512, 640) if data.size == 640 * 512 else None


def south_vector(gimbal_yaw):
    """Unit vector pointing to the low (ground-side) edge of the tables in image coordinates (x right, y down).

    Taking image-up as the gimbal yaw put the hot band of shaded modules on the high edge, but
    on site that band sits on the ground side (confirmed by the operator, 2026-10-14). In these
    M4T nadir frames image-up therefore points opposite the gimbal yaw.
    """
    angle = math.radians(-gimbal_yaw)  # clockwise from image-up
    return math.sin(angle), -math.cos(angle)


def canonical(patch, gimbal_yaw):
    """Rotate (never mirror) so the long side is horizontal and the south (low) edge is on the right."""
    sx, sy = south_vector(gimbal_yaw)
    if patch.shape[0] > patch.shape[1]:  # long side vertical: south is up or down
        patch = np.rot90(patch, -1 if sy < 0 else 1)  # clockwise moves the top to the right
    elif sx < 0:
        patch = np.rot90(patch, 2)
    return cv2.resize(np.ascontiguousarray(patch), (LONG, SHORT), interpolation=cv2.INTER_AREA)


def _edge(profile, guess, window, side):
    """Index of the coolest line (inter-module gap or ground) near an expected module edge."""
    lo, hi = max(0, guess - window), min(len(profile) - 1, guess + window)
    if hi <= lo:
        return guess
    index = lo + int(np.argmin(profile[lo:hi + 1]))
    return index + 1 if side == 'start' else index - 1


def refine_box(raw, bbox):
    """Snap a loose detection box (display pixels) to the module's own boundaries in the raw array.

    Detection boxes overlap neighbouring modules by 10–20 %. Gaps between modules and the
    ground beside a table read cooler than the cells, so each edge moves to the coolest
    line within a quarter of the module size of where the detector put it.
    """
    x1, y1, x2, y2 = (int(round(v * RAW_SCALE)) for v in bbox)
    w, h = x2 - x1, y2 - y1
    pad_x, pad_y = max(2, w // 4), max(2, h // 4)
    X1, Y1, X2, Y2 = max(0, x1 - pad_x), max(0, y1 - pad_y), min(raw.shape[1], x2 + pad_x), min(raw.shape[0], y2 + pad_y)
    region = raw[Y1:Y2, X1:X2]
    rows = region[pad_y + h // 5: pad_y + h - h // 5]
    cols = region[:, pad_x + w // 5: pad_x + w - w // 5]
    px, py = rows.mean(0), cols.mean(1)
    left, right = _edge(px, x1 - X1, w // 4, 'start'), _edge(px, x2 - X1, w // 4, 'end')
    top, bottom = _edge(py, y1 - Y1, h // 4, 'start'), _edge(py, y2 - Y1, h // 4, 'end')
    # Keep the detector's box when snapping would change the module's size implausibly.
    if not (.7 * w <= right - left <= 1.15 * w and .7 * h <= bottom - top <= 1.15 * h):
        return (x1, y1, x2, y2), False
    return (X1 + left, Y1 + top, X1 + right, Y1 + bottom), True


def polygon_patch(image, polygon, gimbal_yaw, inset=.04, scale=RAW_SCALE, size=(LONG, SHORT), trim=True):
    """Warp a refined module outline (4 display-pixel corners, any rotation) into the canonical patch.

    The canonical x axis runs along the module's long side towards the south (low) edge, the
    y axis is that direction turned 90° clockwise, so the patch is rotated, never mirrored.
    """
    points = np.array(polygon, float) * scale
    centre = points.mean(0)
    sides = [points[1] - points[0], points[2] - points[1]]
    lengths = [float(np.hypot(*s)) for s in sides]
    long_i = int(np.argmax(lengths))
    u = sides[long_i] / lengths[long_i]
    sx, sy = south_vector(gimbal_yaw)
    if u[0] * sx + u[1] * sy < 0:
        u = -u
    v = np.array([-u[1], u[0]])
    half_long, half_short = lengths[long_i] / 2 * (1 - inset), lengths[1 - long_i] / 2 * (1 - inset)
    source = np.float32([centre - u * half_long - v * half_short, centre + u * half_long - v * half_short,
                         centre + u * half_long + v * half_short, centre - u * half_long + v * half_short])
    width, height = size[0] * 2, size[1] * 2
    target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    patch = cv2.warpPerspective(image, cv2.getPerspectiveTransform(source, target), (width, height), flags=cv2.INTER_LINEAR)
    if not np.isfinite(patch).all():
        return None
    if trim:
        patch = trim_gaps(patch)
    return cv2.resize(patch, size, interpolation=cv2.INTER_AREA)


def trim_gaps(patch, limit=.2):
    """Drop border rows/columns that are inter-module gap or ground rather than cells.

    Outlines tend to include a sliver of the gap or the ground beside the module; those
    lines read clearly cooler than the module's cells and would look like shade.
    """
    centre = patch[patch.shape[0] // 4:-patch.shape[0] // 4, patch.shape[1] // 4:-patch.shape[1] // 4]
    reference = float(np.median(centre))
    spread = float(np.median(np.abs(centre - reference))) * 1.4826 + .3
    cut = reference - max(1.5, 3 * spread)
    top, bottom, left, right = 0, patch.shape[0], 0, patch.shape[1]
    while top < patch.shape[0] * limit and patch[top, left:right].mean() < cut:
        top += 1
    while bottom > patch.shape[0] * (1 - limit) and patch[bottom - 1, left:right].mean() < cut:
        bottom -= 1
    while left < patch.shape[1] * limit and patch[top:bottom, left].mean() < cut:
        left += 1
    while right > patch.shape[1] * (1 - limit) and patch[top:bottom, right - 1].mean() < cut:
        right -= 1
    return patch[top:bottom, left:right]


def dominant_angle(region):
    """In-image rotation of the module grid (degrees, -45..45) from gradient directions."""
    gx = cv2.Sobel(region, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(region, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(gx, gy)
    angle = (np.degrees(np.arctan2(gy, gx)) + 45) % 90 - 45  # fold so both grid directions agree
    keep = magnitude > np.percentile(magnitude, 80)
    histogram, edges = np.histogram(angle[keep], bins=90, range=(-45, 45), weights=magnitude[keep])
    histogram = np.convolve(np.r_[histogram[-2:], histogram, histogram[:2]], np.ones(5) / 5, 'valid')
    return float(edges[int(np.argmax(histogram))] + .5)


def module_patch(raw, bbox, gimbal_yaw, gsd_m, module_m=(1.0, 1.425), inset=1):
    """Cut one module as an upright patch, correcting rotation and the loose detection box.

    The grid angle comes from the gradients around the detection; after rotating upright
    the module edges snap to the coolest lines (inter-module gaps, ground) near the size
    expected from the flight height. Returns (canonical patch, display bbox, snapped).
    """
    x1, y1, x2, y2 = (v * RAW_SCALE for v in bbox)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    half = int(max(x2 - x1, y2 - y1) * .9)
    X1, Y1 = int(max(0, cx - half)), int(max(0, cy - half))
    region = raw[Y1:int(min(raw.shape[0], cy + half)), X1:int(min(raw.shape[1], cx + half))].astype(np.float32)
    display = list(bbox)
    if region.shape[0] < 20 or region.shape[1] < 20 or not np.isfinite(region).all():
        return None, display, False
    theta = dominant_angle(region)
    centre = (cx - X1, cy - Y1)
    upright = cv2.warpAffine(region, cv2.getRotationMatrix2D(centre, theta, 1), region.shape[::-1], flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
    # Expected module size in raw pixels; which side is horizontal follows the detection box.
    pixel = gsd_m / RAW_SCALE
    a, b = module_m[1] / pixel, module_m[0] / pixel
    w, h = (a, b) if (x2 - x1) >= (y2 - y1) else (b, a)
    px = upright[int(centre[1] - h / 4):int(centre[1] + h / 4)].mean(0)
    py = upright[:, int(centre[0] - w / 4):int(centre[0] + w / 4)].mean(1)
    left = _edge(px, int(centre[0] - w / 2), max(2, int(w / 5)), 'start')
    right = _edge(px, int(centre[0] + w / 2), max(2, int(w / 5)), 'end')
    top = _edge(py, int(centre[1] - h / 2), max(2, int(h / 5)), 'start')
    bottom = _edge(py, int(centre[1] + h / 2), max(2, int(h / 5)), 'end')
    snapped = .8 * w <= right - left <= 1.2 * w and .8 * h <= bottom - top <= 1.2 * h
    if not snapped:
        left, right, top, bottom = (int(round(v)) for v in (centre[0] - w / 2, centre[0] + w / 2, centre[1] - h / 2, centre[1] + h / 2))
    patch = upright[top + inset:bottom - inset, left + inset:right - inset]
    if patch.size < 200:
        return None, display, False
    if abs(theta) < 1:
        display = [(X1 + left) / RAW_SCALE, (Y1 + top) / RAW_SCALE, (X1 + right) / RAW_SCALE, (Y1 + bottom) / RAW_SCALE]
    return canonical(trim_gaps(patch), gimbal_yaw), display, bool(snapped)


def radius(u, v, width, height):
    return float(math.hypot((u - width / 2) / (width / 2), (v - height / 2) / (height / 2)) / math.sqrt(2))


def classify(patch, neighbor_delta_mean, neighbor_ref=None):
    """Return (type, features) for a canonical temperature patch in °C (south / low edge on the right).

    First decide whether the module is split into a warm and a cool part (Otsu on the patch,
    both parts sizeable, clearly different). A split is named by the shape of the warm part:
    a band across the short side at one end (edge band), a strip along the long side covering
    one or two thirds (bypass diode substring), or any other boundary (shade edge, often a
    straight shadow line). Only an unsplit module is checked for cell hot spots and for being
    uniformly hotter than its neighbours.
    """
    # Judge the module interior: outlines leave thin, often slanted slivers of gap or ground along
    # the long sides. End bands are read along the long axis, so trimming the long sides keeps them.
    patch = cv2.resize(np.ascontiguousarray(patch[4:-4, 2:-2]), (LONG, SHORT), interpolation=cv2.INTER_LINEAR)
    base = float(np.median(patch))
    detail = patch - cv2.GaussianBlur(patch, (0, 0), 2)
    noise = float(np.median(np.abs(detail))) * 1.4826
    threshold = max(1.5, 4 * noise)
    lo, hi = float(patch.min()), float(patch.max())
    scaled = np.uint8(np.clip((patch - lo) / max(hi - lo, 1e-6) * 255, 0, 255))
    level, _ = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    warm = scaled > level
    warm_share = float(warm.mean())
    contrast = float(patch[warm].mean() - patch[~warm].mean()) if 0 < warm_share < 1 else 0.0
    split = .12 <= warm_share <= .88 and contrast >= max(2.0, 1.5 * threshold)
    full_columns = float((warm.mean(0) >= .8).mean())   # columns warm across the short side
    full_rows = float((warm.mean(1) >= .8).mean())      # rows warm along the long side
    columns = np.nonzero(warm.mean(0) >= .8)[0]
    band_centre = float(columns.mean() / (LONG - 1)) if len(columns) else None

    hot = (patch - base) >= threshold
    count, labels, stats, _ = cv2.connectedComponentsWithStats(hot.astype(np.uint8), connectivity=8)
    blobs = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= CELL * .4]
    areas = sorted((stats[i, cv2.CC_STAT_AREA] / CELL for i in blobs), reverse=True)
    elongation, slant = 0.0, 0.0
    if blobs:
        largest = max(blobs, key=lambda i: stats[i, cv2.CC_STAT_AREA])
        ys, xs = np.nonzero(labels == largest)
        if len(xs) >= 6:
            values, vectors = np.linalg.eigh(np.cov(np.vstack([xs, ys])))
            elongation = float(math.sqrt(values[1] / max(values[0], 1e-6)))
            major = vectors[:, 1]
            slant = float(abs(math.degrees(math.atan2(major[1], major[0]))) % 90)
            slant = min(slant, 90 - slant)  # 0 = along a module edge, 45 = diagonal
    features = {'base_c': round(base, 2), 'threshold_c': round(threshold, 2), 'split': split,
                'warm_share': round(warm_share, 3), 'split_contrast_c': round(contrast, 2),
                'full_columns': round(full_columns, 3), 'full_rows': round(full_rows, 3),
                'band_centre': round(band_centre, 2) if band_centre is not None else None,
                'blobs': len(blobs), 'largest_blob_cells': round(areas[0], 2) if areas else 0.0,
                'p95_minus_median_c': round(float(np.percentile(patch, 95)) - base, 2),
                'elongation': round(elongation, 1), 'slant_deg': round(slant, 1)}
    if blobs and elongation >= 3.5 and slant >= 15 and areas[0] >= 1.5:
        kind = 'linear_streak'
    elif split and full_columns >= .1 and warm_share <= full_columns + .12:
        touches_end = columns.min() <= 2 or columns.max() >= LONG - 3
        kind = ('low_edge_band' if band_centre > .5 else 'high_edge_band') if touches_end else 'partial_shade'
    elif split and full_rows >= .1 and warm_share <= full_rows + .12:
        # A substring boundary sits on the 1/3 or 2/3 cell line; any other straight boundary is a shade edge.
        kind = 'diode' if abs(warm_share - 1 / 3) <= .06 or abs(warm_share - 2 / 3) <= .06 else 'partial_shade'
    elif split:
        kind = 'partial_shade'
    elif (neighbor_delta_mean or 0) >= 2 and features['p95_minus_median_c'] < 1.5:
        kind = 'whole_module'
    elif len(blobs) == 1 and areas[0] <= 2.5:
        kind = 'single_cell'
    elif blobs:
        kind = 'multi_cell'
    else:
        kind = 'none'
    return kind, features

def rgb_shading(rgb_patch, hot_patch):
    """Share of the hot area that lies on visibly darker panel area of the aligned visible patch.

    rgb_patch is the same module outline cut from the visible image (canonical layout, grey).
    The fixed alignment is good to about one cell, so the dark mask is dilated by one cell
    before the overlap is taken. Returns (dark_fraction, hot_on_dark).
    """
    patch = cv2.GaussianBlur(rgb_patch.astype(np.float32), (0, 0), 1.2)  # suppress the cell grid lines
    base = np.median(patch)
    spread = np.median(np.abs(patch - base)) * 1.4826 + 1e-6
    dark = (patch < base - max(12, 2.5 * spread)).astype(np.uint8)
    dark = cv2.dilate(dark, np.ones((5, 5), np.uint8)) > 0
    return float(dark.mean()), float((hot_patch & dark).sum() / max(1, hot_patch.sum()))


def shadow_suspected(kind, shading):
    """True when the shape or the visible image points to shading rather than a module defect."""
    return kind in SHADOW_TYPES or bool(shading and shading[1] >= .5 and shading[0] >= .03)


def caution(kind, edge, shading):
    """Plain-language caution for the operator; empty when nothing argues against a real defect."""
    notes = []
    if kind == 'low_edge_band':
        notes.append('모듈의 낮은 쪽 끝을 따라 띠 모양으로 뜨겁습니다. 풀이나 앞줄 구조물에 의한 음영일 가능성이 큽니다.')
    if kind == 'high_edge_band':
        notes.append('모듈의 높은 쪽 끝을 따라 띠 모양으로 뜨겁습니다. 반사나 음영일 수 있습니다.')
    if kind == 'linear_streak':
        notes.append('비스듬한 선 모양의 발열입니다. 기둥·구조물 그림자일 가능성이 큽니다.')
    if kind == 'partial_shade':
        notes.append('모듈 일부가 나머지보다 뚜렷하게 차갑게 찍혔습니다. 구조물·수목 그림자로 그늘진 경우가 많습니다.')
    if shading and shading[1] >= .5 and shading[0] >= .03:
        notes.append(f'발열 영역의 {shading[1]:.0%}가 가시광에서 어둡게 보이는 곳과 겹칩니다. 그림자 또는 오염에 의한 음영일 수 있습니다.')
    if shadow_suspected(kind, shading):
        notes.append('그림자가 지나간 다른 시간대에 다시 촬영하거나 현장에서 음영 여부를 확인하세요.')
    if edge:
        notes.append('영상 가장자리에서 찍힌 관측입니다. 비스듬히 보면 반사로 온도가 잘못 찍힐 수 있으니, 가운데에서 찍힌 관측과 비교하세요.')
    return notes
"""PV inspection: geometry."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
import os, re, json, time, math, shutil, subprocess, io
import numpy as np

def _fov_from_35mm_equiv(f35: float, frame_wh=(36.0, 24.0)) -> Tuple[float, float]:
    W, H = frame_wh
    hfov = 2.0 * math.degrees(math.atan((W * 0.5) / max(1e-6, f35)))
    vfov = 2.0 * math.degrees(math.atan((H * 0.5) / max(1e-6, f35)))
    return hfov, vfov


def _gsd_from_fov_and_alt(hfov_deg: float, vfov_deg: float, alt_m: float, img_w: int, img_h: int):
    Wg = 2.0 * alt_m * math.tan(math.radians(hfov_deg * 0.5))
    Hg = 2.0 * alt_m * math.tan(math.radians(vfov_deg * 0.5))
    gsd_x = Wg / max(1, img_w)
    gsd_y = Hg / max(1, img_h)
    return Wg, Hg, gsd_x, gsd_y


def _enu_offset_to_latlon(lat0: float, lon0: float, dE_m: float, dN_m: float) -> Tuple[float,float]:
    R = 6378137.0
    dLat = (dN_m / R) * (180.0 / math.pi)
    dLon = (dE_m / (R * math.cos(math.radians(lat0)))) * (180.0 / math.pi)
    return (lat0 + dLat), (lon0 + dLon)


def _latlon_to_xy_local(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """기준(lat0, lon0) 대비 ENU 평면 근사(m) 좌표."""
    R = 6378137.0
    dE = math.radians(lon - lon0) * R * math.cos(math.radians(lat0))
    dN = math.radians(lat - lat0) * R
    return dE, dN


def _pca_axes_from_points(pts_xy: np.ndarray):
    if pts_xy.shape[0] < 2:
        return np.array([1.0,0.0]), np.array([0.0,1.0])
    X = pts_xy - pts_xy.mean(axis=0, keepdims=True)
    C = np.cov(X.T)
    eigvals, eigvecs = np.linalg.eigh(C)
    major = eigvecs[:, int(np.argmax(eigvals))]
    minor = np.array([-major[1], major[0]], dtype=float)
    return major, minor


def filter_by_grid_adjacency(
    cands: List[Tuple[float,int,int,int,int,int,np.ndarray]],
    img_w: int, img_h: int,
    pair_required: bool = True,
    size_outlier_tol: float = 2.0,
    col_tol_mult: float = 0.7,
    row_near_min_mult: float = 0.3,
    row_near_max_mult: float = 2.2,
) -> List[int]:
    if not cands: return []
    boxes = np.array([[c[1], c[2], c[3], c[4]] for c in cands], dtype=np.float32)
    xs = (boxes[:,0] + boxes[:,2]) * 0.5
    ys = (boxes[:,1] + boxes[:,3]) * 0.5
    ws = (boxes[:,2] - boxes[:,0]); hs = (boxes[:,3] - boxes[:,1])
    w_med = float(np.median(ws)) if ws.size else 0.0
    h_med = float(np.median(hs)) if hs.size else 0.0
    if w_med <= 0 or h_med <= 0: return list(range(len(cands)))
    size_keep = (ws > (w_med / size_outlier_tol)) & (ws < (w_med * size_outlier_tol)) \
              & (hs > (h_med / size_outlier_tol)) & (hs < (h_med * size_outlier_tol))
    idx_pool = np.where(size_keep)[0].tolist()
    if not idx_pool: return []
    xy = np.stack([xs[idx_pool], ys[idx_pool]], axis=1)
    major, minor = _pca_axes_from_points(xy)
    centers = np.stack([xs, ys], axis=1)
    u = centers @ major; v = centers @ minor
    col_tol = float(h_med * col_tol_mult)
    row_near_min = float(w_med * row_near_min_mult); row_near_max = float(w_med * row_near_max_mult)
    keep_flags = np.zeros(len(cands), dtype=bool)
    for i in idx_pool:
        du = np.abs(u - u[i]); dv = np.abs(v - v[i])
        neighbor_mask = (dv <= col_tol) & (du >= row_near_min) & (du <= row_near_max)
        neighbor_mask[i] = False
        has_neighbor = bool(np.any(neighbor_mask))
        keep_flags[i] = (True if not pair_required else has_neighbor)
    return np.where(keep_flags)[0].tolist()


def load_region_polygons(geojson_path):
    if not geojson_path or not os.path.isfile(geojson_path):
        print(f"[Zones] GeoJSON 미발견: {geojson_path}"); return []
    with open(geojson_path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    feats = gj.get("features", [])
    zones = []
    for idx, ft in enumerate(feats):
        geom = ft.get("geometry") or {}
        gtype = (geom.get("type") or "").lower()
        coords = geom.get("coordinates")
        if not coords: continue
        props = ft.get("properties") or {}
        name = str(props.get("id") or props.get("zone_id") or props.get("name") or props.get("NAME") or props.get("title") or f"Zone_{idx+1}")
        if gtype == "polygon": mp = [coords]
        elif gtype == "multipolygon": mp = coords
        else: continue
        zones.append({"name": name, "coords": mp})
    print(f"[Zones] 로드 완료: {len(zones)}개 구역")
    return zones


def _ray_cast_point_in_poly(lon, lat, ring):
    x, y = lon, lat
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i+1) % n]
        if ((y1 > y) != (y2 > y)):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1 + 1e-18)
            if x_int >= x: inside = not inside
    return inside


def _point_in_multipolygon(lon, lat, multipoly):
    for poly in multipoly:
        outer = poly[0]; holes = poly[1:] if len(poly) > 1 else []
        if _ray_cast_point_in_poly(lon, lat, outer):
            for h in holes:
                if _ray_cast_point_in_poly(lon, lat, h): return False
            return True
    return False


def assign_zone_for_point(lon, lat, zones, unassigned="Unassigned"):
    if lon is None or lat is None: return unassigned
    for z in zones:
        if _point_in_multipolygon(lon, lat, z["coords"]):
            return z["name"]
    return unassigned


def _parse_seq_from_image_id(image_id: str) -> Optional[int]:
    m = re.search(r'_(\d{3,6})_(?:T|V)(?:_|$)', image_id)
    if m:
        try: return int(m.group(1))
        except: pass
    m2 = re.search(r'_(\d{3,6})(?:_|$)', image_id)
    if m2:
        try: return int(m2.group(1))
        except: pass
    m3 = re.search(r'(\d{3,6})(?:_(?:T|V)|$)', image_id)
    if m3:
        try: return int(m3.group(1))
        except: pass
    return None


def compute_rotation_classes_by_lonlat(image_gps: Dict[str, Tuple[Optional[float], Optional[float]]]) -> Dict[str, str]:
    seq_items = []
    for iid, (lat, lon) in image_gps.items():
        if lat is None or lon is None: continue
        seq = _parse_seq_from_image_id(iid)
        seq_items.append((iid, float(lat), float(lon), seq if seq is not None else float('inf')))
    if not seq_items: return {}
    seq_items.sort(key=lambda t: t[3])
    rot_by_id: Dict[str, str] = {}
    first_iid = seq_items[0][0]; rot_by_id[first_iid] = "rot-0"
    for k in range(1, len(seq_items)):
        _, prev_lat, prev_lon, _ = seq_items[k-1]
        curr_iid, curr_lat, curr_lon, _ = seq_items[k]
        dlon = curr_lon - prev_lon; dlat = curr_lat - prev_lat
        if abs(dlon) >= abs(dlat):
            rot = "rot-90" if dlon > 0 else ("rot--90" if dlon < 0 else "rot-0")
        else:
            rot = "rot-0"
        rot_by_id[curr_iid] = rot
    return rot_by_id


def _lonlat_to_xy_m(lon, lat, lon0, lat0):
    R = 6378137.0
    x = math.radians(lon - lon0) * R * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * R
    return x, y


def compute_rows_from_gps(image_gps: Dict[str, Tuple[Optional[float], Optional[float]]],
                          gap_multiplier: float = config.ROW_GAP_MULTIPLIER,
                          split_axis: str = config.ROW_SPLIT_AXIS) -> Dict[str, Dict[str, float]]:
    pts = []
    for iid, (lat, lon) in image_gps.items():
        if lat is None or lon is None: continue
        if not math.isfinite(float(lat)) or not math.isfinite(float(lon)): continue
        pts.append((iid, float(lat), float(lon)))
    if not pts: return {}
    if len(pts) == 1:
        return {pts[0][0]: {"row_id": 1, "xprime": 0.0, "yprime": 0.0}}
    lat0 = sum(p[1] for p in pts) / len(pts)
    lon0 = sum(p[2] for p in pts) / len(pts)
    XY = []
    for iid, la, lo in pts:
        x, y = _lonlat_to_xy_m(lo, la, lon0, lat0)
        XY.append((iid, x, y))
    xs = np.array([p[1] for p in XY], dtype=np.float64)
    ys = np.array([p[2] for p in XY], dtype=np.float64)
    X = np.stack([xs, ys], axis=0)
    C = np.cov(X)
    eigvals, eigvecs = np.linalg.eigh(C)
    major = eigvecs[:, np.argmax(eigvals)]
    minor = np.array([-major[1], major[0]])
    yprime = xs * major[0] + ys * major[1]
    xprime = xs * minor[0] + ys * minor[1]
    if split_axis not in ("xprime", "yprime"): split_axis = "yprime"
    arr = xprime if split_axis == "xprime" else yprime
    idx_sorted = np.argsort(arr); arr_sorted = arr[idx_sorted]
    gaps = np.diff(arr_sorted); gabs = np.abs(gaps) if gaps.size else np.array([0.0])
    med_gap = np.median(gabs) if gabs.size else 0.0
    if med_gap <= 0: med_gap = (np.mean(gabs) if gabs.size else 1.0)
    base = med_gap * (gap_multiplier if gap_multiplier > 0 else 1.8)
    thr = max(base, config.ROW_MIN_SEP_M)
    row_ids = np.zeros_like(arr, dtype=int)
    if arr.size > 0:
        row = 1; row_ids[idx_sorted[0]] = row
        for k in range(1, len(idx_sorted)):
            if (arr_sorted[k] - arr_sorted[k-1]) > thr: row += 1
            row_ids[idx_sorted[k]] = row
    out = {}
    for i, (iid, _, _) in enumerate(XY):
        out[iid] = {"row_id": int(row_ids[i]), "xprime": float(xprime[i]), "yprime": float(yprime[i])}
    return out


"""PV inspection: catalog."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
from sklearn.neighbors import NearestNeighbors
import os, re, json, time, math, shutil, subprocess, io
from torch import nn
import numpy as np
import pandas as pd
from .files import ensure_dir

def save_snapped_points_geojson(records: List[Dict], out_path: str):
    """
    records: {"image_id","module_id","final","delta_temp",
              "mod_lat","mod_lon","snap_mid","snap_applied"} ...
    """
    try:
        feats = []
        for r in records:
            lat = r.get("mod_lat"); lon = r.get("mod_lon")
            if lat is None or lon is None:
                continue
            props = {
                "image_id": r.get("image_id"),
                "module_id": r.get("module_id"),
                "final": r.get("final"),
                "delta_temp": r.get("delta_temp"),
                "snap_mid": r.get("snap_mid"),
                "snap_applied": bool(r.get("snap_applied")),
            }
            feats.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}
            })
        ensure_dir(os.path.dirname(out_path))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"type":"FeatureCollection","features":feats}, f, ensure_ascii=False)
        print(f"[SNAP] 저장: {out_path} (features={len(feats)})")
    except Exception as e:
        print(f"[SNAP] GeoJSON 저장 실패: {e}")


def _centroid_of_polygon_lonlat(coords):
    """
    coords: [ [lon,lat], ... ] (폐합 여부 무관)
    단순 평균(면적가중 아님) — 카탈로그 폴리곤이 정규 격자일 때 충분.
    """
    if not coords: return None, None
    xs = [float(c[0]) for c in coords]
    ys = [float(c[1]) for c in coords]
    return (sum(xs)/len(xs)), (sum(ys)/len(ys))


def _extract_feature_lonlat(ft) -> Tuple[Optional[float], Optional[float]]:
    g = ft.get("geometry") or {}
    gtype = (g.get("type") or "").lower()
    c = g.get("coordinates")
    if not c: return None, None
    if gtype == "point":
        lon, lat = c[0], c[1]
        return float(lon), float(lat)
    if gtype == "polygon":
        outer = c[0] if (isinstance(c[0], list) and c[0]) else []
        return _centroid_of_polygon_lonlat(outer)
    if gtype == "multipolygon":
        # 첫 폴리곤 외곽의 평균
        try:
            outer = c[0][0] if (isinstance(c[0], list) and c[0] and isinstance(c[0][0], list)) else []
            return _centroid_of_polygon_lonlat(outer)
        except Exception:
            return None, None
    return None, None


def load_module_catalog_json(json_path: str):
    """
    GeoJSON(FeatureCollection) 또는 일반 JSON 배열 지원.
    반환: dict {
        'lat0','lon0','items':[{'mid','lat','lon','zone'?},...],
        'XY': np.ndarray (N,2) — 로컬 ENU(m) 좌표,
        'nn': NearestNeighbors 모델
    }
    허용 포맷:
    - GeoJSON FeatureCollection: feature.properties.id 또는 name 또는 module_id 를 mid로 사용
    - 일반 JSON 배열: {'id':..., 'lat':..., 'lon':...} 필수
    """
    if (not json_path) or (not os.path.isfile(json_path)):
        print(f"[SNAP] 모듈 카탈로그 없음: {json_path}")
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[SNAP] JSON 로드 실패: {e}")
        return None

    items = []
    # GeoJSON
    if isinstance(data, dict) and (data.get("type","").lower() == "featurecollection"):
        feats = data.get("features") or []
        for i, ft in enumerate(feats):
            props = ft.get("properties") or {}
            mid = props.get("id") or props.get("name") or props.get("module_id") or f"m{i+1}"
            lon, lat = _extract_feature_lonlat(ft)
            if lon is None or lat is None: continue
            zone = props.get("zone")
            items.append({"mid": str(mid), "lat": float(lat), "lon": float(lon), "zone": zone})
    # 일반 배열
    elif isinstance(data, list):
        for i, r in enumerate(data):
            try:
                mid = r.get("id") or r.get("name") or r.get("module_id") or f"m{i+1}"
                lat = float(r["lat"]); lon = float(r["lon"])
                zone = r.get("zone")
                items.append({"mid": str(mid), "lat": lat, "lon": lon, "zone": zone})
            except Exception:
                continue
    else:
        print("[SNAP] 지원하지 않는 JSON 형식")
        return None

    if not items:
        print("[SNAP] 카탈로그 항목이 비어있음")
        return None

    lat0 = float(np.mean([it["lat"] for it in items]))
    lon0 = float(np.mean([it["lon"] for it in items]))

    def _to_xy(it):
        x = math.radians(it["lon"] - lon0) * 6378137.0 * math.cos(math.radians(lat0))
        y = math.radians(it["lat"] - lat0) * 6378137.0
        return [x, y]

    XY = np.array([_to_xy(it) for it in items], dtype=np.float64)
    nn = NearestNeighbors(n_neighbors=1, algorithm="kd_tree")
    nn.fit(XY)

    print(f"[SNAP] 모듈 카탈로그 로드: {len(items)}개 (ref lat0={lat0:.6f}, lon0={lon0:.6f})")
    return {"lat0": lat0, "lon0": lon0, "items": items, "XY": XY, "nn": nn}


def snap_point_to_catalog(lat: float, lon: float, catalog: dict, eps_m: float) -> Tuple[Optional[int], Optional[Dict]]:
    """
    입력(lat,lon)을 카탈로그로 스냅.
    반환: (idx, item) — idx는 catalog['items'] 인덱스, item은 {'mid','lat','lon','zone'?}
    eps_m 미만일 때만 스냅, 아니면 (None, None).
    """
    if (catalog is None) or (lat is None) or (lon is None):
        return None, None
    lat0 = catalog["lat0"]; lon0 = catalog["lon0"]
    x = math.radians(lon - lon0) * 6378137.0 * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * 6378137.0
    q = np.array([[x, y]], dtype=np.float64)
    dist, idx = catalog["nn"].kneighbors(q, n_neighbors=1, return_distance=True)
    d = float(dist[0][0]); j = int(idx[0][0])
    if d <= float(eps_m):
        return j, catalog["items"][j]
    return None, None


def save_snapped_geojson(df: pd.DataFrame, out_path: str):
    """
    df: df.merge 후 최종 테이블. 스냅된 행들만 GeoJSON Point로 저장.
    필요한 컬럼: snap_mid, snap_lat, snap_lon, image_id, module_id, final, delta_temp, crop_path
    """
    try:
        if df is None or df.empty or ("snap_mid" not in df.columns):
            ensure_dir(os.path.dirname(out_path))
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"type":"FeatureCollection","features":[]}, f, ensure_ascii=False)
            return

        msk = df["snap_mid"].notna() & df["snap_lat"].notna() & df["snap_lon"].notna()
        sub = df.loc[msk].copy()
        feats = []
        for _, r in sub.iterrows():
            props = {
                "image_id": r.get("image_id"),
                "module_id": int(r.get("module_id")) if pd.notna(r.get("module_id")) else None,
                "final": r.get("final"),
                "delta_temp": float(r.get("delta_temp")) if pd.notna(r.get("delta_temp")) else None,
                "snap_mid": r.get("snap_mid"),
                "crop_path": r.get("crop_path"),
            }
            lon = float(r.get("snap_lon")); lat = float(r.get("snap_lat"))
            feats.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [lon, lat]}
            })
        ensure_dir(os.path.dirname(out_path))
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"type":"FeatureCollection","features":feats}, f, ensure_ascii=False)
        print(f"[GeoJSON/SNAP] {out_path} (features={len(feats)})")
    except Exception as e:
        print(f"[GeoJSON/SNAP] 저장 실패: {e}")


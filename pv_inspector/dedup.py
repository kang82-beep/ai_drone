"""PV inspection: dedup."""
from __future__ import annotations
from . import config
from sklearn.cluster import DBSCAN
from typing import List, Dict, Tuple, Optional
import os, re, json, time, math, shutil, subprocess, io
import numpy as np
import pandas as pd
from .files import ensure_dir
from .geometry import _latlon_to_xy_local

def _severity_rank(label: str) -> int:
    # 낮을수록 우선: abnormal(0) < attention(1) < normal(2)
    order = {"abnormal": 0, "attention": 1, "normal": 2}
    return order.get(str(label), 9)


def _pick_representative(rows: list) -> dict:
    """군집(rows)에서 대표 1건 선택: 심각도 → 확률 → ΔT → score → 중심부 근접"""
    def _prob(row):
        lab = str(row.get("final"))
        if lab == "abnormal":  return float(row.get("prob_abnormal", -1))
        if lab == "attention": return float(row.get("prob_attention", -1))
        return float(row.get("prob_normal", -1))

    def _edge_margin(row):
        try:
            u = float(row.get("centroid_u", 0.0)); v = float(row.get("centroid_v", 0.0))
            W = float(row.get("img_w", 0.0)); H = float(row.get("img_h", 0.0))
            return min(u, v, max(0.0, W-u), max(0.0, H-v))
        except Exception:
            return 0.0

    rows_sorted = sorted(
        rows,
        key=lambda r: (
            _severity_rank(r.get("final")),
            -_prob(r),
            -(float(r.get("delta_temp")) if r.get("delta_temp") is not None else -1e9),
            -(float(r.get("score", -1.0))),
            -_edge_margin(r),
        )
    )
    return rows_sorted[0] if rows_sorted else {}


def dedup_modules_by_location(df: pd.DataFrame, eps_m: float, min_samples: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    위경도(DBSCAN) 기반 군집 → 대표 1건 선별
    반환: (df_with_cluster, df_dedup)
    - df_with_cluster: 원본 df에 cluster_id 부여본
    - df_dedup: 각 군집 대표만 모은 축약본
    """
    if df is None or df.empty:
        return df, pd.DataFrame()

    msk = df["mod_lat"].notna() & df["mod_lon"].notna()
    sub = df.loc[msk].copy()
    if sub.empty:
        return df.assign(cluster_id=pd.NA), pd.DataFrame()

    lat0 = float(sub["mod_lat"].mean()); lon0 = float(sub["mod_lon"].mean())
    xs, ys = [], []
    for _, r in sub.iterrows():
        x, y = _latlon_to_xy_local(float(r["mod_lat"]), float(r["mod_lon"]), lat0, lon0)  # 베이스에 이미 있음
        xs.append(x); ys.append(y)
    XY = np.stack([xs, ys], axis=1)

    db = DBSCAN(eps=float(eps_m), min_samples=int(min_samples))
    labels = db.fit_predict(XY)
    # DBSCAN noise (-1) represents separate observations, not one cluster.
    next_id = int(labels.max()) + 1
    for i in range(len(labels)):
        if labels[i] == -1:
            labels[i] = next_id
            next_id += 1
    sub["cluster_id"] = labels

    # 원본 df에 cluster_id 병합
    df = df.merge(sub[["crop_path", "cluster_id"]], on="crop_path", how="left")

    # 군집별 대표 선택
    rows = []
    for cid, g in df[df["cluster_id"].notna()].groupby("cluster_id"):
        best = _pick_representative(g.to_dict("records"))
        if best:
            rows.append(best)

    df_dedup = pd.DataFrame(rows)
    return df, df_dedup


def save_dedup_geojson(df_dedup: pd.DataFrame, out_path: str):
    """디듑된 모듈 포인트 GeoJSON(Point) 저장."""
    try:
        ensure_dir(os.path.dirname(out_path))
        feats = []
        for _, r in df_dedup.iterrows():
            lat = r.get("mod_lat"); lon = r.get("mod_lon")
            if pd.isna(lat) or pd.isna(lon):
                continue
            props = {
                "module_uid": r.get("module_uid"),
                "association_status": r.get("association_status"),
                "observation_count": int(r["observation_count"]) if pd.notna(r.get("observation_count")) else None,
                "label_disagreement": bool(r.get("label_disagreement", False)),
                "cluster_id": int(r.get("cluster_id")) if pd.notna(r.get("cluster_id")) else None,
                "final": r.get("final"),
                "prob_abnormal": float(r.get("prob_abnormal", np.nan)) if r.get("prob_abnormal") is not None else None,
                "prob_attention": float(r.get("prob_attention", np.nan)) if r.get("prob_attention") is not None else None,
                "prob_normal": float(r.get("prob_normal", np.nan)) if r.get("prob_normal") is not None else None,
                "delta_temp": float(r.get("delta_temp", np.nan)) if r.get("delta_temp") is not None else None,
                "image_id": r.get("image_id"),
                "module_id": r.get("module_id"),
                "zone": r.get("zone"),
                "crop_path": r.get("crop_path"),
            }
            feats.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}
            })
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False)
        print(f"[GeoJSON/DEDUP] {out_path} (features={len(feats)})")
    except Exception as e:
        print(f"[GeoJSON/DEDUP] 저장 실패: {e}")


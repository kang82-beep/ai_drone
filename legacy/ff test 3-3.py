# -*- coding: utf-8 -*-
"""
PV Auto Inspector v3 — rJPG 기반 분석 + rJPG 오버레이 + 모듈 GeoJSON 스냅 (One-file, 2025-10-16)
[Part 1/5]

업데이트 요약
- (유지) rJPG 원본으로 검출/크롭/분류, 오버레이는 rJPG 위에 생성
- (유지) RAW(float32) ΔT/핫스팟 분석 전용
- (유지) results.html 대시보드 + map.html 경량 지도
- (신규) 기준 모듈 GeoJSON 로드 → KDTree 최근접 스냅(module_id_ref) + (옵션) 좌표 교정/별도 GeoJSON 저장
- (유지) 디듑(DBSCAN) 기능은 그대로
"""

import os, re, json, time, math, shutil, subprocess, io
from glob import glob
from typing import List, Dict, Tuple, Optional
from collections import Counter

import numpy as np
import pandas as pd

import torch
from torch import nn
import torchvision
from torchvision import models, transforms, datasets
from torchvision.ops import nms

import cv2
from PIL import Image, ImageDraw, ImageFile, ExifTags
ImageFile.LOAD_TRUNCATED_IMAGES = True
import piexif
from tqdm import tqdm
from datetime import datetime

# exifread (fallback)
try:
    import exifread
    HAS_EXIFREAD = True
except Exception:
    HAS_EXIFREAD = False

# NEW: 디듑(중복 통합)용
from sklearn.cluster import DBSCAN

# =========================
# CONFIG
# =========================
INPUT_IMG_DIR    = r"C:\Users\USER\Desktop\3호기\DJI_202607290944_006_3호기"
OUTPUT_ROOT      = r"C:\drone\auto_results_v3_rawviz260729_3_2"
DJI_IRP_EXE      = r"C:\dji_thermal_sdk_v1.7_20241205\utility\bin\windows\release_x64\dji_irp.exe"

MASKRCNN_WEIGHTS = r"D:\py code\maskrcnn_trained_drone_shinan_0904.pth"
CLF_WEIGHTS      = r"D:\py code\classifier_b3_2025_1013.pth"
CLF_ARCH         = "efficientnet_b3"

SCORE_TH         = 0.60
MIN_AREA_PX      = 100
MIN_MODULE_W     = 60
MIN_MODULE_H     = 20
MIN_MODULE_AREA  = 5000

# MRK/NAV (원문 .MRK/.NAV 또는 CSV 지원)
MRK_CSV_PATH = r"C:\Users\USER\Desktop\3호기\DJI_202607290944_006_3호기\DJI_20251016092913_0002_D.MRK"
NAV_CSV_PATH = r"C:\Users\USER\Desktop\3호기\DJI_202607290944_006_3호기\DJI_20251016092913_0002_D.NAV"

# 오버레이 색/투명
BOX_ALPHA_ATTENTION = 90
BOX_ALPHA_ABNORMAL  = 110
OUTLINE_ALPHA       = 255
TEXT_FILL           = (255, 255, 255, 255)

CREATE_OVERLAY_WHEN_EMPTY = False

CROP_DIR         = os.path.join(OUTPUT_ROOT, "crops")
OVERLAY_DIR      = os.path.join(OUTPUT_ROOT, "overlays")
SORTED_BASE      = os.path.join(OUTPUT_ROOT, "sorted")
TEMP_RAW_DIR     = os.path.join(OUTPUT_ROOT, "temperature_raw")
TEMP_COLOR_DIR   = os.path.join(OUTPUT_ROOT, "temperature_color")  # (옵션) DJI 컬러 JPG 저장 폴더
TEMP_RGB_DIR     = os.path.join(OUTPUT_ROOT, "temperature_rgb")    # (옵션) 중간 .rgb

BATCH_SIZE       = 64
USE_TTA          = True
USE_KO_LABELS    = True
KO_LABEL_MAP     = {"normal": "정상", "attention": "주의", "abnormal": "이상"}

# 계층형 분류/임계값
USE_HIERARCHICAL_DECISION = True
TH_ABNORMAL               = 0.55  # 이상 우선 임계값
TH_ATT_WITHIN             = 0.50  # P(attention | non-abnormal)

# ===== 주의/오버레이/지도 마커 설정 =====
OVERLAY_ATTENTION            = True   # 주의도 항상 오버레이 생성/표시
MAP_INCLUDE_ATTENTION        = True   # 지도에서 주의 마커(주황) 사용 여부
ATTENTION_COUNT_ORANGE_TH    = 10     # 한 이미지 내 '주의' 개수 임계(주황 마커)

MAKE_MAP_HTML    = True
MAP_HTML_PATH    = os.path.join(OUTPUT_ROOT, "map.html")
MAP_GEOJSON_PATH = os.path.join(OUTPUT_ROOT, "map_points.geojson")

MASTER_CSV       = os.path.join(OUTPUT_ROOT, "master_results.csv")
ALERTS_CSV       = os.path.join(OUTPUT_ROOT, "alerts_topN.csv")
ALERTS_TOP_N     = 200

MOVE_CROPS       = True

# REJECT
SAVE_REJECTS         = True
REJECTS_DIR          = os.path.join(OUTPUT_ROOT, "rejected")
REJECTS_CSV          = os.path.join(OUTPUT_ROOT, "rejected_modules.csv")
REJECT_THUMB_MAX_W   = 480

# 입력 확장/탐색
SUPPORTED_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".rjpeg", ".rjpg"}
RECURSIVE_INPUT = False

# Zones (GeoJSON)
REGION_GEOJSON_PATH = r"D:\py code\zones shinan2 .geojson"
ZONE_UNASSIGNED_NAME = "Unassigned"

# Rows (행)
ROW_MIN_SEP_M      = 0.5
ROW_GAP_MULTIPLIER = 1.8
ROW_SPLIT_AXIS     = "yprime"

# RAW/Hotspot
RAW_INTERP        = "nearest"  # 업샘플 보간
ADD_DELTA_TO_TAG  = True

HS_ENABLE           = True
HS_DELTA_ABS_C      = 3.5
HS_DELTA_SIGMA_MULT = 2.2
HS_MIN_AREA_PX      = 40
HS_MIN_CORE_PX      = 8
HS_BORDER_MARGIN_PX = 6

DELTA_ATT_ENABLE = True
DELTA_ATT_TH     = 6.0   # °C

torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision('high')

# 카메라/촬영기하 (나디르)
ALT_AGL_M        = 30.0
FOCAL_35MM_EQ    = 52.0
FRAME_35MM_W_H   = (36.0, 24.0)

# 모듈 포인트 GeoJSON (프레임 단위 출력)
MODULE_POINTS_GEOJSON = os.path.join(OUTPUT_ROOT, "modules_points.geojson")

# ===== 분석/시각화 입력 선택 =====
ANALYZE_ON_INPUT_THERMAL = True   # True: rJPG 원본으로 검출/분류/크롭
OVERLAY_ON_INPUT_THERMAL = True   # True: rJPG 원본 위에 오버레이
EXTRACT_DJI_COLOR        = False  # True면 DJI 컬러 .rgb→.jpg도 생성(참고용)

DJI_VIZ_PALETTE     = "hot_iron"
DJI_MEASURE_DIST_M  = 30.0

# ===== 정사영상 GeoTIFF (대시보드에서 선택 사용) =====
USE_ORTHO_TIF  = True
ORTHO_TIF_PATH = r"C:\drone\shinan2\map\result.tif"

# ===== NEW: 디듑(중복 통합) 설정 =====
DEDUP_ENABLE               = True     # 디듑 수행 여부
DEDUP_EPS_M                = 0.8      # 같은 실제 모듈로 볼 최대 거리(m)
DEDUP_MIN_SAMPLES          = 1        # 군집 최소 포인트 수
MODULE_POINTS_GEOJSON_DEDUP= os.path.join(OUTPUT_ROOT, "modules_points_dedup.geojson")
MODULE_DEDUP_CSV           = os.path.join(OUTPUT_ROOT, "modules_dedup.csv")
MAP_SHOW_DEDUP_MODULES     = True     # results.html / map.html에 디듑 레이어 표시
MODULE_POINTS_DEDUP_GEOJSON = os.path.join(OUTPUT_ROOT, "modules_points_dedup.geojson")

# ===== NEW: 기준 모듈 GeoJSON 스냅 옵션 =====
MODULE_GEOJSON_PATH   = r"D:\py code\test88.geojson"   # 기준 모듈 GeoJSON (Point/Polygon/MultiPolygon)
MODULE_ID_KEYS        = ["module_id", "id", "name", "label"]  # properties에서 ID 후보 키
MODULE_SNAP_MAX_M     = 100        # 스냅 허용 최대 거리(m)_1.0
MODULE_SNAP_OVERRIDE  = True       # 스냅되면 좌표를 스냅 위치로 대체(교정)
SAVE_SNAPPED_POINTS_GEOJSON = True
SNAPPED_POINTS_GEOJSON      = os.path.join(OUTPUT_ROOT, "modules_points_snapped.geojson")
MODULE_ID_KEYS        = ["fid", "module_id", "id", "name", "label"]  # ← fid를 가장 먼저

# =========================
# 유틸
# =========================
def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def ensure_unique_path(dst_path: str) -> str:
    if not os.path.exists(dst_path):
        return dst_path
    root, ext = os.path.splitext(dst_path)
    k = 1
    while True:
        cand = f"{root}_{k}{ext}"
        if not os.path.exists(cand):
            return cand
        k += 1

def safe_paste_exif(src_img_path: str, dst_img_path: str):
    try:
        base = Image.open(src_img_path)
        if "exif" in base.info:
            piexif.insert(base.info["exif"], dst_img_path)
    except Exception as ex:
        print(f"[경고] EXIF 복사 실패: {dst_img_path} -> {ex}")

def _norm_ext(p: str) -> str:
    return os.path.splitext(p)[1].lower().replace("-", "")

def list_input_images(input_dir: str) -> List[str]:
    files = []
    if RECURSIVE_INPUT:
        for root, _, fnames in os.walk(input_dir):
            for f in fnames:
                if f.startswith("._"): continue
                if _norm_ext(f) in SUPPORTED_EXTS:
                    files.append(os.path.join(root, f))
    else:
        names = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        for f in names:
            if f.startswith("._"): continue
            if _norm_ext(f) in SUPPORTED_EXTS:
                files.append(os.path.join(input_dir, f))
        try:
            ext_counter = Counter(_norm_ext(x) for x in names)
            print("[입력 확장자 요약]", dict(ext_counter.most_common()))
        except Exception:
            pass
    return sorted(files)

EXIF_DT_KEYS = ["DateTimeOriginal", "DateTime", "CreateDate"]

def _parse_exif_datetime_str(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s.strip(), "%Y:%m:%d %H:%M:%S")
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(s.strip(), fmt)
            except Exception:
                pass
    return None

def _extract_datetime_from_exif(img_path: str) -> Optional[datetime]:
    try:
        with Image.open(img_path) as im:
            exif = getattr(im, "_getexif", lambda: None)() or {}
            tag_map = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
            for k in EXIF_DT_KEYS:
                v = tag_map.get(k)
                if isinstance(v, bytes): v = v.decode(errors="ignore")
                if isinstance(v, str):
                    dt = _parse_exif_datetime_str(v)
                    if dt: return dt
    except Exception:
        pass
    if HAS_EXIFREAD:
        try:
            with open(img_path, "rb") as f:
                tags = exifread.process_file(f, details=False)
            for k in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
                v = tags.get(k)
                if v:
                    dt = _parse_exif_datetime_str(str(v))
                    if dt: return dt
        except Exception:
            pass
    return None

def guess_shoot_date(all_image_paths: List[str], input_dir: str) -> Optional[str]:
    dates = []
    sample = all_image_paths[:100]
    for p in sample:
        dt = _extract_datetime_from_exif(p)
        if dt:
            dates.append(dt.date().isoformat())
    if dates:
        most = Counter(dates).most_common(1)[0][0]
        return most
    m = re.search(r"(20\d{6})", os.path.basename(input_dir))
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d").date().isoformat()
            return d
        except Exception:
            pass
    return None

# =========================
# 파일명 파서 (T/V + key5)
# =========================
def parse_tv_and_key5(path: str) -> Tuple[str, Optional[str], Optional[str]]:
    base = os.path.splitext(os.path.basename(path))[0]
    if base and base[-1].upper() in ("T","V"):
        tv = base[-1].upper()
        key5 = base[-6:-1] if len(base) >= 6 else None
        return base, tv, key5
    m = re.search(r"([A-Za-z0-9]{5})([tTvV])$", base)
    if m:
        return base, m.group(2).upper(), m.group(1)
    return base, None, None

# =========================
# GPS/EXIF + MRK/NAV
# =========================
def _dms_to_dd(dms, ref) -> Optional[float]:
    try:
        deg = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1]
        seconds = dms[2][0] / dms[2][1]
        dd = deg + minutes/60.0 + seconds/3600.0
        if ref in ["S", "W"]:
            dd = -dd
        return dd
    except Exception:
        return None

def extract_gps_from_exif(path: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        img = Image.open(path)
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if ExifTags.TAGS.get(tag) == 'GPSInfo':
                    gps_info = val
                    lat = _dms_to_dd(gps_info.get(2), gps_info.get(1))
                    lon = _dms_to_dd(gps_info.get(4), gps_info.get(3))
                    if lat is not None and lon is not None:
                        return lat, lon
    except Exception:
        pass
    if HAS_EXIFREAD:
        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
            def _to_deg(value):
                d, m, s = value.values
                return float(d.num)/d.den + float(m.num)/(m.den*60) + float(s.num)/(s.den*3600)
            lat = tags.get('GPS GPSLatitude')
            lat_ref = tags.get('GPS GPSLatitudeRef')
            lon = tags.get('GPS GPSLongitude')
            lon_ref = tags.get('GPS GPSLongitudeRef')
            if lat and lat_ref and lon and lon_ref:
                la = _to_deg(lat); lo = _to_deg(lon)
                if str(lat_ref.values[0]).upper() != 'N': la = -la
                if str(lon_ref.values[0]).upper() != 'E': lo = -lo
                return la, lo
        except Exception:
            pass
    return None, None

def _heading_from_exif(path: str) -> Optional[float]:
    try:
        img = Image.open(path)
        exif = img._getexif() or {}
        for tag, val in exif.items():
            if ExifTags.TAGS.get(tag) == 'GPSInfo':
                gps = val
                direction = gps.get(16, None)  # GPSImgDirection
                if direction:
                    if isinstance(direction, tuple) and len(direction) == 2:
                        return float(direction[0]) / float(direction[1])
                    return float(direction)
    except Exception:
        pass
    if HAS_EXIFREAD:
        try:
            with open(path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
            d = tags.get('GPS GPSImgDirection')
            if d:
                s = str(d)
                if '/' in s:
                    a, b = s.split('/', 1)
                    return float(a) / float(b)
                return float(s)
        except Exception:
            pass
    return None

def _heading_guess_from_neighbors(prev_lat, prev_lon, curr_lat, curr_lon) -> Optional[float]:
    if None in (prev_lat, prev_lon, curr_lat, curr_lon): return None
    la0 = (prev_lat + curr_lat) * 0.5
    xE = math.radians(curr_lon - prev_lon) * 6378137.0 * math.cos(math.radians(la0))
    yN = math.radians(curr_lat - prev_lat) * 6378137.0
    if abs(xE) < 1e-6 and abs(yN) < 1e-6: return None
    ang = math.degrees(math.atan2(xE, yN))  # 북=0°, 동=+90°
    if ang < 0: ang += 360.0
    return ang

# =========================
# MRK/NAV 다형 로더 (CSV + 일반 텍스트)
# =========================
def _read_text_any(path: str) -> Optional[str]:
    if (not path) or (not os.path.isfile(path)):
        return None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"):
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                return f.read()
        except Exception:
            continue
    try:
        with open(path, "rb") as f:
            b = f.read()
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return None

def _safe_float(x):
    try: return float(x)
    except Exception: return None

def _is_lat_lon_pair(a: float, b: float) -> bool:
    if a is None or b is None: return False
    return (-90.0 <= a <= 90.0) and (-180.0 <= b <= 180.0)

def _extract_filename_candidates(s: str) -> List[str]:
    pat = re.compile(r'(?:DJI_\d{14}_\d{4}_[TV]|DJI_\d{8,}_[TV]|[A-Za-z0-9_\-]+_[TV])\.(?:RJPEG|RJPG|JPG|JPEG|TIF|TIFF)', re.IGNORECASE)
    return pat.findall(s)

def _extract_heading_candidates(s: str) -> List[float]:
    vals = []
    for key in ("Heading", "heading", "Yaw", "yaw", "Course", "course", "GPSImgDirection"):
        m = re.search(rf'{key}\s*[:=]\s*(-?\d+(?:\.\d+)?)', s)
        if m:
            v = _safe_float(m.group(1))
            if v is not None:
                vals.append(v)
    if not vals:
        nums = re.findall(r'(-?\d+(?:\.\d+)?)', s)
        for n in nums:
            v = _safe_float(n)
            if v is not None and -360.0 <= v <= 360.0:
                vals.append(v)
    return vals

def _extract_lat_lon_from_line(s: str) -> Tuple[Optional[float], Optional[float]]:
    mlat = re.search(r'(?:lat|latitude)\s*[:=]\s*(-?\d+(?:\.\d+)?)', s, re.IGNORECASE)
    mlon = re.search(r'(?:lon|lng|longitude)\s*[:=]\s*(-?\d+(?:\.\d+)?)', s, re.IGNORECASE)
    if mlat and mlon:
        la = _safe_float(mlat.group(1)); lo = _safe_float(mlon.group(1))
        if _is_lat_lon_pair(la, lo): return la, lo
    nums = re.findall(r'(-?\d+(?:\.\d+)?)', s)
    for i in range(len(nums)-1):
        la = _safe_float(nums[i]); lo = _safe_float(nums[i+1])
        if _is_lat_lon_pair(la, lo):
            return la, lo
    return None, None

def _parse_table_from_text(txt: str) -> Dict[str, Dict[str, Optional[float]]]:
    table: Dict[str, Dict[str, Optional[float]]] = {}
    if not txt: return table
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    header = lines[0].lower() if lines else ""
    looks_csv = ("," in header) and any(k in header for k in ("lat","lon","latitude","longitude","heading","yaw","filename","name","file"))
    if looks_csv:
        try:
            df = pd.read_csv(io.StringIO(txt))
            def _pick(df, cands):
                for c in cands:
                    if c in df.columns: return c
                return None
            c_name = _pick(df, ["FileName","filename","name","Name","file","File"])
            c_lat  = _pick(df, ["Latitude","latitude","lat","Lat"])
            c_lon  = _pick(df, ["Longitude","longitude","lon","Lng","Long"])
            c_head = _pick(df, ["Heading","heading","Yaw","yaw","Course","course","GPSImgDirection"])
            for _, r in df.iterrows():
                key = None
                if c_name and pd.notna(r[c_name]):
                    key = str(r[c_name])
                la = _safe_float(r[c_lat]) if c_lat else None
                lo = _safe_float(r[c_lon]) if c_lon else None
                hd = _safe_float(r[c_head]) if c_head else None
                if not key:
                    continue
                if key not in table:
                    table[key] = {"lat": None, "lon": None, "heading": None}
                if la is not None and table[key]["lat"] is None: table[key]["lat"] = la
                if lo is not None and table[key]["lon"] is None: table[key]["lon"] = lo
                if hd is not None and table[key]["heading"] is None: table[key]["heading"] = hd
            if table:
                return table
        except Exception:
            pass
    for ln in lines:
        fns = _extract_filename_candidates(ln)
        if not fns:
            m2 = re.search(r'(?:Name|FileName|File)\s*[:=]\s*(\S+\.(?:JPG|JPEG|RJPEG|RJPG|TIF|TIFF))', ln, re.IGNORECASE)
            if m2: fns = [m2.group(1)]
        if not fns:
            continue
        la, lo = _extract_lat_lon_from_line(ln)
        heads = _extract_heading_candidates(ln)
        hd = heads[0] if heads else None
        for key in fns:
            if key not in table:
                table[key] = {"lat": None, "lon": None, "heading": None}
            if table[key]["lat"] is None and la is not None: table[key]["lat"] = la
            if table[key]["lon"] is None and lo is not None: table[key]["lon"] = lo
            if table[key]["heading"] is None and hd is not None: table[key]["heading"] = hd
    return table

def load_mrk_nav(mrk_path: str, nav_path: str) -> Dict[str, Dict[str, Optional[float]]]:
    table: Dict[str, Dict[str, Optional[float]]] = {}
    def _merge_in(newtab: Dict[str, Dict[str, Optional[float]]]):
        for k, rec in newtab.items():
            if k not in table:
                table[k] = {"lat": None, "lon": None, "heading": None}
            if rec.get("lat")     is not None and table[k]["lat"]     is None: table[k]["lat"]     = rec["lat"]
            if rec.get("lon")     is not None and table[k]["lon"]     is None: table[k]["lon"]     = rec["lon"]
            if rec.get("heading") is not None and table[k]["heading"] is None: table[k]["heading"] = rec["heading"]
            stem, _ = os.path.splitext(k)
            if stem and (stem not in table):
                table[stem] = table[k]
    for path in (mrk_path, nav_path):
        if not path or not os.path.isfile(path):
            continue
        txt = _read_text_any(path)
        if not txt:
            continue
        parsed = _parse_table_from_text(txt)
        _merge_in(parsed)
    return table

def mrk_nav_lookup_for_image(image_path: str, table: dict):
    base = os.path.basename(image_path)
    stem, _ = os.path.splitext(base)
    for key in (base, stem):
        if key in table:
            rec = table[key]
            return rec.get("lat"), rec.get("lon"), rec.get("heading")
    return None, None, None

# =========================
# FOV/GSD/ENU→WGS84
# =========================
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

# =========================
# 모듈 GeoJSON 스냅 유틸
# =========================
def _geojson_to_module_points(geojson_path: str):
    """기준 모듈 GeoJSON을 (lon,lat) 포인트로 변환 + module_id 후보 추출."""
    if not geojson_path or not os.path.isfile(geojson_path):
        print(f"[MODULES] GeoJSON 미발견: {geojson_path}")
        return [], []
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            gj = json.load(f)
        feats = gj.get("features", [])
    except Exception as e:
        print(f"[MODULES] GeoJSON 로드 실패: {e}")
        return [], []

    pts, mids = [], []
    for idx, ft in enumerate(feats):   # ★ enumerate로 인덱스 사용
        geom = ft.get("geometry") or {}
        gtype = (geom.get("type") or "").lower()
        props = ft.get("properties") or {}
        mid = None

        # ① MODULE_ID_KEYS 순서대로 ID 찾기
        for k in MODULE_ID_KEYS:
            if k in props and props[k] not in (None, ""):
                mid = str(props[k])
                break

        # ② ★ fallback (properties가 비거나 id 누락 시 임시 ID 부여)
        if mid is None:
            mid = f"feat_{idx+1}"   # ← 예: feat_1, feat_2, ...

        # ③ 좌표 추출
        if gtype == "point":
            c = geom.get("coordinates") or []
            if len(c) >= 2:
                pts.append((float(c[0]), float(c[1])))
                mids.append(mid)

        elif gtype in ("polygon", "multipolygon"):
            def _ring_center(ring):
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                return float(np.mean(xs)), float(np.mean(ys))

            if gtype == "polygon":
                rings = geom.get("coordinates") or []
                if rings and rings[0] and len(rings[0]) >= 3:
                    lon, lat = _ring_center(rings[0])
                    pts.append((lon, lat))
                    mids.append(mid)

            else:  # multipolygon
                mps = geom.get("coordinates") or []
                if mps and mps[0] and mps[0][0] and len(mps[0][0]) >= 3:
                    lon, lat = _ring_center(mps[0][0])
                    pts.append((lon, lat))
                    mids.append(mid)

    print(f"[MODULES] 기준 모듈 포인트: {len(pts)}개")
    return pts, mids

def _build_module_kdtree(module_pts: list):
    """(lon,lat) 리스트로 KDTree 구축 (지역 평면 좌표로)."""
    if not module_pts:
        return None, None, None, None
    lons = np.array([p[0] for p in module_pts]); lats = np.array([p[1] for p in module_pts])
    lat0, lon0 = float(np.mean(lats)), float(np.mean(lons))
    XY = np.array([_latlon_to_xy_local(lat, lon, lat0, lon0) for lon, lat in zip(lons, lats)], dtype=float)
    from sklearn.neighbors import KDTree  # 의존성 존재
    tree = KDTree(XY)
    return tree, XY, lat0, lon0

def snap_to_module(lon: float, lat: float, tree, lat0: float, lon0: float, mids: list, snap_max_m: float):
    """(lon,lat) → KDTree 최근접 모듈 스냅 (거리 ≤ snap_max_m) → (module_id, s_lon, s_lat)"""
    if (lon is None) or (lat is None) or (tree is None):
        return None, None, None
    x, y = _latlon_to_xy_local(lat, lon, lat0, lon0)
    dist, idx = tree.query(np.array([[x, y]]), k=1, return_distance=True)
    d = float(dist[0, 0]); j = int(idx[0, 0])
    if d <= snap_max_m:
        mid = mids[j] if (mids and j < len(mids)) else None
        mod_x, mod_y = tree.data[j, 0], tree.data[j, 1]
        s_lat, s_lon = _enu_offset_to_latlon(lat0, lon0, mod_x, mod_y)
        return mid, s_lon, s_lat
    return None, None, None

# [Part 2/5] — RAW/Hotspot, DJI 추출, 모델 빌드, 오버레이, Grid/Row/Zone/Rotate

# =========================
# RAW/Hotspot (DJI 전용 RAW만 사용)
# =========================
def _load_raw_float32_auto(raw_path: str):
    try:
        with open(raw_path, "rb") as f:
            data = f.read()
        if len(data) % 4 != 0:
            return None
        arr = np.frombuffer(data, dtype=np.float32)
        npix = arr.size
        for (w,h) in [(640,512),(512,640),(1280,1024),(1024,1280)]:
            if w*h == npix:
                return arr.reshape(h, w)
        side = int(np.sqrt(npix))
        if side*side == npix:
            return arr.reshape(side, side)
    except:
        pass
    return None

def _resize_raw_to_size(raw_img: np.ndarray, target_w: int, target_h: int):
    if raw_img is None: return None
    h, w = raw_img.shape[:2]
    if (w, h) == (target_w, target_h): return raw_img
    interp = cv2.INTER_NEAREST if RAW_INTERP == "nearest" else cv2.INTER_LINEAR
    return cv2.resize(raw_img, (target_w, target_h), interpolation=interp)

def _compute_temp_stats_in_bbox(raw_img_up: np.ndarray, bbox):
    if raw_img_up is None: return None, None, None
    H, W = raw_img_up.shape[:2]
    x1,y1,x2,y2 = map(int, bbox)
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(W-1, x2); y2 = min(H-1, y2)
    if x2 <= x1 or y2 <= y1: return None, None, None
    roi = raw_img_up[y1:y2, x1:x2].astype(np.float32)
    if roi.size == 0 or not np.isfinite(roi).any(): return None, None, None
    mean_t = float(np.nanmean(roi))
    max_t  = float(np.nanmax(roi))
    delta  = float(max_t - mean_t)
    return mean_t, max_t, delta

def _analyze_hotspot_in_bbox(raw_img_up: np.ndarray, bbox) -> bool:
    if raw_img_up is None: return False
    H, W = raw_img_up.shape[:2]
    x1,y1,x2,y2 = map(int, bbox)
    x1 = max(0, x1+HS_BORDER_MARGIN_PX); y1 = max(0, y1+HS_BORDER_MARGIN_PX)
    x2 = min(W-1, x2-HS_BORDER_MARGIN_PX); y2 = min(H-1, y2-HS_BORDER_MARGIN_PX)
    if x2 <= x1 or y2 <= y1: return False
    roi = raw_img_up[y1:y2, x1:x2].astype(np.float32)
    if roi.size < 16: return False
    Tbg  = float(np.median(roi))
    sig  = float(np.std(roi))
    Tthr = Tbg + max(HS_DELTA_ABS_C, HS_DELTA_SIGMA_MULT * max(1e-6, sig))
    Tcore = Tthr + 1.5
    inner = roi
    rim = HS_BORDER_MARGIN_PX
    if roi.shape[0] > 2*rim and roi.shape[1] > 2*rim:
        inner = roi[rim:-rim, rim:-rim]
    m_main = (inner > Tthr)
    m_core = (inner > Tcore)
    try:
        n, lab = cv2.connectedComponents(m_main.astype(np.uint8), connectivity=8)
        largest = max((lab == L).sum() for L in range(1, n)) if n > 1 else 0
        area_ok = largest >= HS_MIN_AREA_PX
    except Exception:
        area_ok = int(m_main.sum()) >= HS_MIN_AREA_PX
    core_ok = int(m_core.sum()) >= HS_MIN_CORE_PX
    return bool(area_ok and core_ok)

# =========================
# DJI: RAW (필수) + Color(.rgb→.jpg, 옵션)
# =========================
def extract_temp_and_color_dji(
    rjpeg_path: str,
    output_raw_path: str,
    output_color_path: str,   # need_color=True일 때만 사용
    exe_path: str,
    distance_m: float = 30.0,
    palette: str = "hot_iron",
    max_wait: int = 20,
    need_color: bool = False
) -> bool:
    """
    - 항상 RAW(float32) 추출
    - need_color=False면 컬러 변환은 생략
    - True 반환: RAW 생성 성공(그리고 need_color=True면 컬러까지 성공)
    """
    try:
        ensure_dir(os.path.dirname(output_raw_path))
        # 1) RAW(float32)
        subprocess.run([
            exe_path, "--action", "measure",
            "--source", rjpeg_path,
            "--output", output_raw_path,
            "--measurefmt", "float32",
            "--distance", str(float(distance_m))
        ], check=True)

        if need_color:
            ensure_dir(os.path.dirname(output_color_path))
            ensure_dir(TEMP_RGB_DIR)
            with Image.open(rjpeg_path) as im:
                W_pre, H_pre = im.size  # 예: 1280x1024

            root, _ = os.path.splitext(output_color_path)
            rgb_name = os.path.basename(root) + ".rgb"
            output_rgb_path = os.path.join(TEMP_RGB_DIR, rgb_name)

            # 2) 컬러(.rgb)
            subprocess.run([
                exe_path, "--action", "process",
                "--source", rjpeg_path,
                "--output", output_rgb_path,
                "--palette", str(palette)
            ], check=True)

            # 파일 대기
            t0 = time.time()
            while (not os.path.isfile(output_raw_path) or not os.path.isfile(output_rgb_path)) and (time.time() - t0 < max_wait):
                time.sleep(0.2)

            if not os.path.isfile(output_raw_path):
                return False
            if not os.path.isfile(output_rgb_path):
                # RAW만 생성되면 True로 간주(컬러는 옵션)
                return True

            size_bytes = os.path.getsize(output_rgb_path)
            if size_bytes % 3 != 0:
                print(f"[경고] RGB 바이트수가 3의 배수가 아님: {size_bytes}")
                return True  # RAW 성공이면 True

            npix = size_bytes // 3
            common_sizes = [(640,512), (512,640), (1280,1024), (1024,1280), (800,600), (600,800)]
            wh = None
            for w,h in common_sizes:
                if w*h == npix:
                    wh = (w,h); break
            if wh is None:
                with Image.open(rjpeg_path) as im:
                    W_pre, H_pre = im.size
                candidates = []
                for ratio in [5/4, 4/3, 16/9, 1.0]:
                    w_est = int(round((npix * ratio) ** 0.5))
                    if w_est <= 0: 
                        continue
                    h_est = npix // w_est
                    if w_est * h_est == npix:
                        candidates.append((w_est, h_est))
                    h_est2 = int(round((npix / ratio) ** 0.5))
                    if h_est2 > 0:
                        w_est2 = npix // h_est2
                        if w_est2 * h_est2 == npix:
                            candidates.append((w_est2, h_est2))
                if candidates:
                    wh = min(candidates, key=lambda t: abs((t[0]/max(1,t[1])) - (W_pre/max(1,H_pre))))
            if wh is None:
                print(f"[경고] RGB 크기에서 해상도 추론 실패: npix={npix}")
                return True  # RAW 성공이면 True

            w_rgb, h_rgb = wh
            with open(output_rgb_path, "rb") as f:
                buf = f.read()
            try:
                arr = np.frombuffer(buf, dtype=np.uint8).reshape(h_rgb, w_rgb, 3)  # SDK는 RGB
            except Exception as e:
                print(f"[경고] RGB reshape 실패: {(h_rgb, w_rgb)} -> {e}")
                return True  # RAW 성공이면 True

            # 원본 크기에 맞춰 리샘플(참고용)
            with Image.open(rjpeg_path) as im:
                W_pre, H_pre = im.size
            if (w_rgb, h_rgb) != (W_pre, H_pre):
                arr_up = cv2.resize(arr, (W_pre, H_pre), interpolation=cv2.INTER_LINEAR)
                bgr = cv2.cvtColor(arr_up, cv2.COLOR_RGB2BGR)
            else:
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            cv2.imwrite(output_color_path, bgr)

        else:
            # need_color=False: RAW만 확인
            t0 = time.time()
            while (not os.path.isfile(output_raw_path)) and (time.time() - t0 < max_wait):
                time.sleep(0.2)

        return os.path.isfile(output_raw_path)

    except Exception as e:
        print(f"[온도 RAW/컬러 추출 실패] {rjpeg_path} -> {e}")
        return False

# =========================
# Mask R-CNN & Classifier
# =========================
def get_maskrcnn_model(num_classes=2):
    model = torchvision.models.detection.maskrcnn_resnet50_fpn(weights=None)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    hidden_layer = 256
    model.roi_heads.mask_predictor = torchvision.models.detection.mask_rcnn.MaskRCNNPredictor(
        in_features_mask, hidden_layer, num_classes
    )
    return model

def build_effb3(num_classes: int):
    m = models.efficientnet_b3(weights=None)
    in_f = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_f, num_classes)
    return m

def make_transforms(img_size: int, use_gray: bool):
    base = []
    if use_gray:
        base.append(transforms.Grayscale(num_output_channels=3))
        mean, std = [0.5]*3, [0.5]*3
    else:
        mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    tf = transforms.Compose([
        transforms.Resize(int(img_size * 1.05)),
        transforms.CenterCrop(img_size),
        *base,
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    tf_flip = transforms.Compose([
        transforms.Resize(int(img_size * 1.05)),
        transforms.CenterCrop(img_size),
        transforms.RandomHorizontalFlip(p=1.0),
        *base,
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    return tf, tf_flip

# =========================
# Overlay Drawing
# =========================
def draw_overlay(base_img_path: str, overlays: List[Dict], save_path: str):
    im = Image.open(base_img_path).convert('RGB')
    draw = ImageDraw.Draw(im, 'RGBA')

    def poly(points, outline, fill):
        draw.polygon(points, outline=outline, fill=fill)

    def rect(b, outline, fill):
        x1, y1, x2, y2 = b
        draw.rectangle([x1, y1, x2, y2], outline=outline, fill=fill, width=3)

    for it in overlays:
        label = it.get('label')
        if label == 'abnormal':
            color = (255, 0, 0, BOX_ALPHA_ABNORMAL)
            outline = (255, 0, 0, OUTLINE_ALPHA)
        else:
            color = (255, 165, 0, BOX_ALPHA_ATTENTION)
            outline = (255, 165, 0, OUTLINE_ALPHA)

        if it.get('quad'):
            pts = [(float(x), float(y)) for x, y in it['quad']]
            poly(pts, outline=outline, fill=color)
            tx, ty = pts[0]
        elif it.get('bbox'):
            rect(it['bbox'], outline=outline, fill=color)
            tx, ty = it['bbox'][0], it['bbox'][1]
        else:
            continue

        tag = it.get('tag', '')
        if tag:
            try:
                tw = draw.textlength(tag)
            except Exception:
                tw = 8 * len(tag)
            th = 12
            draw.rectangle([tx+1, ty+1, tx+6+tw, ty+6+th], fill=(0,0,0,140))
            draw.text((tx + 3, ty + 3), tag, fill=TEXT_FILL)

    ensure_dir(os.path.dirname(save_path))
    im.save(save_path, 'JPEG', quality=92)

# =========================
# Grid/Row/Zone/Rotate
# =========================
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
                          gap_multiplier: float = ROW_GAP_MULTIPLIER,
                          split_axis: str = ROW_SPLIT_AXIS) -> Dict[str, Dict[str, float]]:
    pts = []
    for iid, (lat, lon) in image_gps.items():
        if lat is None or lon is None: continue
        pts.append((iid, float(lat), float(lon)))
    if not pts: return {}
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
    thr = max(base, ROW_MIN_SEP_M)
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

# =========================
# (옵션) 스냅된 포인트 GeoJSON 저장
# =========================
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

# [Part 3/5] — 분류/정렬, 지도/대시보드(스냅 레이어 옵션), 모듈 JSON/KDTree 스냅 준비

# =========================
# (NEW CONFIG) 모듈 카탈로그 기반 스냅
# =========================
# ※ 베이스 상단 CONFIG 근처에 추가해 주세요.
MODULE_CATALOG_JSON       = r"D:\py code\modules_catalog.json"  # GeoJSON 또는 JSON 지원(아래 로더 설명)
SNAP_ENABLE               = True     # 모듈 카탈로그에 스냅 사용 여부
SNAP_EPS_M                = 1.2      # 스냅 허용 반경(미터). 가까운 모듈만 스냅
SNAP_SAVE_GEOJSON         = os.path.join(OUTPUT_ROOT, "modules_points_snapped.geojson")
SNAP_SAVE_CSV             = os.path.join(OUTPUT_ROOT, "modules_snapped.csv")
MAP_SHOW_SNAP_MODULES     = True     # results.html / map.html에 스냅 포인트 레이어 표시

# =========================
# 분류 + 정렬 (베이스 유지)
# =========================
def classify_and_sort(
    clf: nn.Module, class_order: List[str], crop_paths: List[str], out_base: str,
    tf, tf_flip, device, move_files=False,
    delta_lookup: Optional[Dict[str,float]] = None, hotspot_lookup: Optional[Dict[str,bool]] = None
) -> pd.DataFrame:
    ensure_dir(out_base)
    out_name = (lambda en: KO_LABEL_MAP.get(en, en)) if USE_KO_LABELS else (lambda en: en)
    normal_top = os.path.join(out_base, out_name("normal")); abnormal_top = os.path.join(out_base, out_name("abnormal"))
    ensure_dir(normal_top); ensure_dir(abnormal_top)
    normal_sub_normal = os.path.join(normal_top, out_name("normal")); ensure_dir(normal_sub_normal)
    normal_sub_attention = os.path.join(normal_top, out_name("attention")); ensure_dir(normal_sub_attention)

    rows = []
    loader = datasets.folder.default_loader
    def to_tensor_list(pil_list, transform):
        xs = [transform(im) for im in pil_list]
        return torch.stack(xs, dim=0)
    i_abn = class_order.index("abnormal"); i_att = class_order.index("attention"); i_nor = class_order.index("normal")

    with torch.no_grad():
        for i in tqdm(range(0, len(crop_paths), BATCH_SIZE), desc="[분류]"):
            batch_paths = crop_paths[i:i+BATCH_SIZE]
            batch_imgs = []
            for p in batch_paths:
                try: batch_imgs.append(loader(p))
                except Exception: batch_imgs.append(Image.new("RGB", (64,64), (255,255,255)))
            x = to_tensor_list(batch_imgs, tf).to(device)
            logits = clf(x); probs = torch.softmax(logits, dim=1)
            if USE_TTA:
                x2 = to_tensor_list(batch_imgs, tf_flip).to(device)
                probs = (probs + torch.softmax(clf(x2), dim=1)) / 2.0
            probs = probs.cpu().numpy()
            for p, pr in zip(batch_paths, probs):
                p_abn = float(pr[i_abn]); p_att = float(pr[i_att]); p_nor = float(pr[i_nor])
                if USE_HIERARCHICAL_DECISION:
                    if p_abn >= TH_ABNORMAL:
                        final_name = "abnormal"; final_bin = "abnormal"; final_sub = None
                        dst_dir = abnormal_top
                    else:
                        denom = max(p_att + p_nor, 1e-8)
                        p_att_cond = p_att / denom
                        if p_att_cond >= TH_ATT_WITHIN:
                            final_name = "attention"; final_bin = "normal"; final_sub = "attention"; dst_dir = normal_sub_attention
                        else:
                            final_name = "normal"; final_bin = "normal"; final_sub = "normal"; dst_dir = normal_sub_normal
                else:
                    pred_idx = int(np.argmax(pr))
                    final_name = class_order[pred_idx]
                    final_bin = "abnormal" if final_name == "abnormal" else "normal"
                    final_sub = final_name if final_bin == "normal" else None
                    dst_dir = {"abnormal": abnormal_top, "attention": normal_sub_attention, "normal": normal_sub_normal}.get(final_name, normal_sub_normal)

                dt = delta_lookup.get(p) if delta_lookup is not None else None
                hs = hotspot_lookup.get(p) if hotspot_lookup is not None else False
                if final_name == "normal":
                    if (DELTA_ATT_ENABLE and dt is not None and dt >= DELTA_ATT_TH) or hs:
                        final_name = "attention"; final_bin = "normal"; final_sub = "attention"; dst_dir = normal_sub_attention

                os.makedirs(dst_dir, exist_ok=True)
                base = os.path.basename(p); dst_path = ensure_unique_path(os.path.join(dst_dir, base))
                try:
                    if move_files: shutil.move(p, dst_path)
                    else: shutil.copy2(p, dst_path)
                except Exception: dst_path = ""

                rows.append({
                    "crop_path": p, "dst_path": dst_path,
                    "final": final_name, "final_bin": final_bin, "final_sub": final_sub,
                    "prob_abnormal": p_abn, "prob_attention": p_att, "prob_normal": p_nor,
                    "delta_temp": dt, "hotspot_gate": bool(hs),
                })
    return pd.DataFrame(rows)

# =========================
# 지도 HTML (Leaflet + vWorld) — 스냅 레이어 옵션 추가
# =========================
def build_satellite_map_js(
    df: pd.DataFrame, map_html_path: str, map_geojson_path: str,
    image_status: Dict[str, Dict[str, bool]], image_gps: Dict[str, Tuple[Optional[float], Optional[float]]],
    thermal_path_by_id: Dict[str, str], rgb_path_by_id: Dict[str, str], overlay_dir: str,
    row_info: Optional[Dict[str, Dict[str, float]]] = None, zones_js: Optional[List[Dict]] = None,
    image_zone: Optional[Dict[str, str]] = None, rotation_by_id: Optional[Dict[str, str]] = None,
    # ▼ 옵션
    ortho_tif_path: Optional[str] = None, use_ortho_tif: bool = False,
    summary: Optional[Dict[str, int]] = None,
    attention_count_th: int = 10,
    # (NEW) 스냅 포인트 GeoJSON 상대경로
    snapped_rel: str = "",
    show_snapped: bool = False,
):
    if not MAKE_MAP_HTML: return

    overlay_map = {}
    if df is not None and not df.empty:
        for image_id in df["image_id"].unique():
            ov = os.path.join(overlay_dir, f"{image_id}_overlay.jpg")
            if os.path.exists(ov): overlay_map[image_id] = ov

    points = []
    base_dir_for_rel = os.path.dirname(map_html_path)
    def relify(path):
        return os.path.relpath(path, start=base_dir_for_rel).replace("\\", "/") if path and os.path.exists(path) else ""

    for image_id, (lat, lon) in image_gps.items():
        if lat is None or lon is None: continue
        st = image_status.get(image_id, {"has_attention": False, "has_abnormal": False, "attention_count": 0})
        has_abn = bool(st.get("has_abnormal"))
        att_cnt = int(st.get("attention_count", 0))

        if has_abn:
            color = "red"
        elif MAP_INCLUDE_ATTENTION and (att_cnt >= attention_count_th):
            color = "orange"
        else:
            color = "white"

        info = row_info.get(image_id, {}) if row_info else {}
        row_id = int(info.get("row_id", 0))
        rot_class = (rotation_by_id or {}).get(image_id, "rot-0")
        ir_show  = overlay_map.get(image_id) or ""
        rgb_show = rgb_path_by_id.get(image_id, "")
        zone_name = image_zone.get(image_id, ZONE_UNASSIGNED_NAME) if image_zone else ZONE_UNASSIGNED_NAME
        points.append({
            "image_id": image_id, "lat": float(lat), "lon": float(lon),
            "color": color, "row_id": row_id, "rot": rot_class,
            "ir_rel":  relify(ir_show), "rgb_rel": relify(rgb_show), "zone": zone_name,
        })

    if points:
        min_lat = min(p["lat"] for p in points); max_lat = max(p["lat"] for p in points)
        min_lon = min(p["lon"] for p in points); max_lon = max(p["lon"] for p in points)
        center_lat = (min_lat + max_lat)/2.0; center_lon = (min_lon + max_lon)/2.0
    else:
        center_lat, center_lon = 36.5, 127.9

    ensure_dir(os.path.dirname(map_geojson_path))
    with open(map_geojson_path, 'w', encoding='utf-8') as f:
        json.dump({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"image_id": p["image_id"], "color": p["color"]},
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]}
            } for p in points]
        }, f, ensure_ascii=False)

    # (NEW) 스냅 포인트 레이어 스위치
    snapped_layer_script = ""
    if show_snapped and snapped_rel:
        snapped_layer_script = f"""
  try {{
    fetch("{snapped_rel}").then(r => r.json()).then(gj => {{
      const feats = (gj && gj.features) ? gj.features : [];
      feats.forEach(ft => {{
        const c = ft.geometry && ft.geometry.coordinates;
        if (!c || c.length < 2) return;
        const lon = c[0], lat = c[1];
        const p = ft.properties || {{}};
        let color = '#00c853'; // green for snapped
        if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
        else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
        const marker = L.circleMarker([lat, lon], {{
          radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.55
        }}).addTo(map);
        let html = `<b>Snapped</b>`;
        if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
        if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
        if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
        if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
        marker.bindPopup(html, {{maxWidth: 320}});
      }});
    }}).catch(e => console.warn('snap layer load error', e));
  }} catch(e) {{ console.warn('snap layer error', e); }}
"""
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PV Map (vWorld JS)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
html, body, #map {{ height:100%; margin:0; padding:0; }}
.leaflet-popup-content-wrapper {{ max-width: 360px; }}
.leaflet-popup-content {{ max-height: 65vh; overflow:auto; }}
.imgbox {{ width:300px; height:220px; display:flex; align-items:center; justify-content:center; overflow:hidden; background:#111; border:1px solid #333; border-radius:6px; margin:6px 0; }}
.img-rot {{ display:block; transform-origin:center center; max-width:none; max-height:none; }}
.rot-0 {{ width:100%; height:auto; transform:rotate(0deg); }}
.rot-90 {{ height:100%; width:auto; transform:rotate(90deg); }}
.rot--90 {{ height:100%; width:auto; transform:rotate(-90deg); }}
.legend {{ position:absolute; bottom:14px; left:14px; background:#fff; padding:8px 10px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.15); font:13px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
.legend .item {{ display:flex; align-items:center; gap:8px; margin:2px 0; }}
.legend .swatch {{ width:12px; height:12px; border-radius:50%; border:1px solid #222; }}
.swatch.white {{ background:#fff; }} .swatch.orange {{ background:orange; }} .swatch.red {{ background:red; }}
</style></head>
<body>
<div id="map"></div>
<div class="legend">
  <div class="item"><span class="swatch white"></span>정상/주의(기본)</div>
  <div class="item"><span class="swatch orange"></span>주의(이미지 내 주의 ≥ {attention_count_th})</div>
  <div class="item"><span class="swatch red"></span>이상</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const vworldKey = "CE021E5D-02DE-3564-B9B8-C907B5121E0E";
const tiles = L.tileLayer(
  `https://api.vworld.kr/req/wmts/1.0.0/${{vworldKey}}/Satellite/{{z}}/{{y}}/{{x}}.jpeg`,
  {{ attribution: "© vWorld/NGII", maxNativeZoom: 19, maxZoom: 22, tileSize: 256 }}
);
const map = L.map('map', {{ center: [{center_lat:.7f}, {center_lon:.7f}], zoom: 7, maxZoom: 22, preferCanvas: true }});
tiles.addTo(map);
const points = {json.dumps(points, ensure_ascii=False)};
if (points && points.length > 0) {{
  const latlngs = points.map(p => [p.lat, p.lon]);
  const bounds = L.latLngBounds(latlngs);
  map.fitBounds(bounds, {{ padding: [30, 30] }});
}}
(points || []).forEach(p => {{
  const stroke = (p.color === "white") ? "#222" : p.color;
  const marker = L.circleMarker([p.lat, p.lon], {{ radius:8, color:stroke, weight:2, fillColor:p.color, fillOpacity:0.5 }}).addTo(map);
  if (marker.bringToFront) marker.bringToFront();
  const rotClass = p.rot || "rot-0";
  let html = `<b>${{p.image_id}}</b>`;
  if (p.zone) {{ html += `<div><small>Zone: <b>${{p.zone}}</b></small></div>`; }}
  html += `<div><small>위치: ${{p.lat.toFixed(6)}}, ${{p.lon.toFixed(6)}}</small></div>`;
  if (p.ir_rel) {{
    const irName = p.ir_rel.split('/').pop();
    html += `<div style="margin-top:6px"><b>IR(Overlay)</b> — <a href="${{p.ir_rel}}" target="_blank">${{irName}}</a></div>`;
    html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.ir_rel}}" alt="IR"></div>`;
  }}
  if (p.rgb_rel) {{
    const rgbName = p.rgb_rel.split('/').pop();
    html += `<div style="margin-top:4px"><b>RGB</b> — <a href="${{p.rgb_rel}}" target="_blank">${{rgbName}}</a></div>`;
    html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.rgb_rel}}" alt="RGB"></div>`;
  }}
  marker.bindPopup(html, {{ maxWidth: 340 }});
}});
{snapped_layer_script}
</script></body></html>
"""
    with open(map_html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[지도(JS)] 저장 완료: {map_html_path}  (포인트 수: {len(points)})")

# =========================
# 결과 대시보드 HTML — 스냅 레이어 옵션 추가
# =========================
def build_results_dashboard_html(
    map_html_path: str,
    points: List[Dict],
    zones_js: Optional[List[Dict]],
    center_lat: float,
    center_lon: float,
    use_ortho_tif: bool,
    ortho_rel: str,
    attention_count_th: int,
    summary: Dict[str, int],
    summary_meta: Dict[str, str],  # {"shoot_date": "..."}
    # 기존: 디듑
    modules_dedup_rel: str = "",
    show_dedup: bool = False,
    # (NEW): 스냅 레이어
    modules_snapped_rel: str = "",
    show_snapped: bool = False,
):
    ensure_dir(os.path.dirname(map_html_path))
    # (NEW) 스냅 레이어 스크립트
    snapped_layer_script = ""
    if show_snapped and modules_snapped_rel:
        snapped_layer_script = f"""
  try {{
    fetch("{modules_snapped_rel}").then(r => r.json()).then(gj => {{
      const feats = (gj && gj.features) ? gj.features : [];
      feats.forEach(ft => {{
        const c = ft.geometry && ft.geometry.coordinates;
        if (!c || c.length < 2) return;
        const lon = c[0], lat = c[1];
        const p = ft.properties || {{}};
        let color = '#00c853';
        if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
        else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
        const marker = L.circleMarker([lat, lon], {{
          radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
        }}).addTo(map);
        let html = `<b>Snapped</b>`;
        if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
        if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
        if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
        if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
        marker.bindPopup(html, {{maxWidth: 320}});
      }});
    }}).catch(e => console.warn('snap layer load error', e));
  }} catch(e) {{ console.warn('snap layer error', e); }}
"""
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PV 결과 대시보드</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  html, body {{ height:100%; margin:0; }}
  body {{ display:flex; flex-direction:column; }}
  header {{
    flex: 0 0 auto;
    background: #fff; border-bottom:1px solid #eee;
    padding: 12px 16px;
    font: 14px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }}
  .wrap {{ display:flex; gap:12px; flex-wrap:wrap; align-items:center; }}
  .title {{ font-size:16px; font-weight:600; margin-right:auto; }}
  .card {{
    background:#fafafa; border:1px solid #eee; border-radius:10px;
    padding:10px 12px; min-width:160px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }}
  .card .k {{ color:#666; font-size:12px; }}
  .card .v {{ font-size:18px; font-weight:700; margin-top:2px; }}
  main {{ flex: 1 1 auto; min-height:0; }}
  #map {{ width:100%; height:100%; }}
  .leaflet-popup-content-wrapper {{ max-width: 360px; }}
  .leaflet-popup-content {{ max-height: 65vh; overflow:auto; }}
  .imgbox {{
    width: 320px; height: 240px; display:flex; align-items:center; justify-content:center;
    overflow:hidden; background:#111; border:1px solid #333; border-radius:6px; margin:6px 0;
  }}
  .img-rot {{ display:block; transform-origin:center center; max-width:none; max-height:none; }}
  .rot-0  {{ width: 100%; height: auto; transform: rotate(0deg);  }}
  .rot-90 {{ height: 100%; width: auto; transform: rotate(90deg);  }}
  .rot--90{{ height: 100%; width: auto; transform: rotate(-90deg); }}
  .legend {{
    position: absolute; bottom: 14px; left: 14px; background:#fff; padding:8px 10px; border-radius:8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15); font: 13px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }}
  .legend .item {{ display:flex; align-items:center; gap:8px; margin:2px 0; }}
  .legend .swatch {{ width:12px; height:12px; border-radius:50%; border:1px solid #222; }}
  .swatch.white {{ background:#fff; }}
  .swatch.orange {{ background:orange; }}
  .swatch.red {{ background:red; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="title">PV 결과 대시보드</div>
    <div class="card"><div class="k">촬영일자</div><div class="v" id="shootDate">-</div></div>
    <div class="card"><div class="k">입력 이미지 수(전체)</div><div class="v" id="sumInput">-</div></div>
    <div class="card"><div class="k">열화상 이미지 수</div><div class="v" id="sumThermal">-</div></div>
    <div class="card"><div class="k">RGB 이미지 수</div><div class="v" id="sumRGB">-</div></div>
    <div class="card"><div class="k">모듈 수(전체)</div><div class="v" id="sumModules">-</div></div>
    <div class="card"><div class="k">이상 모듈 수</div><div class="v" id="sumAbn">-</div></div>
    <div class="card"><div class="k">정상 모듈 수</div><div class="v" id="sumNor">-</div></div>
    <div class="card"><div class="k">주의 모듈 수</div><div class="v" id="sumAtt">-</div></div>
  </div>
</header>
<main>
  <div id="map"></div>
  <div class="legend">
    <div class="item"><span class="swatch white"></span>정상/주의(기본)</div>
    <div class="item"><span class="swatch orange"></span>주의(이미지 내 주의 ≥ {attention_count_th})</div>
    <div class="item"><span class="swatch red"></span>이상</div>
  </div>
</main>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/georaster@1.6.3/dist/georaster.browser.min.js"></script>
<script src="https://unpkg.com/georaster-layer-for-leaflet@3.10.0/dist/georaster-layer-for-leaflet.min.js"></script>

<script>
  const points   = {json.dumps(points, ensure_ascii=False)};
  const zones    = {json.dumps(zones_js or [], ensure_ascii=False)};
  const useOrtho = {str(bool(use_ortho_tif)).lower()};
  const orthoRel = {json.dumps(ortho_rel)};
  const summary  = {json.dumps(summary or {}, ensure_ascii=False)};
  const meta     = {json.dumps(summary_meta or {}, ensure_ascii=False)};
  const showDedup = {str(bool(show_dedup)).lower()};
  const modulesDedupRel = {json.dumps(modules_dedup_rel)};
  const showSnap = {str(bool(show_snapped)).lower()};
  const modulesSnapRel = {json.dumps(modules_snapped_rel)};

  const map = L.map('map', {{
    center: [{center_lat:.7f}, {center_lon:.7f}],
    zoom: 7, maxZoom: 22, preferCanvas: true
  }});
  const tiles = L.tileLayer(
    "https://api.vworld.kr/req/wmts/1.0.0/14190970-6061-3A19-B45C-70C2973E3E9E/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
    {{ attribution:"© vWorld/NGII", maxNativeZoom:19, maxZoom:22, tileSize:256 }}
  ).addTo(map);

  // GeoTIFF 배경 (옵션)
  (async () => {{
    try {{
      if (useOrtho && orthoRel) {{
        const response = await fetch(orthoRel);
        const arrayBuffer = await response.arrayBuffer();
        const georaster = await parseGeoraster(arrayBuffer);
        const layer = new GeoRasterLayer({{ georaster, opacity: 0.95, resolution: 256 }});
        layer.addTo(map);
        try {{ map.fitBounds(layer.getBounds(), {{ padding:[30,30] }}); }} catch(e) {{}}
      }}
    }} catch(e) {{ console.warn("GeoTIFF 로드 실패:", e); }}
  }})();

  // Zone 폴리곤
  function lonlatRingsToLatlng(rings) {{ return rings.map(pt => [pt[1], pt[0]]); }}
  (zones || []).forEach(z => {{
    (z.coords || []).forEach(poly => {{
      const outer = lonlatRingsToLatlng(poly[0] || []);
      const holes = (poly.slice(1) || []).map(r => lonlatRingsToLatlng(r));
      if (outer.length >= 3) {{
        L.polygon([outer, ...holes], {{ color:"#1e90ff", weight:2, fillColor:"#1e90ff", fillOpacity:0.08 }})
        .bindTooltip(String(z.name)).addTo(map);
      }}
    }});
  }});

  // 프레임 포인트(열화상)
  (points || []).forEach(p => {{
    const stroke = (p.color === "white") ? "#222" : p.color;
    const marker = L.circleMarker([p.lat, p.lon], {{
      radius: 8, color: stroke, weight: 2, fillColor: p.color, fillOpacity: 0.5
    }}).addTo(map);
    if (marker.bringToFront) marker.bringToFront();
    const rotClass = p.rot || "rot-0";
    let html = `<b>${{p.image_id}}</b>`;
    if (p.zone) html += `<div><small>Zone: <b>${{p.zone}}</b></small></div>`;
    html += `<div><small>위치: ${{p.lat.toFixed(6)}}, ${{p.lon.toFixed(6)}}</small></div>`;
    if (p.ir_rel) {{
      const nm = p.ir_rel.split('/').pop();
      html += `<div style="margin-top:6px"><b>IR</b> — <a href="${{p.ir_rel}}" target="_blank">${{nm}}</a></div>`;
      html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.ir_rel}}" alt="IR"></div>`;
    }}
    if (p.rgb_rel) {{
      const nm = p.rgb_rel.split('/').pop();
      html += `<div style="margin-top:4px"><b>RGB</b> — <a href="${{p.rgb_rel}}" target="_blank">${{nm}}</a></div>`;
      html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.rgb_rel}}" alt="RGB"></div>`;
    }}
    marker.bindPopup(html, {{maxWidth: 360}});
  }});

  // 디듑 레이어
  try {{
    if (showDedup && modulesDedupRel) {{
      fetch(modulesDedupRel).then(r => r.json()).then(gj => {{
        const feats = (gj && gj.features) ? gj.features : [];
        feats.forEach(ft => {{
          const c = ft.geometry && ft.geometry.coordinates;
          if (!c || c.length < 2) return;
          const lon = c[0], lat = c[1];
          const p = ft.properties || {{}};
          let color = '#ffffff';
          if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
          else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
          const marker = L.circleMarker([lat, lon], {{
            radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
          }}).addTo(map);
          const cid = (p.cluster_id !== undefined && p.cluster_id !== null) ? p.cluster_id : '-';
          let html = `<b>Module# ${{cid}}</b>`;
          html += `<div>상태: <b>${{p.final || '-'}}</b></div>`;
          if (p.delta_temp !== undefined && p.delta_temp !== null) {{
            html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
          }}
          if (p.image_id) html += `<div>대표 프레임: ${{p.image_id}}</div>`;
          marker.bindPopup(html, {{maxWidth: 300}});
        }});
      }}).catch(e => console.warn('dedup geojson load error', e));
    }}
  }} catch(e) {{ console.warn('dedup layer error', e); }}

  // (NEW) 스냅 레이어
  try {{
    if (showSnap && modulesSnapRel) {{
      fetch(modulesSnapRel).then(r => r.json()).then(gj => {{
        const feats = (gj && gj.features) ? gj.features : [];
        feats.forEach(ft => {{
          const c = ft.geometry && ft.geometry.coordinates;
          if (!c || c.length < 2) return;
          const lon = c[0], lat = c[1];
          const p = ft.properties || {{}};
          let color = '#00c853';
          if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
          else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
          const marker = L.circleMarker([lat, lon], {{
            radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
          }}).addTo(map);
          let html = `<b>Snapped</b>`;
          if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
          if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
          if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
          if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
          marker.bindPopup(html, {{maxWidth: 300}});
        }});
      }}).catch(e => console.warn('snap geojson load error', e));
    }}
  }} catch(e) {{ console.warn('snap layer error', e); }}

  // 상단 카드 채우기
  const get = (o,k,d='-') => (o && k in o) ? o[k] : d;
  document.getElementById('shootDate').textContent = get(meta,'shoot_date','-');
  document.getElementById('sumInput').textContent  = get(summary,'num_input_images','-');
  document.getElementById('sumThermal').textContent= get(summary,'num_thermal_images','-');
  document.getElementById('sumRGB').textContent    = get(summary,'num_rgb_images','-');
  document.getElementById('sumModules').textContent= get(summary,'num_modules_total','-');
  document.getElementById('sumAbn').textContent    = get(summary,'num_abnormal','-');
  document.getElementById('sumNor').textContent    = get(summary,'num_normal','-');
  document.getElementById('sumAtt').textContent    = get(summary,'num_attention','-');
</script>
</body>
</html>
"""
    with open(map_html_path, "w", encoding="utf-8") as f:
        f.write(html)

# =========================
# (NEW) 모듈 카탈로그 로드 + KDTree 준비
# =========================
from sklearn.neighbors import NearestNeighbors

# ---------- Dedup(중복 통합) 유틸 ----------
try:
    from sklearn.cluster import DBSCAN
except ImportError as _e:
    raise ImportError("scikit-learn이 필요합니다. pip install scikit-learn") from _e

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
    if not df_dedup.empty:
        df_dedup = df_dedup.merge(df[["crop_path", "cluster_id"]], on="crop_path", how="left")
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

# [Part 4/5] — 메인 루프 스냅 적용 + 스냅 CSV/GeoJSON 저장 + 지도/대시보드 반영

# =========================
# (NEW) 스냅 결과 GeoJSON 저장
# =========================
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


# =========================
# main() 내 수정 — 스냅 적용/저장/요약/지도전달
# =========================
def main():
    if not os.path.isdir(INPUT_IMG_DIR):
        raise FileNotFoundError(f"INPUT_IMG_DIR not found: {INPUT_IMG_DIR}")

    # 출력 폴더 준비
    for d in [OUTPUT_ROOT, OVERLAY_DIR, SORTED_BASE, TEMP_RAW_DIR, TEMP_COLOR_DIR, TEMP_RGB_DIR, CROP_DIR]:
        ensure_dir(d)
    if SAVE_REJECTS:
        ensure_dir(REJECTS_DIR)

    # 재실행 시 비움 (베이스 유지)
    for d in [CROP_DIR, SORTED_BASE, OVERLAY_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
        ensure_dir(d)

    rejected_rows: List[Dict] = []

    # 디바이스
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("[Device]", device)
    if device.type == "cuda":
        try:
            print("CUDA:", torch.cuda.get_device_name(0))
        except Exception:
            pass

    # 모델 로드 (베이스 유지)
    maskrcnn = get_maskrcnn_model(num_classes=2).to(device)
    maskrcnn.load_state_dict(torch.load(MASKRCNN_WEIGHTS, map_location=device))
    maskrcnn.eval()

    ckpt = torch.load(CLF_WEIGHTS, map_location=device)
    class_order: List[str] = ckpt.get("class_order")
    if not class_order:
        raise ValueError("Classifier checkpoint missing 'class_order'. ['normal','attention','abnormal'] 필요")
    img_size = int(ckpt.get("img_size", 300))
    use_gray = bool(ckpt.get("use_grayscale", False))

    clf = build_effb3(num_classes=len(class_order)).to(device)
    clf.load_state_dict(ckpt["model_state"])
    clf.eval()
    tf, tf_flip = make_transforms(img_size, use_gray)

    # 입력 수집 (베이스 유지)
    all_imgs = list_input_images(INPUT_IMG_DIR)
    print(f"[입력 진단] 지원 확장자 매칭 파일 수: {len(all_imgs)}")

    # T/V 매칭 (베이스 유지)
    thermal_by_key5, rgb_by_key5 = {}, {}
    thermal_no_key, rgb_no_key = [], []
    for p in all_imgs:
        base, tv, key5 = parse_tv_and_key5(p)
        if tv == "T":
            (thermal_by_key5.setdefault(key5, []).append(p) if key5 else thermal_no_key.append(p))
        elif tv == "V":
            (rgb_by_key5.setdefault(key5, []).append(p) if key5 else rgb_no_key.append(p))

    image_ids: List[str] = []
    thermal_path_by_id: Dict[str, str] = {}
    rgb_path_by_id: Dict[str, str] = {}
    for key5, t_list in thermal_by_key5.items():
        t_list.sort()
        v_list = sorted(rgb_by_key5.get(key5, []))
        for idx, t_path in enumerate(t_list):
            image_id = os.path.splitext(os.path.basename(t_path))[0]
            image_ids.append(image_id)
            thermal_path_by_id[image_id] = t_path
            if idx < len(v_list):
                rgb_path_by_id[image_id] = v_list[idx]
    for t_path in sorted(thermal_no_key):
        base_t = os.path.splitext(os.path.basename(t_path))[0]
        image_id = base_t if base_t not in thermal_path_by_id else base_t + "_nokey1"
        image_ids.append(image_id)
        thermal_path_by_id[image_id] = t_path
    print(f"[처리 대상 확정] 열화상(T) 이미지 수: {len(image_ids)}")
    if not image_ids:
        raise RuntimeError("열화상(T) 이미지가 없습니다. 파일명 규칙(T/V, key5/끝글자)을 확인하세요.")

    # FOV (베이스 유지)
    HFOV_DEG, VFOV_DEG = _fov_from_35mm_equiv(FOCAL_35MM_EQ, FRAME_35MM_W_H)
    print(f"[FOV] HFOV={HFOV_DEG:.2f}°, VFOV={VFOV_DEG:.2f}°")

    # Zones (베이스 유지)
    zones = load_region_polygons(REGION_GEOJSON_PATH)

    # MRK/NAV 로드 (베이스 유지)
    mrk_nav_table = load_mrk_nav(MRK_CSV_PATH, NAV_CSV_PATH)
    if mrk_nav_table:
        print(f"[MRK/NAV] 보조 테이블 로드: {len(mrk_nav_table)}건")
    else:
        print("[MRK/NAV] 사용 안 함(파일 미지정/미발견)")

    # (NEW) 모듈 카탈로그 로드 (스냅 준비)
    module_catalog = None
    if SNAP_ENABLE and MODULE_CATALOG_JSON and os.path.isfile(MODULE_CATALOG_JSON):
        module_catalog = load_module_catalog_json(MODULE_CATALOG_JSON)
    else:
        print("[SNAP] 비활성화 또는 카탈로그 파일 없음")

    # 결과 누적 컨테이너 (베이스 유지 + 스냅 필드 추가)
    master_rows: List[Dict] = []
    image_status: Dict[str, Dict[str, bool]] = {}
    image_gps: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    image_zone: Dict[str, str] = {}

    extracted_raw_ok = 0
    extracted_raw_fail = 0
    prev_lat_for_heading = None
    prev_lon_for_heading = None

    # ======== 메인 루프 ========
    for image_id in tqdm(sorted(image_ids), desc="[RAW+Detect(rJPG)+Temp]"):
        t_path = thermal_path_by_id[image_id]

        # GPS (EXIF → RGB → MRK/NAV 보강) — 베이스 유지
        lat, lon = extract_gps_from_exif(t_path)
        if (lat is None or lon is None) and image_id in rgb_path_by_id:
            lat2, lon2 = extract_gps_from_exif(rgb_path_by_id[image_id])
            lat = lat if lat is not None else lat2
            lon = lon if lon is not None else lon2
        if (lat is None or lon is None) and mrk_nav_table:
            la_m, lo_m, _ = mrk_nav_lookup_for_image(t_path, mrk_nav_table)
            lat = lat if (lat is not None) else la_m
            lon = lon if (lon is not None) else lo_m
        image_gps[image_id] = (lat, lon)

        zone_name = assign_zone_for_point(lon=lon, lat=lat, zones=zones, unassigned=ZONE_UNASSIGNED_NAME)
        image_zone.setdefault(image_id, zone_name)

        # 헤딩 추정 — 베이스 유지
        heading_deg = _heading_from_exif(t_path)
        if (heading_deg is None) and mrk_nav_table:
            _, _, hdg_m = mrk_nav_lookup_for_image(t_path, mrk_nav_table)
            heading_deg = hdg_m if hdg_m is not None else None
        if heading_deg is None:
            heading_deg = _heading_guess_from_neighbors(prev_lat_for_heading, prev_lon_for_heading, lat, lon)
        if heading_deg is None:
            heading_deg = 0.0
        prev_lat_for_heading, prev_lon_for_heading = lat, lon

        # RAW 추출 (컬러는 옵션) — 베이스 유지
        base_name = os.path.splitext(os.path.basename(t_path))[0]
        raw_out_path = os.path.join(TEMP_RAW_DIR, base_name + ".raw")
        color_out_path = os.path.join(TEMP_COLOR_DIR, base_name + "_djicolor.jpg")

        ok = extract_temp_and_color_dji(
            rjpeg_path=t_path,
            output_raw_path=raw_out_path,
            output_color_path=color_out_path,
            exe_path=DJI_IRP_EXE,
            distance_m=DJI_MEASURE_DIST_M,
            palette=DJI_VIZ_PALETTE,
            max_wait=20,
            need_color=EXTRACT_DJI_COLOR
        )
        if not ok or (not os.path.isfile(raw_out_path)):
            extracted_raw_fail += 1
            print(f"[경고] RAW 추출 실패(계속 진행): {t_path}")
            raw_out_path = ""  # 아래 단계에서 None 처리
        else:
            extracted_raw_ok += 1

        # === 분석(검출/크롭/분류) 입력은 rJPG 원본 — 베이스 유지
        det_base_path = t_path
        pil_det = Image.open(det_base_path).convert("RGB")
        img_np = np.array(pil_det)
        H, W = pil_det.height, pil_det.width

        # RAW 로드 및 rJPG 크기 맞춤 — 베이스 유지
        raw_img_up = None
        if raw_out_path and os.path.isfile(raw_out_path):
            raw0 = _load_raw_float32_auto(raw_out_path)
            if raw0 is not None:
                raw_img_up = _resize_raw_to_size(raw0, W, H)

        # RCNN 추론 — 베이스 유지
        x = transforms.ToTensor()(Image.fromarray(img_np)).unsqueeze(0).to(device)
        with torch.inference_mode(), torch.cuda.amp.autocast(enabled=(device.type == 'cuda')):
            out = maskrcnn(x)[0]
        scores_t = out.get("scores", torch.tensor([]))
        labels_t = out.get("labels", torch.tensor([]))
        boxes_t = out.get("boxes", torch.tensor([]))
        masks_t = out.get("masks", None)

        boxes_np = boxes_t.detach().cpu().numpy().astype(int) if isinstance(boxes_t, torch.Tensor) and boxes_t.numel() > 0 else []
        labels_np = labels_t.detach().cpu().numpy().astype(int) if isinstance(labels_t, torch.Tensor) and labels_t.numel() > 0 else []
        scores_np = scores_t.detach().cpu().numpy().astype(float) if isinstance(scores_t, torch.Tensor) and scores_t.numel() > 0 else []
        if isinstance(masks_t, torch.Tensor) and masks_t.numel() > 0:
            masks_np = masks_t[:, 0].detach().cpu().numpy()
        else:
            masks_np = []

        # 후보 수집 + 필터 — 베이스 유지
        cands: List[Tuple[float, int, int, int, int, int, np.ndarray]] = []

        def _log_reject(reason, s, lbl, x1, y1, x2, y2, area_bbox, area_mask):
            saved_path = ""
            if SAVE_REJECTS:
                x1c = max(0, x1); y1c = max(0, y1); x2c = min(W - 1, x2); y2c = min(H - 1, y2)
                crop = pil_det.crop((x1c, y1c, x2c, y2c)) if (x2c > x1c and y2c > y1c) else pil_det.copy()
                out_dir = os.path.join(REJECTS_DIR, image_id); ensure_dir(out_dir)
                out_name = f"{image_id}_{len(rejected_rows)+1:03d}_{reason}.jpg"
                out_path = os.path.join(out_dir, out_name)
                try:
                    if crop.width > REJECT_THUMB_MAX_W:
                        new_h = int(crop.height * (REJECT_THUMB_MAX_W / float(crop.width)))
                        crop = crop.resize((REJECT_THUMB_MAX_W, new_h), Image.BICUBIC)
                    crop.save(out_path, "JPEG", quality=92)
                    if os.path.isfile(det_base_path):
                        safe_paste_exif(det_base_path, out_path)
                except Exception:
                    pass
                saved_path = out_path
            rejected_rows.append({
                "image_id": image_id, "rej_idx": len(rejected_rows) + 1, "reason": reason, "score": s, "label": lbl,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2, "w": max(0, x2 - x1), "h": max(0, y2 - y1),
                "area_bbox": area_bbox, "area_mask": area_mask, "preview_path": saved_path
            })

        for i in range(len(scores_np)):
            s = float(scores_np[i])
            box = boxes_np[i] if len(boxes_np) else np.array([0, 0, W - 1, H - 1])
            x1, y1, x2, y2 = map(int, box.tolist())
            lbl = int(labels_np[i]) if len(labels_np) else -1
            mask = (masks_np[i] > 0.5) if len(masks_np) else np.zeros((H, W), dtype=bool)

            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(W - 1, x2); y2 = min(H - 1, y2)

            w = (x2 - x1); h = (y2 - y1)
            area_bbox = max(0, w) * max(0, h)
            area_mask = int(mask[y1:y2, x1:x2].sum()) if (y2 > y1 and x2 > x1) else 0

            if s < SCORE_TH:
                _log_reject("low_score", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if lbl != 1:
                _log_reject("wrong_cls", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if x1 <= 1 or y1 <= 1 or x2 >= W - 2 or y2 >= H - 2:
                _log_reject("border", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if area_bbox < MIN_AREA_PX and area_mask < MIN_AREA_PX:
                _log_reject("too_small_noise", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if w < MIN_MODULE_W or h < MIN_MODULE_H:
                _log_reject("min_dim", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if area_bbox < MIN_MODULE_AREA and area_mask < MIN_MODULE_AREA:
                _log_reject("min_area", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue

            cands.append((s, x1, y1, x2, y2, lbl, mask))

        # NMS — 베이스 유지
        if cands:
            boxes_t2 = torch.tensor([[c[1], c[2], c[3], c[4]] for c in cands], dtype=torch.float32, device=device)
            scores_t2 = torch.tensor([c[0] for c in cands], dtype=torch.float32, device=device)
            keep_idx = nms(boxes_t2, scores_t2, 0.50).tolist()
        else:
            keep_idx = []

        # 격자 이웃 필터 — 베이스 유지
        if keep_idx:
            cands_kept = [cands[k] for k in keep_idx]
            keep_idx_grid_local = filter_by_grid_adjacency(
                cands_kept, img_w=W, img_h=H, pair_required=True,
                size_outlier_tol=2.0, col_tol_mult=0.7, row_near_min_mult=0.3, row_near_max_mult=2.2
            )
            keep_idx = [keep_idx[j] for j in keep_idx_grid_local]

        # 크롭/온도/핫스팟 + 모듈 중심 GPS + (NEW) 스냅
        cnt = 0
        for k in keep_idx:
            s, x1, y1, x2, y2, lbl, mask = cands[k]
            crop_arr = img_np[y1:y2, x1:x2]
            crop_pil = Image.fromarray(crop_arr)
            quad = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

            crop_name = f"{image_id}_{cnt + 1}.jpg"
            crop_path = os.path.join(CROP_DIR, crop_name)
            ensure_dir(os.path.dirname(crop_path))
            try:
                crop_pil.save(crop_path, "JPEG", quality=92)
                safe_paste_exif(det_base_path, crop_path)  # rJPG에서 EXIF 복사
            except Exception:
                continue

            mean_t, max_t, delta_t = _compute_temp_stats_in_bbox(raw_img_up, (x1, y1, x2, y2))
            is_hot = _analyze_hotspot_in_bbox(raw_img_up, (x1, y1, x2, y2)) if HS_ENABLE else False

            # 모듈 중심 → GPS (베이스 유지)
            cx = (x1 + x2) * 0.5; cy = (y1 + y2) * 0.5
            c_x = W * 0.5; c_y = H * 0.5
            Wg, Hg, gsd_x, gsd_y = _gsd_from_fov_and_alt(HFOV_DEG, VFOV_DEG, ALT_AGL_M, W, H)
            du = cx - c_x; dv = cy - c_y
            dx_cam = du * gsd_x; dy_cam = -dv * gsd_y
            psi = math.radians(heading_deg if heading_deg is not None else 0.0)
            cosP, sinP = math.cos(psi), math.sin(psi)
            dE = cosP * dx_cam - sinP * dy_cam
            dN = sinP * dx_cam + cosP * dy_cam
            mod_lat, mod_lon = (None, None)
            if (lat is not None) and (lon is not None):
                mod_lat, mod_lon = _enu_offset_to_latlon(lat, lon, dE, dN)

            # (NEW) 카탈로그 스냅
            snap_mid = None; snap_lat = None; snap_lon = None
            if SNAP_ENABLE and module_catalog and (mod_lat is not None) and (mod_lon is not None):
                idx, item = snap_point_to_catalog(mod_lat, mod_lon, module_catalog, eps_m=float(SNAP_EPS_M))
                if item is not None:
                    snap_mid = item.get("mid")
                    snap_lat = float(item.get("lat"))
                    snap_lon = float(item.get("lon"))

            tag = {"image_id": image_id, "module_id": cnt + 1, "bbox": [int(x1), int(y1), int(x2), int(y2)],
                   "quad": [[float(q[0]), float(q[1])] for q in quad], "score": float(s)}

            master_rows.append({
                "image_id": image_id, "module_id": cnt + 1, "tag": json.dumps(tag, ensure_ascii=False),
                "bbox_x1": int(x1), "bbox_y1": int(y1), "bbox_x2": int(x2), "bbox_y2": int(y2),
                "quad": json.dumps(tag["quad"]), "score": float(s),
                "crop_path": crop_path, "temp_raw": raw_out_path,
                "mean_temp": None if mean_t is None else float(mean_t),
                "max_temp": None if max_t is None else float(max_t),
                "delta_temp": None if delta_t is None else float(delta_t),
                "zone": zone_name, "hs_is_hotspot": bool(is_hot),
                "centroid_u": float(cx), "centroid_v": float(cy),
                "mod_lat": None if (mod_lat is None) else float(mod_lat),
                "mod_lon": None if (mod_lon is None) else float(mod_lon),
                "snap_mid": snap_mid,
                "snap_lat": snap_lat,
                "snap_lon": snap_lon,
                "heading_deg": float(heading_deg if heading_deg is not None else 0.0),
                "gsd_x_m_per_px": float(gsd_x), "gsd_y_m_per_px": float(gsd_y),
                "footprint_w_m": float(Wg), "footprint_h_m": float(Hg),
                "overlay_base": det_base_path,   # 오버레이는 rJPG 원본 위에
                "det_base": det_base_path,       # 분석 입력 기록
                "img_w": int(W), "img_h": int(H),
            })
            cnt += 1

    print(f"[RAW] 추출 성공: {extracted_raw_ok} / 실패: {extracted_raw_fail}")

    # 분류 (베이스 유지)
    crop_paths = [r["crop_path"] for r in master_rows]
    delta_lookup = {r["crop_path"]: r.get("delta_temp") for r in master_rows}
    hotspot_lookup = {r["crop_path"]: r.get("hs_is_hotspot") for r in master_rows}
    df_clf = classify_and_sort(
        clf, class_order, crop_paths, SORTED_BASE, tf, tf_flip, device,
        move_files=MOVE_CROPS, delta_lookup=delta_lookup, hotspot_lookup=hotspot_lookup
    )

    # 병합 (베이스 유지 + 스냅 필드 포함)
    df_master = pd.DataFrame(master_rows)
    df = df_master.merge(df_clf, on="crop_path", how="left") if not df_master.empty else pd.DataFrame()

    # ===== Summary 계산 (스냅 포함)
    num_thermal_images = len(image_ids)
    num_rgb_images     = sum(1 for _ in rgb_path_by_id.values())
    num_modules_total  = int(len(df)) if not df.empty else 0
    num_abnormal       = int((df["final"] == "abnormal").sum()) if not df.empty else 0
    num_attention      = int((df["final"] == "attention").sum()) if not df.empty else 0
    num_normal         = int((df["final"] == "normal").sum()) if not df.empty else 0

    # (NEW) 스냅 카운트
    num_snapped = int(df["snap_mid"].notna().sum()) if (not df.empty and "snap_mid" in df.columns) else 0

    summary = {
        "num_thermal_images": num_thermal_images,
        "num_rgb_images": num_rgb_images,
        "num_modules_total": num_modules_total,
        "num_abnormal": num_abnormal,
        "num_attention": num_attention,
        "num_normal": num_normal,
        "num_modules_snapped": num_snapped,
    }

    # 이미지 상태 + rJPG 오버레이 생성 (베이스 유지)
    ensure_dir(OVERLAY_DIR)
    overlay_map = {}
    image_status = {}
    if not df.empty:
        for image_id, g in df.groupby("image_id"):
            has_att = bool((g["final"] == "attention").any())
            has_abn = bool((g["final"] == "abnormal").any())
            att_cnt = int((g["final"] == "attention").sum())
            image_status[image_id] = {"has_attention": has_att, "has_abnormal": has_abn, "attention_count": att_cnt}

            base_for_overlay = next((row.get("overlay_base") for _, row in g.iterrows() if row.get("overlay_base")), None)
            if not base_for_overlay:
                base_for_overlay = thermal_path_by_id.get(image_id, "")

            overlay_items = []
            for _, row in g[g["final"].isin(["attention", "abnormal"])].iterrows():
                quad = json.loads(row["quad"]) if isinstance(row["quad"], str) else row["quad"]
                bbox = [int(row["bbox_x1"]), int(row["bbox_y1"]), int(row["bbox_x2"]), int(row["bbox_y2"])]
                tag_extra = ""
                if ADD_DELTA_TO_TAG and ("delta_temp" in row) and pd.notna(row["delta_temp"]):
                    try: tag_extra = f" (ΔT={float(row['delta_temp']):.1f}°C)"
                    except Exception: tag_extra = ""
                overlay_items.append({
                    "quad": quad, "bbox": bbox, "label": row["final"],
                    "tag": f"{row['image_id']}#{row['module_id']}{tag_extra}"
                })
            overlay_path = os.path.join(OVERLAY_DIR, f"{image_id}_overlay.jpg")
            if overlay_items and base_for_overlay and os.path.exists(base_for_overlay):
                draw_overlay(base_for_overlay, overlay_items, overlay_path)
                try: safe_paste_exif(base_for_overlay, overlay_path)
                except Exception: pass
                overlay_map[image_id] = overlay_path
            elif CREATE_OVERLAY_WHEN_EMPTY and base_for_overlay and os.path.isfile(base_for_overlay):
                shutil.copy2(base_for_overlay, overlay_path)
                try: safe_paste_exif(base_for_overlay, overlay_path)
                except Exception: pass
                overlay_map[image_id] = overlay_path

    for _img_id in image_gps.keys():
        if _img_id not in image_status:
            image_status[_img_id] = {"has_attention": False, "has_abnormal": False, "attention_count": 0}

    # CSV (마스터 + 스냅)
    if not df.empty:
        df["overlay_path"] = df["image_id"].map(overlay_map).fillna("")
    ensure_dir(os.path.dirname(MASTER_CSV))
    (df if not df.empty else pd.DataFrame()).to_csv(MASTER_CSV, index=False, encoding="utf-8-sig")

    # (NEW) 스냅 결과 CSV/GeoJSON 저장
    if SNAP_ENABLE and (not df.empty):
        try:
            df_snap = df[df["snap_mid"].notna()].copy()
            ensure_dir(os.path.dirname(SNAP_SAVE_CSV))
            df_snap.to_csv(SNAP_SAVE_CSV, index=False, encoding="utf-8-sig")
            print(f"[SNAP] CSV 저장: {SNAP_SAVE_CSV} (rows={len(df_snap)})")
            save_snapped_geojson(df, SNAP_SAVE_GEOJSON)
        except Exception as e:
            print(f"[SNAP] 저장 실패: {e}")

    # Alerts (베이스 유지)
    df_alerts = pd.DataFrame()
    if not df.empty:
        df_alerts = df[df["final"].isin(["abnormal", "attention"])].copy()
        by = []; ascending = []
        if "prob_abnormal" in df_alerts.columns: by.append("prob_abnormal"); ascending.append(False)
        if "score" in df_alerts.columns:         by.append("score");          ascending.append(False)
        if "delta_temp" in df_alerts.columns:    by.append("delta_temp");     ascending.append(False)
        if by:
            df_alerts = df_alerts.sort_values(by=by, ascending=ascending)
        if ALERTS_TOP_N and ALERTS_TOP_N > 0:
            df_alerts = df_alerts.head(ALERTS_TOP_N)
    ensure_dir(os.path.dirname(ALERTS_CSV))
    df_alerts.to_csv(ALERTS_CSV, index=False, encoding="utf-8-sig")

    # Reject CSV (베이스 유지)
    if rejected_rows:
        rej_df = pd.DataFrame(rejected_rows)
        ensure_dir(os.path.dirname(REJECTS_CSV))
        rej_df.to_csv(REJECTS_CSV, index=False, encoding="utf-8-sig")
        print(f"[REJECT] 미달 모듈 {len(rejected_rows)}건 기록: {REJECTS_CSV}")
    else:
        print("[REJECT] 미달 모듈 없음")

    # 모듈 포인트 GeoJSON (프레임 단위) — 베이스 유지
    try:
        ensure_dir(os.path.dirname(MODULE_POINTS_GEOJSON))
        features = []
        for r in master_rows:
            mlon = r.get("mod_lon", None); mlat = r.get("mod_lat", None)
            if mlon is None or mlat is None:
                continue
            props = {
                "image_id": r.get("image_id"), "module_id": r.get("module_id"),
                "zone": r.get("zone"), "delta_temp": r.get("delta_temp"),
                "hs_is_hotspot": r.get("hs_is_hotspot"), "heading_deg": r.get("heading_deg"),
                "gsd_x": r.get("gsd_x_m_per_px"), "gsd_y": r.get("gsd_y_m_per_px"),
                "crop_path": r.get("crop_path"), "temp_raw": r.get("temp_raw"),
                "final": None,
            }
            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [float(mlon), float(mlat)]}
            })
        with open(MODULE_POINTS_GEOJSON, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
        print(f"[GeoJSON] 모듈 포인트 저장: {MODULE_POINTS_GEOJSON} (features={len(features)})")
    except Exception as e:
        print(f"[GeoJSON] 모듈 포인트 저장 실패: {e}")

    # === NEW: DEDUP (중복 모듈 통합) — 베이스 유지
    df_with_cluster = df.copy()
    df_dedup = pd.DataFrame()
    if DEDUP_ENABLE and (not df.empty):
        try:
            df_with_cluster, df_dedup = dedup_modules_by_location(
                df=df, eps_m=float(DEDUP_EPS_M), min_samples=int(DEDUP_MIN_SAMPLES)
            )
            if not df_dedup.empty:
                save_dedup_geojson(df_dedup, MODULE_POINTS_DEDUP_GEOJSON)
                summary["num_modules_dedup"]  = int(len(df_dedup))
                summary["num_abnormal_dedup"] = int((df_dedup["final"] == "abnormal").sum())
                summary["num_attention_dedup"]= int((df_dedup["final"] == "attention").sum())
                summary["num_normal_dedup"]   = int((df_dedup["final"] == "normal").sum())
            else:
                summary["num_modules_dedup"]  = 0
                summary["num_abnormal_dedup"] = 0
                summary["num_attention_dedup"]= 0
                summary["num_normal_dedup"]   = 0
        except Exception as e:
            print(f"[DEDUP] 실행 실패: {e}")
            summary["num_modules_dedup"]  = 0
            summary["num_abnormal_dedup"] = 0
            summary["num_attention_dedup"]= 0
            summary["num_normal_dedup"]   = 0
    else:
        summary["num_modules_dedup"]  = 0
        summary["num_abnormal_dedup"] = 0
        summary["num_attention_dedup"]= 0
        summary["num_normal_dedup"]   = 0

    # === NEW: DEDUP (중복 모듈 통합) ===
    df_with_cluster = df.copy()
    df_dedup = pd.DataFrame()
    if DEDUP_ENABLE and (not df.empty):
        try:
            df_with_cluster, df_dedup = dedup_modules_by_location(
                df=df, eps_m=float(DEDUP_EPS_M), min_samples=int(DEDUP_MIN_SAMPLES)
        )
            if not df_dedup.empty:
                save_dedup_geojson(df_dedup, MODULE_POINTS_DEDUP_GEOJSON)
                # 요약(대시보드 카드용)도 갱신
                summary["num_modules_dedup"]   = int(len(df_dedup))
                summary["num_abnormal_dedup"]  = int((df_dedup["final"] == "abnormal").sum())
                summary["num_attention_dedup"] = int((df_dedup["final"] == "attention").sum())
                summary["num_normal_dedup"]    = int((df_dedup["final"] == "normal").sum())
            else:
                summary["num_modules_dedup"]   = 0
                summary["num_abnormal_dedup"]  = 0
                summary["num_attention_dedup"] = 0
                summary["num_normal_dedup"]    = 0
        except Exception as e:
            print(f"[DEDUP] 실행 실패: {e}")
            summary["num_modules_dedup"]   = 0
            summary["num_abnormal_dedup"]  = 0
            summary["num_attention_dedup"] = 0
            summary["num_normal_dedup"]    = 0
    else:
        summary["num_modules_dedup"]   = 0
        summary["num_abnormal_dedup"]  = 0
        summary["num_attention_dedup"] = 0
        summary["num_normal_dedup"]    = 0


    # === 지도/대시보드 생성 (스냅 레이어 전달 추가)
    RESULTS_HTML_PATH = os.path.join(OUTPUT_ROOT, "results.html")
    row_info = compute_rows_from_gps(image_gps, gap_multiplier=ROW_GAP_MULTIPLIER, split_axis=ROW_SPLIT_AXIS)
    rotation_by_id = compute_rotation_classes_by_lonlat(image_gps)
    zones_js = [{"name": z["name"], "coords": z["coords"]} for z in zones]

    # (1) map.html — 경량 지도
    snapped_rel = ""
    show_snapped = False
    if SNAP_ENABLE and os.path.isfile(SNAP_SAVE_GEOJSON):
        try:
            snapped_rel = os.path.relpath(SNAP_SAVE_GEOJSON, start=os.path.dirname(MAP_HTML_PATH)).replace("\\", "/")
            show_snapped = True
        except Exception:
            show_snapped = False

    build_satellite_map_js(
        df=df if not df.empty else pd.DataFrame(columns=["image_id"]),
        map_html_path=MAP_HTML_PATH,
        map_geojson_path=MAP_GEOJSON_PATH,
        image_status=image_status,
        image_gps=image_gps,
        thermal_path_by_id=thermal_path_by_id,
        rgb_path_by_id=rgb_path_by_id,
        overlay_dir=OVERLAY_DIR,
        row_info=row_info,
        zones_js=zones_js,
        image_zone=image_zone,
        rotation_by_id=rotation_by_id,
        ortho_tif_path=ORTHO_TIF_PATH if (USE_ORTHO_TIF and os.path.isfile(ORTHO_TIF_PATH)) else None,
        use_ortho_tif=USE_ORTHO_TIF and os.path.isfile(ORTHO_TIF_PATH),
        summary=summary,
        attention_count_th=ATTENTION_COUNT_ORANGE_TH,
        # (NEW)
        snapped_rel=snapped_rel,
        show_snapped=show_snapped,
    )

    # (2) results.html — 대시보드
    points = []
    overlay_map = {}
    if not df.empty:
        for image_id in df["image_id"].unique():
            ov = os.path.join(OVERLAY_DIR, f"{image_id}_overlay.jpg")
            if os.path.exists(ov):
                overlay_map[image_id] = ov

    def _relify_for_results(path):
        base_dir_for_rel = os.path.dirname(RESULTS_HTML_PATH)
        return os.path.relpath(path, start=base_dir_for_rel).replace("\\", "/") if path and os.path.exists(path) else ""

    for image_id, (lat, lon) in image_gps.items():
        if lat is None or lon is None:
            continue
        st = image_status.get(image_id, {"has_attention": False, "has_abnormal": False, "attention_count": 0})
        att_cnt = int(st.get("attention_count", 0))
        if st.get("has_abnormal"):
            color = "red"
        elif MAP_INCLUDE_ATTENTION and (att_cnt >= ATTENTION_COUNT_ORANGE_TH):
            color = "orange"
        else:
            color = "white"
        rot_class = (rotation_by_id or {}).get(image_id, "rot-0")
        ir_show  = overlay_map.get(image_id) or thermal_path_by_id.get(image_id, "")
        rgb_show = rgb_path_by_id.get(image_id, "")
        zone_name = image_zone.get(image_id, ZONE_UNASSIGNED_NAME) if image_zone else ZONE_UNASSIGNED_NAME
        points.append({
            "image_id": image_id,
            "lat": float(lat), "lon": float(lon),
            "color": color, "rot": rot_class,
            "ir_rel":  _relify_for_results(ir_show),
            "rgb_rel": _relify_for_results(rgb_show),
            "zone": zone_name,
        })

    if points:
        min_lat = min(p["lat"] for p in points); max_lat = max(p["lat"] for p in points)
        min_lon = min(p["lon"] for p in points); max_lon = max(p["lon"] for p in points)
        center_lat = (min_lat + max_lat)/2.0
        center_lon = (min_lon + max_lon)/2.0
    else:
        center_lat, center_lon = 36.5, 127.9

    ortho_rel = ""
    if USE_ORTHO_TIF and os.path.isfile(ORTHO_TIF_PATH):
        try:
            ortho_rel = os.path.relpath(ORTHO_TIF_PATH, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
        except Exception:
            pass

    shoot_date = guess_shoot_date(all_imgs, INPUT_IMG_DIR) or "-"
    summary2 = dict(summary)
    summary2["num_input_images"] = len(all_imgs)

    modules_dedup_rel = ""
    show_dedup = False
    if DEDUP_ENABLE and os.path.isfile(MODULE_POINTS_DEDUP_GEOJSON):
        try:
            modules_dedup_rel = os.path.relpath(MODULE_POINTS_DEDUP_GEOJSON, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
            show_dedup = True
        except Exception:
            show_dedup = False

    modules_snapped_rel = ""
    show_snapped2 = False
    if SNAP_ENABLE and os.path.isfile(SNAP_SAVE_GEOJSON):
        try:
            modules_snapped_rel = os.path.relpath(SNAP_SAVE_GEOJSON, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
            show_snapped2 = True
        except Exception:
            show_snapped2 = False

    build_results_dashboard_html(
        map_html_path=RESULTS_HTML_PATH,
        points=points,
        zones_js=zones_js,
        center_lat=center_lat, center_lon=center_lon,
        use_ortho_tif=USE_ORTHO_TIF and os.path.isfile(ORTHO_TIF_PATH),
        ortho_rel=ortho_rel,
        attention_count_th=ATTENTION_COUNT_ORANGE_TH,
        summary=summary2,
        summary_meta={"shoot_date": shoot_date},
        modules_dedup_rel=modules_dedup_rel,
        show_dedup=show_dedup,
        # (NEW) 스냅
        modules_snapped_rel=modules_snapped_rel,
        show_snapped=show_snapped2,
    )

    print(f"대시보드 페이지 : {RESULTS_HTML_PATH}")

    # 요약 출력 (베이스 유지 + 스냅)
    ncrops = len(glob(os.path.join(CROP_DIR, "*.jpg")))
    nsorted = 0
    if os.path.isdir(SORTED_BASE):
        for d in os.listdir(SORTED_BASE):
            sub = os.path.join(SORTED_BASE, d)
            if os.path.isdir(sub):
                nsorted += len(glob(os.path.join(sub, "*.jpg")))
                for dd in os.listdir(sub):
                    sub2 = os.path.join(sub, dd)
                    if os.path.isdir(sub2):
                        nsorted += len(glob(os.path.join(sub2, "*.jpg")))

    print(f"\n=== DONE (v3 rJPG 분석 + rJPG 오버레이 + DEDUP + SNAP) ===")
    print(f"총 열화상 이미지: {len(image_ids)}")
    print(f"총 크롭 수(DF 기준): {0 if df_master.empty else len(df)}")
    print(f"카운트: crops/{ncrops} | sorted/{nsorted}")
    print(f"마스터 CSV : {MASTER_CSV}")
    print(f"스냅 CSV   : {SNAP_SAVE_CSV if os.path.isfile(SNAP_SAVE_CSV) else '(생성 실패/없음)'}")
    print(f"스냅 GeoJSON: {SNAP_SAVE_GEOJSON if os.path.isfile(SNAP_SAVE_GEOJSON) else '(생성 실패/없음)'}")
    print(f"모듈 포인트(프레임): {MODULE_POINTS_GEOJSON}")
    if DEDUP_ENABLE:
        print(f"모듈 포인트(디듑): {MODULE_POINTS_DEDUP_GEOJSON if os.path.isfile(MODULE_POINTS_DEDUP_GEOJSON) else '(생성 실패/없음)'}")
    if MAKE_MAP_HTML:
        print(f"지도(위성)  : {MAP_HTML_PATH}")


if __name__ == "__main__":
    main()

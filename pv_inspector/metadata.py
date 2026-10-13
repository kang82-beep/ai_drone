"""PV inspection: metadata."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFile, ExifTags
import os, re, json, time, math, shutil, subprocess, io
import pandas as pd
try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

def _dms_to_dd(dms, ref) -> Optional[float]:
    try:
        def number(value):
            return value[0] / value[1] if isinstance(value, (tuple, list)) else float(value)
        deg, minutes, seconds = map(number, dms)
        if isinstance(ref, bytes):
            ref = ref.decode('ascii')
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
                direction = gps.get(17, None)  # GPSImgDirection
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


def _read_text_any(path: str) -> Optional[str]:
    if (not path) or (not os.path.isfile(path)):
        return None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
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


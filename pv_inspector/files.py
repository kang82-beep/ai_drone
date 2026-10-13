"""PV inspection: files."""
from __future__ import annotations
from . import config
from collections import Counter
from PIL import Image, ImageDraw, ImageFile, ExifTags
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import os, re, json, time, math, shutil, subprocess, io
import piexif
try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

def ensure_dir(p: str):
    os.makedirs(p or ".", exist_ok=True)


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
    if config.RECURSIVE_INPUT:
        for root, _, fnames in os.walk(input_dir):
            for f in fnames:
                if f.startswith("._"): continue
                if _norm_ext(f) in config.SUPPORTED_EXTS:
                    files.append(os.path.join(root, f))
    else:
        names = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        for f in names:
            if f.startswith("._"): continue
            if _norm_ext(f) in config.SUPPORTED_EXTS:
                files.append(os.path.join(input_dir, f))
        try:
            ext_counter = Counter(_norm_ext(x) for x in names)
            print("[입력 확장자 요약]", dict(ext_counter.most_common()))
        except Exception:
            pass
    return sorted(files)


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
            for k in config.EXIF_DT_KEYS:
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


def parse_tv_and_key5(path: str) -> Tuple[str, Optional[str], Optional[str]]:
    base = os.path.splitext(os.path.basename(path))[0]
    capture = re.fullmatch(r"DJI_(\d{8})\d{6}_(\d+)_([TV])", base, re.IGNORECASE)
    if capture:
        day, sequence, kind = capture.groups()
        # Thermal/RGB timestamps can differ by a second within one capture.
        key = os.path.join(os.path.dirname(os.path.abspath(path)), f"{day}_{sequence}")
        return base, kind.upper(), key
    if base and base[-1].upper() in ("T","V"):
        tv = base[-1].upper()
        key5 = os.path.join(os.path.dirname(os.path.abspath(path)), base[:-1])
        return base, tv, key5
    m = re.search(r"([A-Za-z0-9]{5})([tTvV])$", base)
    if m:
        return base, m.group(2).upper(), m.group(1)
    return base, None, None


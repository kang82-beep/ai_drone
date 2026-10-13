"""PV inspection: thermal."""
from __future__ import annotations
from . import config
from PIL import Image, ImageDraw, ImageFile, ExifTags
import cv2
import numpy as np
import os, re, json, time, math, shutil, subprocess, io
from .files import ensure_dir


def measure_module_raw(raw, mask):
    """Measure finite temperatures inside a detector mask on the native RAW grid.

    Mask coverage must be >=75% of a RAW pixel. Erode the boundary once on the
    RAW grid; never fall back to background-containing bounding boxes.
    Hotspot area thresholds retain the old display-pixel units via area scaling.
    """
    result = dict(temperature_status='raw_unavailable', mean_temp=None, max_temp=None,
                  delta_temp=None, raw_pixel_count=0, raw_valid_fraction=None,
                  hs_is_hotspot=None, temperature_method='native_raw_mask_v1')
    if raw is None:
        return result
    h,w=raw.shape
    coverage=cv2.resize(mask.astype(np.float32),(w,h),interpolation=cv2.INTER_AREA)
    selected=cv2.erode((coverage>=.75).astype(np.uint8),np.ones((3,3),np.uint8),iterations=1).astype(bool)
    total=int(selected.sum())
    finite=selected & np.isfinite(raw)
    count=int(finite.sum())
    result.update(raw_pixel_count=count,raw_valid_fraction=count/total if total else None)
    if total<8:
        result['temperature_status']='mask_too_small';return result
    if count/total<.95:
        result['temperature_status']='invalid_raw_pixels';return result
    vals=raw[finite]
    mean=float(vals.mean());maximum=float(vals.max())
    result.update(temperature_status='ok',mean_temp=mean,max_temp=maximum,delta_temp=maximum-mean)
    bg=float(np.median(vals));sigma=float(np.std(vals))
    threshold=bg+max(config.HS_DELTA_ABS_C,config.HS_DELTA_SIGMA_MULT*max(sigma,1e-6))
    hot=finite & (raw>threshold)
    core=finite & (raw>threshold+1.5)
    area_scale=(mask.shape[0]*mask.shape[1])/(h*w)
    n,labels,stats,_=cv2.connectedComponentsWithStats(hot.astype(np.uint8),8)
    result['hs_is_hotspot']=bool(config.HS_ENABLE and any(
        stats[k,cv2.CC_STAT_AREA]*area_scale>=config.HS_MIN_AREA_PX and
        int((core & (labels==k)).sum())*area_scale>=config.HS_MIN_CORE_PX
        for k in range(1,n)))
    return result

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
    interp = cv2.INTER_NEAREST if config.RAW_INTERP == "nearest" else cv2.INTER_LINEAR
    return cv2.resize(raw_img, (target_w, target_h), interpolation=interp)


def _compute_temp_stats_in_bbox(raw_img_up: np.ndarray, bbox):
    if raw_img_up is None: return None, None, None
    H, W = raw_img_up.shape[:2]
    x1,y1,x2,y2 = map(int, bbox)
    x1 = max(0, x1); y1 = max(0, y1)
    x2 = min(W, x2); y2 = min(H, y2)
    if x2 <= x1 or y2 <= y1: return None, None, None
    roi = raw_img_up[y1:y2, x1:x2].astype(np.float32)
    if roi.size == 0 or not np.isfinite(roi).any(): return None, None, None
    finite = roi[np.isfinite(roi)]
    mean_t = float(finite.mean())
    max_t  = float(finite.max())
    delta  = float(max_t - mean_t)
    return mean_t, max_t, delta


def _analyze_hotspot_in_bbox(raw_img_up: np.ndarray, bbox) -> bool:
    if raw_img_up is None: return False
    H, W = raw_img_up.shape[:2]
    x1,y1,x2,y2 = map(int, bbox)
    x1 = max(0, x1+config.HS_BORDER_MARGIN_PX); y1 = max(0, y1+config.HS_BORDER_MARGIN_PX)
    x2 = min(W-1, x2-config.HS_BORDER_MARGIN_PX); y2 = min(H-1, y2-config.HS_BORDER_MARGIN_PX)
    if x2 <= x1 or y2 <= y1: return False
    roi = raw_img_up[y1:y2, x1:x2].astype(np.float32)
    if roi.size < 16: return False
    Tbg  = float(np.median(roi))
    sig  = float(np.std(roi))
    Tthr = Tbg + max(config.HS_DELTA_ABS_C, config.HS_DELTA_SIGMA_MULT * max(1e-6, sig))
    Tcore = Tthr + 1.5
    inner = roi
    rim = config.HS_BORDER_MARGIN_PX
    if roi.shape[0] > 2*rim and roi.shape[1] > 2*rim:
        inner = roi[rim:-rim, rim:-rim]
    m_main = (inner > Tthr)
    m_core = (inner > Tcore)
    try:
        n, lab = cv2.connectedComponents(m_main.astype(np.uint8), connectivity=8)
        largest = max((lab == L).sum() for L in range(1, n)) if n > 1 else 0
        area_ok = largest >= config.HS_MIN_AREA_PX
    except Exception:
        area_ok = int(m_main.sum()) >= config.HS_MIN_AREA_PX
    core_ok = int(m_core.sum()) >= config.HS_MIN_CORE_PX
    return bool(area_ok and core_ok)


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
        ], check=True, timeout=max_wait)

        if need_color:
            ensure_dir(os.path.dirname(output_color_path))
            ensure_dir(config.TEMP_RGB_DIR)
            with Image.open(rjpeg_path) as im:
                W_pre, H_pre = im.size  # 예: 1280x1024

            root, _ = os.path.splitext(output_color_path)
            rgb_name = os.path.basename(root) + ".rgb"
            output_rgb_path = os.path.join(config.TEMP_RGB_DIR, rgb_name)

            # 2) 컬러(.rgb)
            subprocess.run([
                exe_path, "--action", "process",
                "--source", rjpeg_path,
                "--output", output_rgb_path,
                "--palette", str(palette)
            ], check=True, timeout=max_wait)

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


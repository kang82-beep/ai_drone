"""PV inspection: pipeline."""
from __future__ import annotations
from . import config
from .association import associate_modules
from .two_row_structure import detector_candidates, filter_two_row_candidates
from .array_refinement import refine_arrays
from .neighbor_delta import add_neighbor_delta
from .checkpoints import prepare_run
from .geolocation import read_dji_pose, read_mrk, match_mrk, project_pixel
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFile, ExifTags
from glob import glob
import os, re, json, time, shutil, subprocess, io
from torchvision.ops import nms
import numpy as np
import pandas as pd
import torch
from tqdm import tqdm
from torchvision import models, transforms, datasets
from .catalog import load_module_catalog_json, save_snapped_geojson, snap_point_to_catalog
from .classification import classify_and_sort
from .dedup import dedup_modules_by_location, save_dedup_geojson
from .files import ensure_dir, guess_shoot_date, list_input_images, parse_tv_and_key5, safe_paste_exif
from .geometry import _enu_offset_to_latlon, _fov_from_35mm_equiv, _gsd_from_fov_and_alt, assign_zone_for_point, compute_rotation_classes_by_lonlat, compute_rows_from_gps, filter_by_grid_adjacency, load_region_polygons
from .metadata import _heading_from_exif, _heading_guess_from_neighbors, extract_gps_from_exif, load_mrk_nav, mrk_nav_lookup_for_image
from .models import build_effb3, get_maskrcnn_model, make_transforms
from .overlay import draw_overlay
from .reports import build_results_dashboard_html, build_satellite_map_js
from .thermal import _load_raw_float32_auto, extract_temp_and_color_dji, measure_module_raw

def main():
    if not os.path.isdir(config.INPUT_IMG_DIR):
        raise FileNotFoundError(f"INPUT_IMG_DIR not found: {config.INPUT_IMG_DIR}")

    config.validate_inputs()
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")
    prepare_run(config)

    # 출력 폴더 준비
    for d in [config.OUTPUT_ROOT, config.OVERLAY_DIR, config.SORTED_BASE, config.TEMP_RAW_DIR, config.TEMP_COLOR_DIR, config.TEMP_RGB_DIR, config.CROP_DIR]:
        ensure_dir(d)
    if config.SAVE_REJECTS:
        ensure_dir(config.REJECTS_DIR)

    rejected_rows: List[Dict] = []
    structure_rows: List[Dict] = []

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
    maskrcnn.load_state_dict(torch.load(config.MASKRCNN_WEIGHTS, map_location=device))
    maskrcnn.eval()

    ckpt = torch.load(config.CLF_WEIGHTS, map_location=device)
    class_order: List[str] = ckpt.get("class_order")
    if not class_order or len(class_order) != 3 or set(class_order) != {"normal", "attention", "abnormal"}:
        raise ValueError("Classifier checkpoint missing 'class_order'. ['normal','attention','abnormal'] 필요")
    img_size = int(ckpt.get("img_size", 300))
    use_gray = bool(ckpt.get("use_grayscale", False))

    clf = build_effb3(num_classes=len(class_order)).to(device)
    clf.load_state_dict(ckpt["model_state"])
    clf.eval()
    tf, tf_flip = make_transforms(img_size, use_gray)

    # 입력 수집 (베이스 유지)
    all_imgs = list_input_images(config.INPUT_IMG_DIR)
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
        if len(t_list) > 1 or len(v_list) > 1:
            raise ValueError(f"Ambiguous T/V capture key; separate flight folders: {key5}")
        for idx, t_path in enumerate(t_list):
            image_id = os.path.splitext(os.path.basename(t_path))[0]
            if image_id in thermal_path_by_id:
                raise ValueError(f"Duplicate image filename: {image_id}")
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
    HFOV_DEG, VFOV_DEG = _fov_from_35mm_equiv(config.FOCAL_35MM_EQ, config.FRAME_35MM_W_H)
    print(f"[FOV] HFOV={HFOV_DEG:.2f}°, VFOV={VFOV_DEG:.2f}°")

    # Zones (베이스 유지)
    zones = load_region_polygons(config.REGION_GEOJSON_PATH)

    # MRK/NAV 로드 (베이스 유지)
    mrk_records = read_mrk(config.MRK_CSV_PATH)
    mrk_nav_table = load_mrk_nav(config.MRK_CSV_PATH, config.NAV_CSV_PATH)
    if mrk_nav_table:
        print(f"[MRK/NAV] 보조 테이블 로드: {len(mrk_nav_table)}건")
    else:
        print("[MRK/NAV] 사용 안 함(파일 미지정/미발견)")

    # (NEW) 모듈 카탈로그 로드 (스냅 준비)
    module_catalog = None
    if config.SNAP_ENABLE and config.MODULE_CATALOG_JSON and os.path.isfile(config.MODULE_CATALOG_JSON):
        module_catalog = load_module_catalog_json(config.MODULE_CATALOG_JSON)
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
        pose = read_dji_pose(t_path)
        mrk = match_mrk(t_path, mrk_records)
        lat, lon = pose.get("GpsLatitude"), pose.get("GpsLongitude")
        position_source = "thermal_xmp"
        if lat is None or lon is None:
            lat, lon = extract_gps_from_exif(t_path)
            position_source = "thermal_exif"
        if (lat is None or lon is None) and mrk:
            lat, lon = mrk["lat"], mrk["lon"]
            position_source = "mrk_capture_fallback"
        if (lat is None or lon is None) and image_id in rgb_path_by_id:
            lat, lon = extract_gps_from_exif(rgb_path_by_id[image_id])
            position_source = "rgb_exif_fallback"
        if lat is None or lon is None:
            position_source = "missing"
        height_m = config.ALT_AGL_M
        height_source = "configured_camera_to_surface"
        if config.GEO_USE_RELATIVE_ALTITUDE and "RelativeAltitude" in pose:
            height_m = pose["RelativeAltitude"] - config.GEO_SURFACE_ABOVE_TAKEOFF_M
            height_source = "relative_altitude_minus_configured_surface"
        image_gps[image_id] = (lat, lon)

        zone_name = assign_zone_for_point(lon=lon, lat=lat, zones=zones, unassigned=config.ZONE_UNASSIGNED_NAME)
        image_zone.setdefault(image_id, zone_name)

        # 헤딩 추정 — 베이스 유지
        heading_deg = pose.get("GimbalYawDegree")

        # RAW 추출 (컬러는 옵션) — 베이스 유지
        base_name = os.path.splitext(os.path.basename(t_path))[0]
        raw_out_path = os.path.join(config.TEMP_RAW_DIR, base_name + ".raw")
        color_out_path = os.path.join(config.TEMP_COLOR_DIR, base_name + "_djicolor.jpg")

        ok = extract_temp_and_color_dji(
            rjpeg_path=t_path,
            output_raw_path=raw_out_path,
            output_color_path=color_out_path,
            exe_path=config.DJI_IRP_EXE,
            distance_m=config.DJI_MEASURE_DIST_M,
            palette=config.DJI_VIZ_PALETTE,
            max_wait=20,
            need_color=config.EXTRACT_DJI_COLOR
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

        # RAW 로드 (네이티브 해상도, 마스크 기반 온도 계산에 사용)
        raw0 = None
        if raw_out_path and os.path.isfile(raw_out_path):
            raw0 = _load_raw_float32_auto(raw_out_path)

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
            if config.SAVE_REJECTS:
                x1c = max(0, x1); y1c = max(0, y1); x2c = min(W - 1, x2); y2c = min(H - 1, y2)
                crop = pil_det.crop((x1c, y1c, x2c, y2c)) if (x2c > x1c and y2c > y1c) else pil_det.copy()
                out_dir = os.path.join(config.REJECTS_DIR, image_id); ensure_dir(out_dir)
                out_name = f"{image_id}_{len(rejected_rows)+1:03d}_{reason}.jpg"
                out_path = os.path.join(out_dir, out_name)
                try:
                    if crop.width > config.REJECT_THUMB_MAX_W:
                        new_h = int(crop.height * (config.REJECT_THUMB_MAX_W / float(crop.width)))
                        crop = crop.resize((config.REJECT_THUMB_MAX_W, new_h), Image.BICUBIC)
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

            if s < config.SCORE_TH:
                _log_reject("low_score", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if lbl != 1:
                _log_reject("wrong_cls", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if not config.TWO_ROW_FILTER_ENABLE and (x1 <= 1 or y1 <= 1 or x2 >= W - 2 or y2 >= H - 2):
                _log_reject("border", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if area_bbox < config.MIN_AREA_PX and area_mask < config.MIN_AREA_PX:
                _log_reject("too_small_noise", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if w < config.MIN_MODULE_W or h < config.MIN_MODULE_H:
                _log_reject("min_dim", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue
            if area_bbox < config.MIN_MODULE_AREA and area_mask < config.MIN_MODULE_AREA:
                _log_reject("min_area", s, lbl, x1, y1, x2, y2, area_bbox, area_mask); continue

            cands.append((s, x1, y1, x2, y2, lbl, mask))

        # NMS — 베이스 유지
        if cands:
            boxes_t2 = torch.tensor([[c[1], c[2], c[3], c[4]] for c in cands], dtype=torch.float32, device=device)
            scores_t2 = torch.tensor([c[0] for c in cands], dtype=torch.float32, device=device)
            keep_idx = nms(boxes_t2, scores_t2, 0.50).tolist()
        else:
            keep_idx = []

        # Two-row evidence replaces legacy adjacency so uncertain candidates survive.
        structure_by_candidate = {}
        array_by_candidate = {}
        array_review_path = ''
        if keep_idx and config.ARRAY_REVIEW_ENABLE:
            array_candidates = detector_candidates([cands[k] for k in keep_idx])
            for item, k in zip(array_candidates, keep_idx):
                item['score'] = float(cands[k][0])
            array_result = refine_arrays(img_np, array_candidates, mode='thermal')
            review_dir = os.path.join(config.OUTPUT_ROOT, 'array_review')
            ensure_dir(review_dir)
            array_review_path = os.path.join(review_dir, image_id+'.json')
            array_result['detector_candidate_indices'] = keep_idx.copy()
            array_result['image_id'] = image_id
            array_result['applied_to_temperature_masks'] = False
            with open(array_review_path, 'w', encoding='utf-8') as f:
                json.dump(array_result, f, ensure_ascii=False, indent=2, allow_nan=False)
            preview = pil_det.copy()
            preview_draw = ImageDraw.Draw(preview)
            for slot in array_result['slots']:
                supported = slot['status'] == 'image_supported'
                polygon = slot['evidence']['polygon'] if supported else slot['expected_polygon']
                points = [tuple(p) for p in polygon]
                preview_draw.line(points+[points[0]], fill='#00ff91' if supported else '#ffae32', width=2)
            preview.save(os.path.join(review_dir, image_id+'.jpg'), quality=92)
            for local_i, audit in enumerate(array_result['source_audit']):
                array_by_candidate[keep_idx[local_i]] = audit
        if keep_idx and config.TWO_ROW_FILTER_ENABLE:
            candidates = detector_candidates([cands[k] for k in keep_idx])
            local_keep, decisions = filter_two_row_candidates(candidates, (W, H))
            for local_i, decision in enumerate(decisions):
                structure_by_candidate[keep_idx[local_i]] = decision
                s, x1, y1, x2, y2, lbl, mask = cands[keep_idx[local_i]]
                structure_rows.append({
                    'image_id': image_id, 'candidate_index': keep_idx[local_i],
                    'bbox_x1': x1, 'bbox_y1': y1, 'bbox_x2': x2, 'bbox_y2': y2,
                    'score': s, **decision,
                })
                if decision['filter_action'] == 'reject':
                    _log_reject(decision['filter_reason'], s, lbl, x1, y1, x2, y2,
                                (x2-x1)*(y2-y1), int(mask[y1:y2, x1:x2].sum()))
            keep_idx = [keep_idx[j] for j in local_keep]
        elif keep_idx:
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
            crop_path = os.path.join(config.CROP_DIR, crop_name)
            ensure_dir(os.path.dirname(crop_path))
            try:
                crop_pil.save(crop_path, "JPEG", quality=92)
                safe_paste_exif(det_base_path, crop_path)  # rJPG에서 EXIF 복사
            except Exception:
                continue

            temp_result = measure_module_raw(raw0, mask)
            mean_t = temp_result["mean_temp"]
            max_t = temp_result["max_temp"]
            delta_t = temp_result["delta_temp"]
            is_hot = bool(temp_result["hs_is_hotspot"])

            # 모듈 중심 → GPS (베이스 유지)
            cx = (x1 + x2) * 0.5; cy = (y1 + y2) * 0.5
            Wg, Hg, gsd_x, gsd_y = _gsd_from_fov_and_alt(HFOV_DEG, VFOV_DEG, height_m, W, H)
            mod_lat, mod_lon, geo_status = project_pixel(
                cx, cy, W, H, lat, lon, pose, height_m, config.FOCAL_35MM_EQ)

            snap_mid = None; snap_lat = None; snap_lon = None
            if config.SNAP_ENABLE and module_catalog and (mod_lat is not None) and (mod_lon is not None):
                idx, item = snap_point_to_catalog(mod_lat, mod_lon, module_catalog, eps_m=float(config.SNAP_EPS_M))
                if item is not None:
                    snap_mid = item.get("mid")
                    snap_lat = float(item.get("lat"))
                    snap_lon = float(item.get("lon"))

            tag = {"image_id": image_id, "module_id": cnt + 1, "bbox": [int(x1), int(y1), int(x2), int(y2)],
                   "quad": [[float(q[0]), float(q[1])] for q in quad], "score": float(s)}

            master_rows.append({
                **temp_result,
                "image_id": image_id, "module_id": cnt + 1, "tag": json.dumps(tag, ensure_ascii=False),
                "structure_status": structure_by_candidate.get(k, {}).get('status', 'not_assessed'),
                "structure_filter_reason": structure_by_candidate.get(k, {}).get('filter_reason', 'legacy_filter'),
                "structure_reasons": json.dumps(structure_by_candidate.get(k, {}).get('reasons', [])),
                "array_proposed_cells": json.dumps(array_by_candidate.get(k, {}).get('cell_ids', [])),
                "array_review_path": array_review_path,
                "array_geometry_applied": False,
                "bbox_x1": int(x1), "bbox_y1": int(y1), "bbox_x2": int(x2), "bbox_y2": int(y2),
                "quad": json.dumps(tag["quad"]), "score": float(s),
                "crop_path": crop_path, "temp_raw": raw_out_path,
                "rgb_path": rgb_path_by_id.get(image_id, ""),
                "mean_temp": None if mean_t is None else float(mean_t),
                "max_temp": None if max_t is None else float(max_t),
                "delta_temp": None if delta_t is None else float(delta_t),
                "zone": zone_name, "hs_is_hotspot": bool(is_hot),
                "centroid_u": float(cx), "centroid_v": float(cy),
                "mod_lat": None if (mod_lat is None) else float(mod_lat),
                "mod_lon": None if (mod_lon is None) else float(mod_lon),
                "geo_status": geo_status,
                "position_source": position_source,
                "height_source": height_source,
                "camera_to_surface_m": height_m,
                "gimbal_yaw": pose.get("GimbalYawDegree"),
                "gimbal_pitch": pose.get("GimbalPitchDegree"),
                "gimbal_roll": pose.get("GimbalRollDegree"),
                "rtk_flag": pose.get("RtkFlag"),
                "mrk_lat": mrk.get("lat") if mrk else None,
                "mrk_lon": mrk.get("lon") if mrk else None,
                "mrk_quality": mrk.get("quality") if mrk else None,
                "snap_mid": snap_mid,
                "snap_lat": snap_lat,
                "snap_lon": snap_lon,
                "heading_deg": heading_deg,
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
    # 같은 프레임의 다른 모듈 대비 온도차와 촬영 일사 조건
    add_neighbor_delta(master_rows, threshold=config.NEIGHBOR_DELTA_ATT_TH,
                       irradiance=config.IRRADIANCE_W_M2, min_irradiance=config.IRRADIANCE_MIN_W_M2)
    neighbor_lookup = {r["crop_path"]: r["neighbor_flag"] for r in master_rows} if config.NEIGHBOR_DELTA_ENABLE else None
    df_clf = classify_and_sort(
        clf, class_order, crop_paths, config.SORTED_BASE, tf, tf_flip, device,
        move_files=config.MOVE_CROPS, delta_lookup=delta_lookup, hotspot_lookup=hotspot_lookup,
        neighbor_lookup=neighbor_lookup
    )

    # 병합 (베이스 유지 + 스냅 필드 포함)
    df_master = pd.DataFrame(master_rows)
    df = df_master.merge(df_clf.drop(columns=["delta_temp"], errors="ignore"), on="crop_path", how="left", validate="one_to_one") if not df_master.empty else pd.DataFrame()

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
        "num_reading_hold": int(df["reading_hold"].sum()) if not df.empty else 0,
        "capture_condition": master_rows[0]["capture_condition"] if master_rows else "no_observations",
    }

    # 이미지 상태 + rJPG 오버레이 생성 (베이스 유지)
    ensure_dir(config.OVERLAY_DIR)
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
                if config.ADD_DELTA_TO_TAG and ("delta_temp" in row) and pd.notna(row["delta_temp"]):
                    try: tag_extra = f" (ΔT={float(row['delta_temp']):.1f}°C)"
                    except Exception: tag_extra = ""
                overlay_items.append({
                    "quad": quad, "bbox": bbox, "label": row["final"],
                    "tag": f"{row['image_id']}#{row['module_id']}{tag_extra}"
                })
            overlay_path = os.path.join(config.OVERLAY_DIR, f"{image_id}_overlay.jpg")
            if overlay_items and base_for_overlay and os.path.exists(base_for_overlay):
                draw_overlay(base_for_overlay, overlay_items, overlay_path)
                try: safe_paste_exif(base_for_overlay, overlay_path)
                except Exception: pass
                overlay_map[image_id] = overlay_path
            elif config.CREATE_OVERLAY_WHEN_EMPTY and base_for_overlay and os.path.isfile(base_for_overlay):
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
    ensure_dir(os.path.dirname(config.MASTER_CSV))
    (df if not df.empty else pd.DataFrame()).to_csv(config.MASTER_CSV, index=False, encoding="utf-8-sig")

    # (NEW) 스냅 결과 CSV/GeoJSON 저장
    if config.SNAP_ENABLE and (not df.empty):
        try:
            df_snap = df[df["snap_mid"].notna()].copy()
            ensure_dir(os.path.dirname(config.SNAP_SAVE_CSV))
            df_snap.to_csv(config.SNAP_SAVE_CSV, index=False, encoding="utf-8-sig")
            print(f"[SNAP] CSV 저장: {config.SNAP_SAVE_CSV} (rows={len(df_snap)})")
            save_snapped_geojson(df, config.SNAP_SAVE_GEOJSON)
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
        if config.ALERTS_TOP_N and config.ALERTS_TOP_N > 0:
            df_alerts = df_alerts.head(config.ALERTS_TOP_N)
    ensure_dir(os.path.dirname(config.ALERTS_CSV))
    df_alerts.to_csv(config.ALERTS_CSV, index=False, encoding="utf-8-sig")

    # Reject CSV (베이스 유지)
    if config.TWO_ROW_FILTER_ENABLE:
        pd.DataFrame(structure_rows, columns=[
            'image_id', 'candidate_index', 'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2',
            'score', 'version', 'status', 'reasons', 'mate_ids', 'track_size',
            'same_row_neighbors', 'two_row_eligible', 'orientation_deg', 'track_id',
            'filter_action', 'filter_reason',
        ]).to_csv(os.path.join(config.OUTPUT_ROOT, 'two_row_filter.csv'), index=False, encoding='utf-8-sig')
    if rejected_rows:
        rej_df = pd.DataFrame(rejected_rows)
        ensure_dir(os.path.dirname(config.REJECTS_CSV))
        rej_df.to_csv(config.REJECTS_CSV, index=False, encoding="utf-8-sig")
        print(f"[REJECT] 미달 모듈 {len(rejected_rows)}건 기록: {config.REJECTS_CSV}")
    else:
        print("[REJECT] 미달 모듈 없음")

    # 모듈 포인트 GeoJSON (프레임 단위) — 베이스 유지
    try:
        ensure_dir(os.path.dirname(config.MODULE_POINTS_GEOJSON))
        features = []
        for r in df.to_dict("records"):
            mlon = r.get("mod_lon", None); mlat = r.get("mod_lat", None)
            if mlon is None or mlat is None:
                continue
            props = {
                "image_id": r.get("image_id"), "module_id": r.get("module_id"),
                "zone": r.get("zone"), "delta_temp": r.get("delta_temp"),
                "hs_is_hotspot": r.get("hs_is_hotspot"), "heading_deg": r.get("heading_deg"),
                "gsd_x": r.get("gsd_x_m_per_px"), "gsd_y": r.get("gsd_y_m_per_px"),
                "crop_path": r.get("dst_path") or r.get("crop_path"), "temp_raw": r.get("temp_raw"),
                "final": r.get("final"),
                "geo_status": r.get("geo_status"),
                "position_source": r.get("position_source"),
                "height_source": r.get("height_source"),
                "camera_to_surface_m": r.get("camera_to_surface_m"),
            }
            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [float(mlon), float(mlat)]}
            })
        with open(config.MODULE_POINTS_GEOJSON, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
        print(f"[GeoJSON] 모듈 포인트 저장: {config.MODULE_POINTS_GEOJSON} (features={len(features)})")
    except Exception as e:
        print(f"[GeoJSON] 모듈 포인트 저장 실패: {e}")

    # === NEW: DEDUP (중복 모듈 통합) — 베이스 유지
    df_with_cluster = df.copy()
    df_dedup = pd.DataFrame()
    if config.DEDUP_ENABLE and (not df.empty):
        try:
            if config.DEDUP_METHOD == "visual":
                df_with_cluster, df_dedup = associate_modules(
                    df, thermal_path_by_id, config.OUTPUT_ROOT,
                    config.ASSOCIATION_GPS_RADIUS_M, config.ASSOCIATION_FRAME_WINDOW)
            elif config.DEDUP_METHOD == "gps":
                df_with_cluster, df_dedup = dedup_modules_by_location(
                    df=df, eps_m=float(config.DEDUP_EPS_M), min_samples=int(config.DEDUP_MIN_SAMPLES))
            else:
                raise ValueError(f"Unknown DEDUP_METHOD: {config.DEDUP_METHOD}")
            df_with_cluster.to_csv(config.MASTER_CSV, index=False, encoding="utf-8-sig")
            if not df_dedup.empty:
                save_dedup_geojson(df_dedup, config.MODULE_POINTS_DEDUP_GEOJSON)
                df_dedup.to_csv(config.MODULE_DEDUP_CSV, index=False, encoding="utf-8-sig")
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

    from .field_review import write_field_review
    review_path = write_field_review(df_with_cluster.to_dict('records'), config.OUTPUT_ROOT)
    print(f"현장 검토표 : {review_path}")

    # === 지도/대시보드 생성 (스냅 레이어 전달 추가)
    RESULTS_HTML_PATH = os.path.join(config.OUTPUT_ROOT, "results.html")
    row_info = compute_rows_from_gps(image_gps, gap_multiplier=config.ROW_GAP_MULTIPLIER, split_axis=config.ROW_SPLIT_AXIS)
    rotation_by_id = compute_rotation_classes_by_lonlat(image_gps)
    zones_js = [{"name": z["name"], "coords": z["coords"]} for z in zones]

    # (1) map.html — 경량 지도
    snapped_rel = ""
    show_snapped = False
    if config.SNAP_ENABLE and os.path.isfile(config.SNAP_SAVE_GEOJSON):
        try:
            snapped_rel = os.path.relpath(config.SNAP_SAVE_GEOJSON, start=os.path.dirname(config.MAP_HTML_PATH)).replace("\\", "/")
            show_snapped = True
        except Exception:
            show_snapped = False

    build_satellite_map_js(
        df=df if not df.empty else pd.DataFrame(columns=["image_id"]),
        map_html_path=config.MAP_HTML_PATH,
        map_geojson_path=config.MAP_GEOJSON_PATH,
        image_status=image_status,
        image_gps=image_gps,
        thermal_path_by_id=thermal_path_by_id,
        rgb_path_by_id=rgb_path_by_id,
        overlay_dir=config.OVERLAY_DIR,
        row_info=row_info,
        zones_js=zones_js,
        image_zone=image_zone,
        rotation_by_id=rotation_by_id,
        ortho_tif_path=config.ORTHO_TIF_PATH if (config.USE_ORTHO_TIF and os.path.isfile(config.ORTHO_TIF_PATH)) else None,
        use_ortho_tif=config.USE_ORTHO_TIF and os.path.isfile(config.ORTHO_TIF_PATH),
        summary=summary,
        attention_count_th=config.ATTENTION_COUNT_ORANGE_TH,
        # (NEW)
        snapped_rel=snapped_rel,
        show_snapped=show_snapped,
    )

    # (2) results.html — 대시보드
    points = []
    overlay_map = {}
    if not df.empty:
        for image_id in df["image_id"].unique():
            ov = os.path.join(config.OVERLAY_DIR, f"{image_id}_overlay.jpg")
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
        elif config.MAP_INCLUDE_ATTENTION and (att_cnt >= config.ATTENTION_COUNT_ORANGE_TH):
            color = "orange"
        else:
            color = "white"
        rot_class = (rotation_by_id or {}).get(image_id, "rot-0")
        ir_show  = overlay_map.get(image_id) or thermal_path_by_id.get(image_id, "")
        rgb_show = rgb_path_by_id.get(image_id, "")
        zone_name = image_zone.get(image_id, config.ZONE_UNASSIGNED_NAME) if image_zone else config.ZONE_UNASSIGNED_NAME
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
    if config.USE_ORTHO_TIF and os.path.isfile(config.ORTHO_TIF_PATH):
        try:
            ortho_rel = os.path.relpath(config.ORTHO_TIF_PATH, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
        except Exception:
            pass

    shoot_date = guess_shoot_date(all_imgs, config.INPUT_IMG_DIR) or "-"
    summary2 = dict(summary)
    summary2["num_input_images"] = len(all_imgs)

    modules_dedup_rel = ""
    show_dedup = False
    if config.DEDUP_ENABLE and os.path.isfile(config.MODULE_POINTS_DEDUP_GEOJSON):
        try:
            modules_dedup_rel = os.path.relpath(config.MODULE_POINTS_DEDUP_GEOJSON, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
            show_dedup = True
        except Exception:
            show_dedup = False

    modules_snapped_rel = ""
    show_snapped2 = False
    if config.SNAP_ENABLE and os.path.isfile(config.SNAP_SAVE_GEOJSON):
        try:
            modules_snapped_rel = os.path.relpath(config.SNAP_SAVE_GEOJSON, start=os.path.dirname(RESULTS_HTML_PATH)).replace("\\", "/")
            show_snapped2 = True
        except Exception:
            show_snapped2 = False

    build_results_dashboard_html(
        map_html_path=RESULTS_HTML_PATH,
        points=points,
        zones_js=zones_js,
        center_lat=center_lat, center_lon=center_lon,
        use_ortho_tif=config.USE_ORTHO_TIF and os.path.isfile(config.ORTHO_TIF_PATH),
        ortho_rel=ortho_rel,
        attention_count_th=config.ATTENTION_COUNT_ORANGE_TH,
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
    ncrops = len(glob(os.path.join(config.CROP_DIR, "*.jpg")))
    nsorted = 0
    if os.path.isdir(config.SORTED_BASE):
        for d in os.listdir(config.SORTED_BASE):
            sub = os.path.join(config.SORTED_BASE, d)
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
    print(f"마스터 CSV : {config.MASTER_CSV}")
    print(f"스냅 CSV   : {config.SNAP_SAVE_CSV if os.path.isfile(config.SNAP_SAVE_CSV) else '(생성 실패/없음)'}")
    print(f"스냅 GeoJSON: {config.SNAP_SAVE_GEOJSON if os.path.isfile(config.SNAP_SAVE_GEOJSON) else '(생성 실패/없음)'}")
    print(f"모듈 포인트(프레임): {config.MODULE_POINTS_GEOJSON}")
    if config.DEDUP_ENABLE:
        print(f"모듈 포인트(디듑): {config.MODULE_POINTS_DEDUP_GEOJSON if os.path.isfile(config.MODULE_POINTS_DEDUP_GEOJSON) else '(생성 실패/없음)'}")
    if config.MAKE_MAP_HTML:
        print(f"지도(위성)  : {config.MAP_HTML_PATH}")


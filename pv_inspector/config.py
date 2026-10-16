"""Analysis settings. Output paths are derived by configure()."""
import os
import json
RESUME_RUN = False
CPU_THREADS = 4
DEDUP_METHOD = "visual"
ASSOCIATION_GPS_RADIUS_M = 2.0
ASSOCIATION_FRAME_WINDOW = 3
GEO_USE_RELATIVE_ALTITUDE = False
# Fitted on the Shinan3 2025-10-30 flight (M4T thermal, 30 m, about 6 m/s) by
# register_flight.py --calibrate; refit for another camera, site or flight speed.
GEO_SURFACE_ABOVE_TAKEOFF_M = 1.48  # mean panel surface above the take-off point
GEO_YAW_OFFSET_DEG = -0.64          # gimbal yaw against the drawing rows
GEO_CAMERA_FORWARD_M = 0.45         # exposure lags the position stamp by about 75 ms
GEO_CAMERA_RIGHT_M = -0.09
# Cause-estimation agent (과제_기획서 4.4). Nothing leaves this PC unless a model is named,
# LLM_SEND_IMAGES is true and OPENAI_API_KEY is set in the environment (never in a file).
LLM_MODEL = ""
LLM_SEND_IMAGES = False
LLM_MAX_MODULES = 60
from pathlib import Path

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
MRK_CSV_PATH = r"C:\Users\USER\Desktop\3호기\DJI_202607290944_006_3호기\DJI_20251016092913_0002_D.MRK"
NAV_CSV_PATH = r"C:\Users\USER\Desktop\3호기\DJI_202607290944_006_3호기\DJI_20251016092913_0002_D.NAV"
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
USE_HIERARCHICAL_DECISION = True
TH_ABNORMAL               = 0.55  # 이상 우선 임계값
TH_ATT_WITHIN             = 0.50  # P(attention | non-abnormal)
OVERLAY_ATTENTION            = True   # 주의도 항상 오버레이 생성/표시
MAP_INCLUDE_ATTENTION        = True   # 지도에서 주의 마커(주황) 사용 여부
ATTENTION_COUNT_ORANGE_TH    = 10     # 한 이미지 내 '주의' 개수 임계(주황 마커)
MAKE_MAP_HTML    = True
VWORLD_API_KEY = ""  # Set in config.local.json; used by both maps
BLENDER_EXE = ""
BLENDER_SCENE = ""
MAP_HTML_PATH    = os.path.join(OUTPUT_ROOT, "map.html")
MAP_GEOJSON_PATH = os.path.join(OUTPUT_ROOT, "map_points.geojson")
MASTER_CSV       = os.path.join(OUTPUT_ROOT, "master_results.csv")
ALERTS_CSV       = os.path.join(OUTPUT_ROOT, "alerts_topN.csv")
ALERTS_TOP_N     = 200
MOVE_CROPS       = True
SAVE_REJECTS         = True
TWO_ROW_FILTER_ENABLE = True  # Two-row sites; false restores legacy adjacency filter.
ARRAY_REVIEW_ENABLE = True  # Image-backed split/gap proposals, separate from temperature masks.
REJECTS_DIR          = os.path.join(OUTPUT_ROOT, "rejected")
REJECTS_CSV          = os.path.join(OUTPUT_ROOT, "rejected_modules.csv")
REJECT_THUMB_MAX_W   = 480
SUPPORTED_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".rjpeg", ".rjpg"}
RECURSIVE_INPUT = False
REGION_GEOJSON_PATH = r"D:\py code\zones shinan2 .geojson"
ZONE_UNASSIGNED_NAME = "Unassigned"
ROW_MIN_SEP_M      = 0.5
ROW_GAP_MULTIPLIER = 1.8
ROW_SPLIT_AXIS     = "yprime"
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
NEIGHBOR_DELTA_ENABLE = True
NEIGHBOR_DELTA_ATT_TH = 3.0   # °C, module mean above same-frame reference; provisional
IRRADIANCE_W_M2       = 0.0   # In-plane irradiance during the flight; 0 = not recorded
IRRADIANCE_MIN_W_M2   = 600.0 # Below this a reading is held, not reported as normal
ALT_AGL_M        = 30.0
FOCAL_35MM_EQ    = 52.0
FRAME_35MM_W_H   = (36.0, 24.0)
MODULE_POINTS_GEOJSON = os.path.join(OUTPUT_ROOT, "modules_points.geojson")
ANALYZE_ON_INPUT_THERMAL = True   # True: rJPG 원본으로 검출/분류/크롭
OVERLAY_ON_INPUT_THERMAL = True   # True: rJPG 원본 위에 오버레이
EXTRACT_DJI_COLOR        = False  # True면 DJI 컬러 .rgb→.jpg도 생성(참고용)
DJI_VIZ_PALETTE     = "hot_iron"
DJI_MEASURE_DIST_M  = 30.0
USE_ORTHO_TIF  = True
ORTHO_TIF_PATH = r"C:\drone\shinan2\map\result.tif"
DEDUP_ENABLE               = True     # 디듑 수행 여부
DEDUP_EPS_M                = 0.8      # 같은 실제 모듈로 볼 최대 거리(m)
DEDUP_MIN_SAMPLES          = 1        # 군집 최소 포인트 수
MODULE_DEDUP_CSV           = os.path.join(OUTPUT_ROOT, "modules_dedup.csv")
MAP_SHOW_DEDUP_MODULES     = True     # results.html / map.html에 디듑 레이어 표시
MODULE_POINTS_DEDUP_GEOJSON = os.path.join(OUTPUT_ROOT, "modules_points_dedup.geojson")
EXIF_DT_KEYS = ["DateTimeOriginal", "DateTime", "CreateDate"]
MODULE_CATALOG_JSON       = r"D:\py code\modules_catalog.json"  # GeoJSON 또는 JSON 지원(아래 로더 설명)
SNAP_ENABLE               = True     # 모듈 카탈로그에 스냅 사용 여부
SNAP_EPS_M                = 1.2      # 스냅 허용 반경(미터). 가까운 모듈만 스냅
SNAP_SAVE_GEOJSON         = os.path.join(OUTPUT_ROOT, "modules_points_snapped.geojson")
SNAP_SAVE_CSV             = os.path.join(OUTPUT_ROOT, "modules_snapped.csv")
MAP_SHOW_SNAP_MODULES     = True     # results.html / map.html에 스냅 포인트 레이어 표시

def configure(path=None, output_root=None, input_dir=None):
    """Load uppercase settings from JSON; recompute dependent output paths."""
    values = json.loads(Path(path).read_text(encoding="utf-8-sig")) if path else {}
    allowed = {key for key in globals() if key.isupper()}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown settings: {sorted(unknown)}")
    for key, value in values.items():
        previous = globals()[key]
        if isinstance(previous, bool) and not isinstance(value, bool):
            raise ValueError(f"{key} must be boolean")
        if not isinstance(previous, bool) and isinstance(previous, (int, float)) and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError(f"{key} must be numeric")
        if isinstance(previous, str) and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
    globals().update(values)
    if DEDUP_METHOD not in ("visual", "gps"):
        raise ValueError("DEDUP_METHOD must be visual or gps")
    if isinstance(ASSOCIATION_FRAME_WINDOW, bool) or not isinstance(ASSOCIATION_FRAME_WINDOW, int) or ASSOCIATION_FRAME_WINDOW < 1:
        raise ValueError("ASSOCIATION_FRAME_WINDOW must be a positive integer")
    if not 0 < ASSOCIATION_GPS_RADIUS_M < float("inf"):
        raise ValueError("ASSOCIATION_GPS_RADIUS_M must be finite and positive")
    if output_root:
        globals()["OUTPUT_ROOT"] = str(output_root)
    if input_dir:
        globals()["INPUT_IMG_DIR"] = str(input_dir)
    for key, filename in OUTPUT_FILES.items():
        globals()[key] = os.path.join(OUTPUT_ROOT, filename)
    for key in ("BATCH_SIZE", "DEDUP_MIN_SAMPLES"):
        if not isinstance(globals()[key], int) or globals()[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if not 0 <= IRRADIANCE_W_M2 <= 1500:
        raise ValueError("IRRADIANCE_W_M2 must be 0 (not recorded) or a W/m2 value up to 1500")
    for key in ("DEDUP_EPS_M", "SNAP_EPS_M", "ALT_AGL_M", "NEIGHBOR_DELTA_ATT_TH", "IRRADIANCE_MIN_W_M2"):
        if not 0 < globals()[key] < float("inf"):
            raise ValueError(f"{key} must be finite and positive")

def camera_model():
    return dict(yaw_offset_deg=GEO_YAW_OFFSET_DEG, forward_m=GEO_CAMERA_FORWARD_M, right_m=GEO_CAMERA_RIGHT_M)


def validate_inputs():
    errors = []
    if not Path(INPUT_IMG_DIR).is_dir():
        errors.append(f"INPUT_IMG_DIR: {INPUT_IMG_DIR}")
    for key in ("MASKRCNN_WEIGHTS", "CLF_WEIGHTS", "DJI_IRP_EXE"):
        if not Path(globals()[key]).is_file():
            errors.append(f"{key}: {globals()[key]}")
    if errors:
        raise FileNotFoundError("Missing required inputs:\n" + "\n".join(errors))

    warnings = []
    if MRK_CSV_PATH and not Path(MRK_CSV_PATH).is_file():
        warnings.append(f"MRK_CSV_PATH: {MRK_CSV_PATH} (MRK 기반 GPS 보강 비활성화)")
    if NAV_CSV_PATH and not Path(NAV_CSV_PATH).is_file():
        warnings.append(f"NAV_CSV_PATH: {NAV_CSV_PATH} (NAV 보조 테이블 비활성화)")
    if REGION_GEOJSON_PATH and not Path(REGION_GEOJSON_PATH).is_file():
        warnings.append(f"REGION_GEOJSON_PATH: {REGION_GEOJSON_PATH} (구역 배정 비활성화, 전부 Unassigned)")
    if SNAP_ENABLE and MODULE_CATALOG_JSON and not Path(MODULE_CATALOG_JSON).is_file():
        warnings.append(f"MODULE_CATALOG_JSON: {MODULE_CATALOG_JSON} (SNAP_ENABLE=True이지만 카탈로그 없음, 스냅 비활성화)")
    if USE_ORTHO_TIF and ORTHO_TIF_PATH and not Path(ORTHO_TIF_PATH).is_file():
        warnings.append(f"ORTHO_TIF_PATH: {ORTHO_TIF_PATH} (USE_ORTHO_TIF=True이지만 정사영상 없음, 배경 비활성화)")
    if warnings:
        print("[설정 경고] 다음 선택적 입력이 없어 관련 기능이 비활성화됩니다:")
        for w in warnings:
            print(f"  - {w}")

OUTPUT_FILES = {'CROP_DIR': 'crops', 'OVERLAY_DIR': 'overlays', 'SORTED_BASE': 'sorted', 'TEMP_RAW_DIR': 'temperature_raw', 'TEMP_COLOR_DIR': 'temperature_color', 'TEMP_RGB_DIR': 'temperature_rgb', 'MAP_HTML_PATH': 'map.html', 'MAP_GEOJSON_PATH': 'map_points.geojson', 'MASTER_CSV': 'master_results.csv', 'ALERTS_CSV': 'alerts_topN.csv', 'REJECTS_DIR': 'rejected', 'REJECTS_CSV': 'rejected_modules.csv', 'MODULE_POINTS_GEOJSON': 'modules_points.geojson', 'MODULE_DEDUP_CSV': 'modules_dedup.csv', 'MODULE_POINTS_DEDUP_GEOJSON': 'modules_points_dedup.geojson', 'SNAP_SAVE_GEOJSON': 'modules_points_snapped.geojson', 'SNAP_SAVE_CSV': 'modules_snapped.csv'}

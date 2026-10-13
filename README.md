# 드론 열화상 태양광 검사

**현장 검토표:** 분석 후 `field_review.html`에서 원본/크롭/오버레이와 검토 사유를 확인하고 검수 CSV 양식을 받을 수 있습니다. 온도 품질과 모델/최종 판정 근거를 보존합니다. [바로 확인하는 방법과 모델 정확도 개선 준비](FIELD_REVIEW.md)를 참고하세요.

**배열 우선 분리:** RGB의 국소 2단 배열·원본 경계를 이용한 분리/중복 정리/빈칸 재검사를 구현했습니다. 운영 RGB 지도에서 새 결과와 기존 후보를 전환할 수 있습니다. 열화상은 별도 검토 제안을 저장합니다. [적용 방법과 검증 범위](ARRAY_REFINEMENT.md)를 참고하세요.

**2단 배열 필터:** 실제 검출 단계에 보수적 구조 필터와 후보별 판단 기록을 연결했습니다. 설정·실영상 비교 결과·제한은 [TWO_ROW_FILTER.md](TWO_ROW_FILTER.md)를 참고하세요.

**중복 연결 업데이트:** 기본 중복 제거를 GPS 후보 + 열화상 정합 기반 임시 ID 방식으로 변경했습니다. 원본 관측은 보존하고 불확실한 연결을 보류합니다. 설정·검증·RGB 미구현 범위는 [ASSOCIATION.md](ASSOCIATION.md)를 참고하세요.

**위치 계산 업데이트:** 원시 MRK 촬영 번호 연결과 DJI XMP 짐벌 자세 기반 지상 투영을 추가했습니다. 아래 초기 리팩터링 제한 중 고정 촬영 방향/원시 MRK 미지원 설명은 이 변경으로 대체됩니다. 현재 설정과 검증 범위는 [GEOLOCATION.md](GEOLOCATION.md)를 참고하세요.

기존 `ff test 3-3.py`를 기능별 패키지로 분리했습니다. 원본은 `legacy/ff test 3-3.py`에 그대로 보관했습니다. 기존 파일은 새 프로그램을 실행하는 진입점입니다.

## 실행

Python 3.10 이상을 사용합니다. `requirements.txt`는 리팩터링 당시 환경의 버전입니다. 학습 가중치와 호환되는 PyTorch/CUDA 환경을 사용하세요.

1. `config.example.json`을 `config.local.json`으로 복사합니다.
2. 입력 이미지 폴더, 검출/분류 가중치, DJI SDK 실행 파일 경로를 수정합니다.
3. 경로 검사 후 실행합니다.

```powershell
python -m pv_inspector --config config.local.json --check
python -m pv_inspector --config config.local.json
# 기존 실행 파일도 같은 옵션 지원
python "ff test 3-3.py" --config config.local.json --output results/run02
```

출력 폴더는 새 폴더 또는 빈 폴더여야 합니다. 기존 결과를 자동 삭제하지 않습니다. 설정 파일 없이 실행하면 `pv_inspector/config.py`의 예전 경로가 사용됩니다. `--check`는 필수 경로 존재 여부만 검사하며 모델 로딩/SDK 실행을 보장하지 않습니다. `--input`으로 설정 JSON의 `INPUT_IMG_DIR`을 커맨드라인에서 덮어쓸 수 있습니다. `--gui`는 Tkinter 운영 창을 엽니다 — 자세한 내용은 [DESKTOP.md](DESKTOP.md)를 참고하세요.

## 구조

| 파일 | 역할 |
|---|---|
| `config.py` | 경로, 임계값, JSON 설정 로드 및 검증 |
| `checkpoints.py` | 입력/설정/코드 서명 기반 재실행(RESUME_RUN) 검증 |
| `files.py` | 입력 검색, T/V 매칭 키, 촬영 날짜 |
| `metadata.py` | GPS/EXIF, MRK/NAV |
| `geometry.py` | 좌표 변환, 격자 필터, 구역/행 계산 |
| `thermal.py` | DJI SDK, RAW 온도, 핫스팟 |
| `models.py` | Mask R-CNN / EfficientNet-B3 생성과 전처리 |
| `classification.py` | 배치 분류, TTA, 온도 기반 주의 판정 |
| `catalog.py` | 모듈 카탈로그와 스냅 |
| `dedup.py` | 위치 군집 및 대표 모듈 선정 |
| `overlay.py` | 이미지 오버레이 |
| `reports.py` | Leaflet 지도 및 HTML 대시보드 |
| `pipeline.py` | 모델 로드 → 이미지 검출/온도 → 분류 → 결과 저장 |

검출과 크롭은 rJPG의 표시 영상에서 수행하며 온도는 DJI SDK가 추출한 RAW로 계산합니다. 동영상 프레임 추출 기능은 없습니다. 입력은 파일명 끝이 T인 열화상이며 V인 가시광과 전체 촬영 접두사/폴더로 매칭합니다.

## 수정한 문제

- 마스터/분류 병합 시 `delta_temp_x/y`로 갈라져 ΔT가 후속 단계에서 사라짐.
- DBSCAN 중복 실행, 대표 결과 재병합으로 `cluster_id_x/y` 생성, noise(-1)를 한 모듈로 합치는 문제.
- 중복 제거 CSV가 설정만 있고 실제 저장되지 않음.
- 원본 모듈 GeoJSON의 최종 분류가 항상 null로 저장됨.
- EXIF 방향 태그 16(기준 문자) 대신 17(방향 각도) 사용, Pillow 숫자형 GPS 처리.
- 북쪽 0도/시계 방향 heading에 맞게 카메라 좌표 회전 부호 수정.
- 좌표 숫자를 heading으로 오인하는 비정형 텍스트 추론 제거.
- RAW 온도 영역의 마지막 행/열 누락과 무한대 값 처리.
- SDK 프로세스 자체의 timeout 누락.
- 분류 입력 읽기 실패를 흰 이미지로 대체해 정상 결과처럼 저장하던 동작을 명시적 오류로 변경.
- 모델 백본의 불필요한 사전학습 다운로드 방지.
- 재실행 시 기존 결과 삭제 방지, 여러 촬영의 T/V 잘못된 매칭 및 동일 파일명 덮어쓰기 방지.
- 온도 계산을 bbox 기준에서 마스크 기준(`thermal.measure_module_raw`, RAW 네이티브 격자에서 커버리지 검증 후 집계)으로 교체. 배경 픽셀이 통계에 섞이는 문제를 줄임.
- `RESUME_RUN`이 `checkpoints.prepare_run()`과 연결되지 않아 아무 효과가 없던 문제 수정. 이제 입력/설정/코드가 이전 실행과 동일할 때만 기존 출력 폴더에 재실행을 허용합니다(그 외에는 여전히 빈 폴더가 필요).
- `geometry._gsd_from_fov_and_alt`가 import만 되고 실제로는 다른 공식으로 GSD를 중복 계산하던 것을 하나로 통일.
- `geometry.py`의 미사용 KDTree 기반 스냅 구현(`_geojson_to_module_points`/`_build_module_kdtree`/`snap_to_module`)과 이를 위해서만 쓰이던 중복 config 키(`MODULE_GEOJSON_PATH`, `MODULE_ID_KEYS`, `MODULE_SNAP_MAX_M`, `MODULE_SNAP_OVERRIDE`, `SNAPPED_POINTS_GEOJSON`, `SAVE_SNAPPED_POINTS_GEOJSON`, `MODULE_POINTS_GEOJSON_DEDUP`) 제거. 현재 스냅은 `catalog.py`/`MODULE_CATALOG_JSON` 경로만 사용합니다.
- `validate_inputs()`가 필수 입력만 검사하고 MRK/NAV/구역/모듈 카탈로그/정사영상 같은 선택적 입력은 검사하지 않아, 경로가 없으면 실행 중간에 조용히 기능이 꺼지던 문제 보완. 이제 시작 시점에 `[설정 경고]`로 알려줍니다.

## 검증 및 남은 제한

```powershell
python -m unittest discover -s tests -v
python -m compileall -q pv_inspector tests
```

실제 촬영 데이터, 학습 가중치, DJI SDK는 작업 폴더에 없으므로 실제 추론과 SDK 연동, 지도 브라우저 렌더링은 검증하지 못했습니다. 회귀 검증은 수치 처리/메타데이터/군집/스냅 등 코드 수준입니다.

- 고도 30m, 초점거리, 수직 촬영을 가정하는 근사 GPS입니다. 기체/짐벌 자세와 실제 AGL을 반영하지 않아 실측 모듈 위치와 오차가 날 수 있습니다.
- RAW 해상도는 바이트 수로 추론합니다. 가로/세로가 같은 픽셀 수인 경우 방향 판별이 불가능하므로 센서별 검증이 필요합니다.
- MRK/NAV 일반 텍스트 로더는 파일명이 포함된 보조 자료용입니다. 원시 DJI MRK의 프레임/시간 매칭을 완전 지원하지 않습니다.
- `ANALYZE_ON_INPUT_THERMAL`/`OVERLAY_ON_INPUT_THERMAL`은 예전 설정이며 현재 입력은 rJPG로 고정됩니다.
- `validate_inputs()`는 필수 입력(이미지 폴더/가중치/DJI SDK)만 없으면 오류로 막습니다. MRK/NAV/구역/모듈 카탈로그/정사영상처럼 선택적인 입력이 없을 때는 실행은 계속하되 시작 시점에 `[설정 경고]`로 어떤 기능이 비활성화되는지 알려줍니다.
- 대시보드는 외부 지도/JS와 상대 파일 경로를 사용합니다. 다른 드라이브의 이미지 경로나 브라우저 file:// 제한은 추가 점검이 필요합니다.
- HTML 템플릿과 이미지별 검출 루프는 기존 동작 비교를 위해 보존했습니다. 이번 분리는 기능 경계와 확인된 오류 수정에 초점을 맞췄습니다.

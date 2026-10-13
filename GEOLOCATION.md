# 위치 계산 개선

새 `geolocation.py`는 DJI XMP 위치/짐벌 자세와 원시 MRK 촬영 기록을 읽습니다.
`pipeline.py`에서 실제로 사용하며, 기존 이동 방향 추정은 위치 계산에서 제거했습니다.

- 위치 우선순위: 열화상 XMP → 열화상 EXIF → 촬영 번호/날짜/폴더가 맞는 MRK → RGB EXIF.
- MRK 좌표가 열화상 좌표보다 정확하다고 가정하지 않습니다. 카메라별 광학 중심 차이가 있을 수 있습니다. MRK 안테나 오프셋은 재적용하지 않습니다.
- 짐벌 yaw/pitch/roll을 NED 회전 행렬에 모두 반영하고 픽셀 광선과 수평면의 교점을 계산합니다.
- 자세가 없거나 광선이 수평에 가까우면 모듈 좌표는 비워 둡니다. 영상 검출/분류는 계속할 수 있습니다.
- 35mm 환산 초점거리의 대각선 환산, 중심 주점, 정사각 픽셀을 가정합니다. 기존 3:2 프레임의 세로 화각을 5:4 영상에 그대로 쓰던 계산을 대체했습니다. 센서별 내부 보정값은 아직 적용하지 않습니다.

## 높이 설정

기본값은 `ALT_AGL_M`(현재 30m)을 **카메라에서 패널 기준 수평면까지의 수직 높이**로 사용합니다.
실측된 값으로 조정해야 합니다. 상대고도를 쓰려면 JSON 설정에 다음을 추가합니다.

```json
{
  "GEO_USE_RELATIVE_ALTITUDE": true,
  "GEO_SURFACE_ABOVE_TAKEOFF_M": 0.0
}
```

이 경우 `RelativeAltitude - GEO_SURFACE_ABOVE_TAKEOFF_M`으로 계산합니다. 기준면 값은 이륙점 대비 패널 면 높이이며, 기본 0m가 현장에 맞는다는 뜻은 아닙니다. 경사면/지형 변화/패널 높이 차이는 여전히 반영하지 못합니다. 레이저 거리 필드는 자동 사용하지 않습니다.

## 결과 및 검증

마스터 CSV에 `geo_status`, `position_source`, `height_source`, `camera_to_surface_m`, 짐벌 세 각도, RTK flag, 연결된 MRK 위치/품질을 기록합니다. 계산 성공도 `approximate_flat_plane`으로 표시합니다. 명목 GSD/footprint 필드는 수직 촬영 기준이며 경사 촬영의 실제 footprint가 아닙니다.

`python audit_geolocation.py`로 모델 추론 없이 전체 T 이미지의 자세/촬영 번호 연결을 검사할 수 있습니다. 결과는 `results/geolocation_check/metadata_audit.csv`입니다.

방향·roll 180도·경사 촬영·수평 광선 제외·MRK 연결을 단위 테스트로 검증했습니다. 이는 수학적 일관성 검증입니다. **실제 패널 좌표 정확도, M4T XMP/영상 방향 일치, 렌즈 왜곡, 동일 패널의 다중 영상 일치까지 검증된 것은 아닙니다.** 수치 정확도 보장은 실측 기준점과 비교해야 합니다.

OBS/NAV/RTK를 이용한 PPK 처리는 이번 변경에 포함하지 않습니다. 예전 파일명 기반 CSV 보조 로더와 별도로 원시 MRK를 처리합니다.

참고 좌표계: https://developer.dji.com/doc/mobile-sdk-tutorial/en/basic-introduction/basic-concepts/flight-control.html
DJI PPK 절차: https://enterprise-insights.dji.com/blog/ppk-post-processed-kinematics-workflow

"""Prepare compact, traceable reference assets and operating instructions."""
from pathlib import Path
from PIL import Image, ImageOps
import shutil, csv
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan2_delivery'
refs=OUT/'ThreeJS/assets/reference'
refs.mkdir(parents=True,exist_ok=True)
for number in [5916,5934,5940]:
    image=ImageOps.exif_transpose(Image.open(Path('C:/3d')/f'IMG_{number}.JPG'))
    image.thumbnail((1600,1200))
    image.convert('RGB').save(refs/f'IMG_{number}.jpg',quality=90)
review=OUT/'Review'
review.mkdir(exist_ok=True)
for name in ['source_audit.md','photo_audit.md','layout_count_audit.json','array_layout_verified_overlay.png']:
    src=ROOT/'results/shinan2_review'/name
    if src.exists():shutil.copy2(src,review/name)
(OUT/'시작하기.txt').write_text('''신안2호기 — 도면·사진 기반 3D 검토 모델

1. 압축 파일을 폴더 전체로 풉니다.
2. ThreeJS/Shinan2_Viewer.html을 Chrome 또는 Edge로 엽니다.
   Python, Node.js, Blender를 설치할 필요가 없습니다. WebGL을 지원하는 브라우저가 필요합니다.
3. 전체 조망 / 배치도 / 모듈 가까이로 확인합니다.
4. 전기실 1 또는 2를 선택한 다음 현장 걷기를 누릅니다.
5. E 또는 문 열기 버튼으로 문을 열고 W/A/S/D로 안으로 이동합니다.
   화면을 누른 채 드래그하면 시선이 바뀝니다. Esc로 전체 조망으로 돌아갑니다.
6. 레이어 체크를 해제하면 지붕·모듈·지지대·장비 등을 개별적으로 숨깁니다.
7. 날짜와 시간 슬라이더로 현장 위치에 따른 그림자를 살펴봅니다.
8. 자료·모델 범위에서 실제 현장 사진과 모델의 추정 범위를 확인합니다.
9. GLB 저장은 현재 표시 중인 구성을 내보냅니다. Blender에서 glTF 2.0으로 가져올 수 있습니다.

근거: C:/3d의 2013.05 신안군 태양광 발전단지 2차 (5MW) 조성공사.pdf 및 IMG_5909–5943.
확인 수량: 245W 모듈 20,420장, 1,021그룹, 총 5,002.9kWp, 경사 22도.
전기실 1은 20.5×9.6m, 전기실 2는 18×9.6m입니다.

모델 상태와 한계:
- 스캔 도면 기반 근사 평면 위치입니다. 실측/CAD 좌표로 검증되지 않았습니다.
- 모듈 ID는 형상 ID이며 실제 모듈 일련번호 또는 회로 ID와 미대조 상태입니다.
- 외관·장비는 사진/도면을 참고했으나 세부 부품, 표면 상태, 문 동작 치수는 재구성입니다.
- 케이블 트레이는 실내 형상입니다. 실제 케이블 결선/회로 매칭은 검증되지 않았습니다.
- 지형은 평면 근사입니다. TIFF는 정사영상이며 지표면 높이 자료로 사용하지 않았습니다.
- 그림자는 태양 위치 근사에 따른 시각 표현입니다. 발전량·구조·안전 설계용 결과가 아닙니다.
- 화면의 계기/장비 표시는 정적 모델이며 실시간 운전 데이터가 아닙니다.
- AAA 품질 또는 준공 현장과의 완전한 일치를 인증한 결과물이 아닙니다.

기존 신안3호기 결과물과 분리된 신안2호기 전용 모델입니다.
''',encoding='utf-8-sig')
with (OUT/'module_catalog.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['viewer_shape_id','power_w','mapping_status'])
    for group in range(1,1022):
        for row in range(1,3):
            for module in range(1,11):w.writerow([f'S2-G{group:04d}-R{row}-M{module:02d}',245,'실물/회로 미대조'])
print('Reference assets, instructions, 20,420 shape IDs prepared.')

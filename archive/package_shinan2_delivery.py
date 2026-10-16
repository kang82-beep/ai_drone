"""Package only reviewed Shinan 2 delivery assets; no local app configuration."""
from pathlib import Path
import json, shutil, zipfile, hashlib
from PIL import Image, ImageStat
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan2_delivery'
REVIEW=ROOT/'results/shinan2_review'
checks=json.loads((REVIEW/'functional_suite.json').read_text(encoding='utf-8'))
assert all(r.get('passed',True) for r in checks), 'Browser checks failed'
images=['viewer_overview.png','viewer_room1.png','viewer_inside1.png','viewer_inside2.png','viewer_detail.png','cables_D31_to_grid.png','cables_B4213_special.png','cables_isolated.png','cables_lighting.png','cables_earthing.png']
screen_checks=[]
for name in images:
    with Image.open(REVIEW/name) as im:
        # Inspect the central scene, excluding UI. A missing postprocessing input
        # can leave a uniform viewport without producing a browser exception.
        crop=im.crop((360,150,im.width-70,im.height-120)).convert('RGB')
        variance=max(ImageStat.Stat(crop).var)
        assert variance>100, f'Blank or flat scene capture: {name}'
        screen_checks.append({'image':name,'scene_variance':variance})
        shutil.copy2(REVIEW/name,OUT/'Review'/name)
for name in ['functional_suite.json','visual_iteration1.md','visual_iteration2.md','blender_validation.json']:
    if (REVIEW/name).exists():shutil.copy2(REVIEW/name,OUT/'Review'/name)
(OUT/'Review/screenshot_validation.json').write_text(json.dumps(screen_checks,indent=2),encoding='utf-8')
(OUT/'Review/최신_개선사항.txt').write_text('''신안2호기 검토 모델 개선 사항

수량: 도면과 중첩 검증한 1,021그룹/20,420모듈.
전기실: 2개, 배전반·변압기·인버터 캐비닛 51개 세그먼트.
기능: 슬라이딩 문, 문/벽/장비 충돌, 경사로를 통한 실제 키보드 진입,
구성별 레이어, 모듈 형상 ID 검색, 날짜/시간별 태양과 그림자.
사진 대조 개선: 녹색 도장 바닥, 작은 체크 강판 무늬, 황색선,
H형 철골, 경사 인버터 덕트, 계기 눈금, 곡면 외벽 환기구,
사각 콘크리트 기초·C형강·가새·앵커·접지선.
주변: 도면 기반 외곽 도로/울타리와 간략한 바다·낮은 식생.
최적화: 정적 장비 메시 병합, 반복 구조물 인스턴싱.

기능 검증 결과는 functional_suite.json에 기록했습니다.
독립 시각 검토 2회에서 개선은 확인했으나 AAA 승인은 받지 못했습니다.
2차 지적 이후 강판 무늬 축척, 음영 반경, 계기 눈금, 곡면 환기구,
근거리 지면 텍스처를 추가 수정했습니다. 최종 화면은 주 작업자가 확인했습니다.
여전히 실제와 다른 세부 형상/재질/노후도, 스캔 기반 배치 오차가 남습니다.
주전력·보조전원·RS-485 도면 회로와 모듈 형상 ID 매칭을 추가했습니다.
접지·피뢰·조명·전열 연결표, CCTV 7개, 원격 맨홀 7개 연결을 추가했습니다.
위치 미확인 연결은 카드의 회로표로 표시하며 임의로 3D 포설선을 만들지 않습니다.
Electrical 폴더에서 결선 검증 범위와 원도면 불일치를 확인할 수 있습니다.
실물 제조 일련번호, 현장 케이블 연속성, 측량 기반 지형은 미확인입니다.
''',encoding='utf-8-sig')
if (OUT/'Models/Shinan2_Review.blend').exists() and 'Blender: Models/Shinan2_Review.blend' not in (OUT/'시작하기.txt').read_text(encoding='utf-8-sig'):
    with (OUT/'시작하기.txt').open('a',encoding='utf-8') as f:
        f.write('\nBlender: Models/Shinan2_Review.blend는 반복 부품을 Geometry Nodes로 구성한 정적 편집 모델입니다.\n문 개폐·보행·태양 시간 조절은 ThreeJS HTML에서 사용합니다.\nGLB는 교환용이며 많은 인스턴스를 개별 객체로 불러오는 프로그램에서는 느려질 수 있습니다. Blender에서는 제공된 .blend를 권장합니다.\n')
manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name!='manifest.json' and not p.name.endswith('.blend1'):
        manifest.append({'file':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
target=ROOT/'results/Shinan2_3D_Review_Package.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and not p.name.endswith('.blend1'):z.write(p,Path('Shinan2_3D')/p.relative_to(OUT))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
print(json.dumps({'package':str(target),'bytes':target.stat().st_size,'files':len(manifest)+1,'checks':sum('passed' in r for r in checks)},ensure_ascii=False))

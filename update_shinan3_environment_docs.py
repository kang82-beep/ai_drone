from pathlib import Path
import shutil,re
ROOT=Path(__file__).resolve().parent
p=ROOT/'shinan3_viewer/index.html';s=p.read_text(encoding='utf-8')
s=re.sub(r'<button id="environment".*?</button>','<button id="environment" aria-pressed="true" title="위성영상 참고 · 지형 높이는 추정">주변 환경 켜짐</button>',s)
s=s.replace('지표·재질·지지부 상세는 추정입니다.','주변 산림·해안은 간략 재현, 높이는 추정입니다.')
if '<b>주변 환경:</b>' not in s:
    s=s.replace('<li><b>제공 사진:</b>','<li><b>주변 환경:</b> VWorld 위성영상의 산림·농경지·도로·제방·갯벌을 간략하게 재현했습니다. 수목·높이·수심은 추정이며 지리 정합/측량 모델이 아닙니다. 주변 환경 버튼으로 숨길 수 있습니다. 보행 충돌은 기존 발전소의 평탄 지면·설비에만 적용합니다.</li><li><b>제공 사진:</b>')
s=s.replace('완공 설비 사진이 없습니다.','완공 설비 측면 사진은 없습니다. 추가 위성영상의 촬영일은 확인되지 않았습니다.')
p.write_text(s,encoding='utf-8')
p=ROOT/'shinan3_viewer/assets/source_reference.html';s=p.read_text(encoding='utf-8')
section='<h2>추가 위성영상과 주변 환경</h2><p>VWorld / NGII 위성영상에서 산림·농경지·제방·갯벌·진입로의 대략적 배치를 참고했습니다. 높이와 식생, 수심은 추정입니다. 지리 좌표 정합 또는 측량 지형이 아니며 주변 환경은 보행용 충돌 지형이 아닙니다. 위성영상 촬영일은 미확인입니다.</p><figure><img src="reference/plant_overview.jpg" loading="lazy"><figcaption>2026-10-03 조회 · VWorld / NGII. 조회 날짜와 촬영 날짜는 다릅니다.</figcaption></figure>'
if '<h2>추가 위성영상과 주변 환경</h2>' not in s:s=s.replace('</main>',section+'</main>')
p.write_text(s,encoding='utf-8')
shutil.copy2(ROOT/'results/shinan3_satellite/plant_overview.jpg',ROOT/'shinan3_viewer/assets/reference/plant_overview.jpg')
p=ROOT/'results/shinan3_delivery/README.md';s=p.read_text(encoding='utf-8')
section='\n## 주변 환경 추가 업데이트\n\nVWorld 위성영상을 참고한 간략 산림·구릉·농경지·진입로·제방·갯벌·수면을 추가했습니다. 뷰어의 **주변 환경 켜짐/꺼짐** 버튼으로 비교할 수 있습니다. 지형 높이·수목·수심은 시각화용 추정이며 측량 DEM이 아닙니다. 기존 보행 충돌은 발전소의 평탄 지면과 설비에만 적용되므로 주변 산림/해안 보행용 기능이 아닙니다. 전기실 지붕색도 영상에서 보이는 적갈색 계열로 조정했습니다.\n\nBlender에는 `12_Surrounding_Environment_ASSUMED` 컬렉션과 `Surroundings_Overview` 카메라를 추가했습니다. 해당 컬렉션을 숨기면 주변 환경을 끌 수 있습니다.\n'
if '## 주변 환경 추가 업데이트' not in s:s+=section
p.write_text(s,encoding='utf-8')

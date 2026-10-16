from pathlib import Path
import shutil,json,html
ROOT=Path(__file__).resolve().parent
src=ROOT/'shinan3_viewer/assets';refs=src/'reference'
for name in ['page_025.png','page_026.png','page_031.png','page_052.png','series_detail.png']:
 shutil.copy2(ROOT/'results/shinan3_cables'/name,refs/('cable_'+name))
content='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>신안 3호기 전기 연결 근거</title><style>body{font:16px/1.8 "Segoe UI","Malgun Gothic",sans-serif;background:#14232b;color:#dce5e0;margin:40px auto;max-width:1050px;padding:0 25px}a{color:#c9deb7}img{width:100%;background:white}h1,h2{font-weight:500}table{border-collapse:collapse;width:100%}td,th{border:1px solid #526568;padding:10px;text-align:left}small{color:#aebebb}.note{background:#604d262e;border-left:3px solid #b99959;padding:20px}</style><h1>전기도면 기반 케이블 3D</h1><p><a href="../index.html">3D 뷰어로 돌아가기</a></p><p>원본 준공도서 CAD의 모듈 배치, 스트링 평면, 접속반 병렬회로표, 전기실 기기 배치도와 Cable Schedule.xls를 대조했습니다. 원본 파일은 변경하지 않았습니다.</p><table><tr><th>항목</th><th>검증 및 구현 범위</th></tr><tr><td>모듈 → 스트링</td><td>30,000개 모듈을 1,500개 스트링에 20개씩 중복·누락 없이 대응. 기존 S3-G… ID 유지.</td></tr><tr><td>스트링 → 접속반 → 인버터</td><td>82개 접속반의 회로 수가 11240 병렬회로표와 일치. 인버터 15개. DC P/N 케이블 3,164개는 목록의 출발·도착과 일치.</td></tr><tr><td>AC·고압</td><td>양 끝 설비 위치가 있는 342개 항목의 단자 간 개략 연결. 실제 실내 트렌치·외부 고압 포설 경로의 확정 모델이 아님.</td></tr><tr><td>트레이·전선관</td><td>12210~12370 CAD에서 추출한 평면 도면선 2,193개. 높이·단면 형상은 추정이며 도면선은 개별 케이블 중심선이 아님.</td></tr><tr><td>나머지 목록</td><td>원본에서 출발·도착이 명시된 3,836개 항목을 검색 가능. 위치가 미확정인 330개는 3D로 그리지 않음. 원본 병합/공란 행을 임의로 채워 전체 전기회로가 완성됐다고 간주하지 않음.</td></tr></table><p class="note">연결 관계와 개별 물리 경로를 구분합니다. 모듈 간 점퍼는 11310 표준 직렬접속도에 따른 시각화이며 단자 위치·처짐은 추정입니다. 스트링 인출은 개략 배선, 접속반 간선은 트레이 도면선을 따라 계산한 추정 경로입니다. 목록의 경로 코드가 3D의 모든 분기와 일치하는지 검증된 것은 아닙니다. 화면 선의 길이는 목록상 케이블 길이를 대체하지 않으며 표시 굵기와 색은 식별용입니다. 굴착·포설·전기 안전 검토용 확정 모델이 아닙니다.</p><p>평면 정합은 각 상세 도면의 모듈 사각형을 원본 전체 배치에 맞춰 검증했습니다. 대부분 수치 오차 수준이며, 11450의 일부 모듈 배치는 전체 배치와 최대 0.20m, 12320은 최대 0.023m 차이가 있습니다. 원본 전체 배치와 ID를 보존했고 자료 간 차이를 숨기지 않았습니다. 도면·파일 개정이 다를 수 있으므로 첨부 PDF 이미지는 육안 비교 자료, 추출 형상과 회로 ID는 각 CAD 개정 파일이 기준입니다.</p>'''
for title,name in [('접속반 배치 · 11230','page_025.png'),('접속반별 병렬회로 · 11240','page_026.png'),('모듈 직렬회로 평면 · INV111 / 11320','page_031.png'),('트레이 평면 · INV111 / 12210','page_052.png'),('직렬접속 표준 · 11310','series_detail.png')]:
 content+=f'<h2>{title}</h2><img src="reference/cable_{name}" loading="lazy" alt="{title}">'
content+='<p><small>자료: C:\\3호기준공도서CD\\전기\\1. 도면. 도면·자료의 권리는 원자료 소유자에게 있습니다. 열화상 분석 결과 및 현장 실물 시리얼과는 별도이며 현재 미연결 상태입니다.</small></p></html>'
(src/'cable_reference.html').write_text(content,encoding='utf-8')
p=ROOT/'shinan3_viewer/index.html';s=p.read_text(encoding='utf-8');s=s.replace('<button id="cable-reset"','<p><a href="assets/cable_reference.html" target="_blank">케이블 구현 근거와 범위 ↗</a></p><button id="cable-reset"');p.write_text(s,encoding='utf-8')
p=ROOT/'results/shinan3_delivery/README.md';s=p.read_text(encoding='utf-8')
s+='''

## 전기도면 기반 케이블 보기

하단 **케이블 보기**를 누르면 전기 연결을 볼 수 있습니다. 기본 화면에서는 배선을 숨겨 발전소 외관을 유지합니다. 레이어에 전기 연결 6개 항목을 추가해 총 19개 레이어를 제공합니다.

1. 모듈 ID 검색 또는 패널 클릭 → **이 모듈의 연결 추적**: 스트링·접속반·인버터 연결을 확대합니다.
2. 케이블 번호 `D111A01 P`, `D111A00 N` 또는 스트링 ID `SM-111A01` 검색: 연결, 규격, 원본 목록상 길이, 경로 코드와 원본 행 번호 확인.
3. **선택한 연결만 표시**로 다른 배선을 숨기고, **레이어**에서 직렬 배선·DC 인출·DC 간선·AC/고압 개략선·트레이 도면선·전기설비를 각각 조작합니다.
4. **기본 조감도로 돌아가기**로 원래 외관을 복원합니다.

연결 확인 범위: 모듈 30,000개 → 스트링 1,500개 → 접속반 82개 → 인버터 15개. DC 3,164개 케이블의 출발·도착을 원본 목록과 대조했습니다. AC/고압 342개는 단자 간 개략 연결입니다. 위치 미확정 330개는 목록 조회만 가능합니다.

**개별 케이블 포설 형상·높이·굵기는 추정**입니다. 트레이 도면선은 원본 CAD 평면을 변환한 것이며, 개별 간선의 실제 경로가 모든 경로 코드와 일치하는지 확인된 것은 아닙니다. 목록상 길이와 3D 선 길이는 별개입니다. 선택선은 잘 보이도록 투시 표시하며 색은 실제 피복색이 아닙니다. 열화상 분석 연결 상태는 미연결로 유지됩니다.

Blender: `13_Electrical_Cables_DRAWING_AND_ASSUMED_Z` 컬렉션 아래 6종류로 분리했습니다. 기본은 숨김 상태입니다. Outliner에서 해당 컬렉션의 눈 아이콘을 켜서 확인하고, 렌더링하려면 카메라 표시도 켜세요. 개별 케이블 객체 이름은 원본 케이블 번호이며, Custom Properties에 출발·도착·규격·목록 길이·출처 행·추정 여부를 넣었습니다. `SM-…` 곡선에는 기존 모듈 ID 20개가 기록되어 있습니다. AC/고압선의 건물 내부 경로와 캐비닛 세부 형상은 단순화했습니다.

`Electrical/cable_model.json`은 양쪽 뷰어가 공유하는 전기 연결 데이터이며, `Electrical/*validation.json` 및 `Review/cables_browser_validation.json`에 검증 결과가 있습니다. 자세한 도면 근거는 뷰어의 **케이블 구현 근거와 범위** 링크에서 확인할 수 있습니다.
'''
p.write_text(s,encoding='utf-8')

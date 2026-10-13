from pathlib import Path
import json,csv,shutil
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan2_delivery';source=ROOT/'results/shinan2_cables'
(OUT/'References').mkdir(exist_ok=True)
shutil.copy2(next(Path('C:/3d').glob('*.pdf')),OUT/'References/Shinan2_Electrical_Drawings.pdf')
(OUT/'Electrical').mkdir(exist_ok=True)
mapping=json.loads((source/'circuit_map.json').read_text(encoding='utf-8'))
connections=json.loads((source/'source_connections.json').read_text(encoding='utf-8'))
schedule={j['jb']:j for j in connections['junction_box_schedule']}
assert mapping['report']['complete']
with (OUT/'module_catalog.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.writer(f);w.writerow(['viewer_shape_id','drawing_string_id','junction_box','inverter_input','inverter','diagram_page','slot_in_string','physical_serial_number','status'])
    rows=[]
    for s in mapping['strings']:
        for slot,index in enumerate(s['moduleIndices'],1):
            group=index//20+1;row=index%20//10+1;module=index%10+1
            rows.append((index,[f'S2-G{group:04d}-R{row}-M{module:02d}',s['id'],s['jb'],schedule[s['jb']]['inverter_input'],s['inverter'],s['page'],slot,'미제공','도면 소속 매칭 / 실물 연속성 미확인']))
    for _,row in sorted(rows):w.writerow(row)
for name in ['circuit_map.json','source_connections.json','cable_routes.json','secondary_systems.json','audit.md','de_mapping_notes.md','final_review.md']:
    if (source/name).exists():shutil.copy2(source/name,OUT/'Electrical'/name)
(OUT/'Electrical/결선_사용법과_검증범위.txt').write_text('''신안2호기 도면 기반 결선 모델

사용법
1. ThreeJS/Shinan2_Viewer.html을 Chrome/Edge에서 엽니다.
2. 전기 결선 메뉴에서 전체 결선 또는 회로만 보기를 선택합니다.
3. 모듈을 클릭하거나 SM-A1101, SM-D3101, JB-D31, INV-D1, VCB-5 등의 ID를 검색합니다.
4. 오른쪽 카드에서 스트링→접속반→인버터 입력→변압기→차단기→계통을 추적합니다.
5. 모듈 직렬/DC, 접속반→인버터, AC/22.9kV, 보조전원, RS-485, 트레이를 개별 표시합니다.
6. 원도면 링크는 References/Shinan2_Electrical_Drawings.pdf의 해당 페이지를 엽니다.

확인한 범위
- PDF22–26의 스트링 1,021개, PDF12의 접속반 60개와 전 모듈 20,420개를 누락/중복 없이 매칭.
- 실제 제조 일련번호는 자료에 없어 매칭하지 않았습니다. module_catalog.csv는 도면 위치 소속표입니다.
- 일반 스트링은 가로 20장입니다. 기존 2행×10장 구조 그룹과 일대일이 아닙니다.
- SM-B4213만 10+10 U자 연결입니다(PDF21).
- D31/32/33→입력D1, D11/12/13→D2, D21/22/23→D3를 반영했습니다(PDF12).
- PDF4/5 주전력·22.9kV·전기실 간 계통, PDF13 보조전원 회로 소속, PDF64 RS-485 순서를 반영했습니다.
- 접속반 위치 60개와 주요 트레이 38개는 PDF27–36에서 판독한 근사 좌표입니다.
- 실내 트레이 FL−250/FL+2600은 외부 지면 기준 Y0.25m/Y3.1m입니다.
- 접지·피뢰·조명·전열 등 162개 도면 연결 기록을 추가했습니다. 조명은 24/19개, 콘센트는 8/5개의 회로 부하표를 보존합니다.
- 조명·접지·CCTV·피뢰 선택 메뉴와 카드의 회로 종류 버튼으로 별도 연결을 확인합니다.
- 강전 ETT-P와 통신 ETT-J 접지를 분리했습니다. 모든 접지를 하나로 합치지 않았습니다.
- CCTV 7개와 영상/네트워크 연결을 추가했습니다. 형상과 포설 경로는 단순화했습니다.
- 전주201→MH07→MH06→MH05→MH04→MH03→MH02→MH01→전주163의 맨홀 연결과 도면 길이 합계1,320m를 보존합니다. 지리 위치는 미등록입니다.
- 조명·콘센트 부하 수는 도면 회로표 기준이며 개별 단자 위치와 모든 등기구의 정밀 형상을 뜻하지 않습니다.

도면과 재구성의 구분
- 회색 실선 트레이는 도면 경로를 근사한 것입니다. 점선 가지선은 장비 끝점을 연결하기 위해 재구성했습니다.
- 굵은 강조선은 선택 회로의 연결 설명입니다. 실제 포설 위치나 케이블 굵기를 나타내지 않습니다.
- 옥외 높이, 일부 가지선, 실내 기기 내부선, 원격 송전선의 실물 위치는 검증되지 않았습니다.
- 원격 전주202→201→163→안좌변전소는 연결 카드에 표시하고 임의 위치에 3D 전주를 만들지 않았습니다.
- p13 E4 보조전원 가지선은 도식의 D41/42/43과 부하표의 E41/42/43이 불일치합니다. 개별 결선을 확정하지 않았습니다.
- 보조전원 p4/5의1.16kVA, p13 MAIN1,800VA(예비 포함)도 미해결 차이로 원문을 유지합니다.
- p21의 P/N 단자 표기와 양극/음극 주석이 통상 명칭과 달라 P/N 원문만 유지합니다.
- 접지/피뢰·조명/전열의 개별 단자 결선 및 제조사 기기 내부 회로는 이 주전력/통신 추적표에서 인증하지 않습니다.
- 현장 개조 여부·케이블 양단 실측·단자대 번호·절연/연속성 시험 결과는 제공되지 않았습니다.

이 결과는 원도면의 회로 소속과 연결을 검토하는 3D 모델입니다.
실물 배선 공사 지시서, 구매용 케이블 길이 산출서 또는 현장 결선 검증서가 아닙니다.
''',encoding='utf-8-sig')
readme=OUT/'시작하기.txt'
text=readme.read_text(encoding='utf-8-sig')
text=text.replace('모듈 ID는 형상 ID이며 실제 모듈 일련번호 또는 회로 ID와 미대조 상태입니다.','모듈 형상 ID를 도면 스트링·접속반·인버터 입력에 매칭했습니다. 실물 제조 일련번호는 미제공입니다.')
text=text.replace('케이블 트레이는 실내 형상입니다. 실제 케이블 결선/회로 매칭은 검증되지 않았습니다.','주전력·보조전원·RS-485 회로 소속을 도면과 매칭했습니다. 가지선 위치·실물 연속성은 미검증이며 Electrical 폴더에 범위/불일치를 기록했습니다.')
readme.write_text(text,encoding='utf-8-sig')
print('Electrical records and original drawing PDF included; module catalog updated.')

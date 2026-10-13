from pathlib import Path
p=Path(__file__).parent/'shinan2_viewer/app.js'
s=p.read_text(encoding='utf-8')
s=s.replace("245W · 형상 ID / 회로 미대조';return id;","245W · 도면 회로 매칭';cableSystem.selectModule(index);return id;")
s=s.replace("e.preventDefault();const match=/^S2-G", "e.preventDefault();if(cableSystem.select($('search').value,true))return;const match=/^S2-G")
s=s.replace('window.__SHINAN2_QA__={layers,environment,','window.__SHINAN2_QA__={cableSystem,layers,environment,')
s=s.replace('형상 ID는 실제 회로 ID와 미대조 상태입니다.','형상 ID와 도면 스트링을 매칭했습니다. 실물 일련번호는 미확인입니다.')
s=s.replace('케이블 트레이는 실내 형상 표현이며 전기 회로의 실제 결선 검증은 완료되지 않았습니다.','모듈→접속반→인버터→계통 연결은 전기도면과 매칭했습니다. 3D 가지선·장비 내부 경로는 재구성이며 현장 케이블 연속성은 미검증입니다.')
p.write_text(s,encoding='utf-8')

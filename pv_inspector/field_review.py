"""Offline observation review; never treats missing measurements as normal."""
from __future__ import annotations

import argparse
import csv
from html import escape
import json
import math
from pathlib import Path


LABELS = {'normal': '정상', 'attention': '주의', 'abnormal': '이상'}


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def review_record(row, min_score=0.7, min_margin=0.15):
    """Scores are review heuristics, not calibrated diagnostic probabilities."""
    result = dict(row)
    reasons = []
    final = row.get('final')
    if final in ('abnormal', 'attention'):
        reasons.append('모델/온도 판정: ' + LABELS[final])
    elif final != 'normal':
        reasons.append('분류 결과 미확인')
    status = row.get('temperature_status')
    temps = [number(row.get(k)) for k in ('mean_temp', 'max_temp', 'delta_temp')]
    if status != 'ok' or any(v is None for v in temps):
        reasons.append('온도 품질 미확인' if not status or str(status) == 'nan' else '온도 확인 필요: ' + str(status))
    hold = str(row.get('reading_hold')).lower() == 'true'
    if hold:
        reasons.append('판독 보류: 일사량 기준 미달')
    if str(row.get('neighbor_flag')).lower() == 'true' and 'neighbor_delta' not in str(row.get('decision_reason')):
        reasons.append('주변 모듈 대비 고온')
    scores = [number(row.get('prob_' + k)) for k in LABELS]
    valid = all(v is not None and 0 <= v <= 1 for v in scores)
    valid = valid and abs(sum(scores) - 1) < 0.01
    top = margin = None
    if not valid:
        reasons.append('분류 점수 미확인')
    else:
        ordered = sorted(scores, reverse=True)
        top, margin = ordered[0], ordered[0] - ordered[1]
        if top < min_score:
            reasons.append('낮은 분류 점수')
        if margin < min_margin:
            reasons.append('분류 경계 사례')
    lat, lon = number(row.get('mod_lat')), number(row.get('mod_lon'))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        reasons.append('위치 미확인')
    result.update(review_required=bool(reasons), review_reason='; '.join(reasons),
                  review_priority=1 if final == 'abnormal' else (2 if reasons else 3),
                  model_top_score=top, model_margin=margin,
                  reviewer='', reviewed_label='', field_module_id='', review_notes='')
    return result


def _link(value, base):
    if not isinstance(value, str) or not value.strip():
        return ''
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve().as_uri() if path.is_file() else ''


def write_field_review(records, output, source_base=None, min_score=0.7, min_margin=0.15):
    if not 0 <= min_score <= 1 or not 0 <= min_margin <= 1:
        raise ValueError('Review thresholds must be between 0 and 1')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base = Path(source_base) if source_base else Path.cwd()
    rows = [review_record(r, min_score, min_margin) for r in records]
    rows.sort(key=lambda r: r['review_priority'])
    columns = list(dict.fromkeys(k for r in rows for k in r)) or ['image_id', 'module_id', 'review_reason', 'reviewer', 'reviewed_label', 'field_module_id', 'review_notes']
    # This is a blank review template; completed reviews should be saved separately.
    with (output / 'field_review_template.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            # Prevent spreadsheet formulas in imported filenames/labels.
            writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    cards = []
    for row in rows:
        e = lambda v: escape(str(v if v is not None else ''), quote=True)
        crop = _link(row.get('dst_path'), base) or _link(row.get('crop_path'), base)
        links = ''.join(f'<a href="{e(url)}" target="_blank" rel="noopener">{label}</a> ' for label, url in [
            ('크롭', crop), ('오버레이', _link(row.get('overlay_path'), base)),
            ('원본 열화상', _link(row.get('det_base'), base))] if url)
        image = f'<img loading="lazy" src="{e(crop)}" alt="모듈 크롭">' if crop else '<p>크롭 파일 없음</p>'
        fmt = lambda value: '미확인' if number(value) is None else f'{float(value):.2f}'
        cards.append(f'''<article data-review="{int(row['review_required'])}">
        {image}<div><h2>{e(row.get('image_id'))} / 모듈 {e(row.get('module_id'))}</h2>
        <p><b>{e('판독 보류' if row.get('final') == 'normal' and str(row.get('reading_hold')).lower() == 'true' else LABELS.get(row.get('final'), '미확인'))}</b> · {e(row['review_reason'] or '자동 검토 조건에 해당 없음')}</p>
        <p>최고 분류 점수 {fmt(row['model_top_score'])} · 점수 차이 {fmt(row['model_margin'])}<br>
        평균 {fmt(row.get('mean_temp'))} °C · 최고 {fmt(row.get('max_temp'))} °C · 모듈 내 ΔT {fmt(row.get('delta_temp'))} °C<br>
        주변 모듈 대비: 평균 {fmt(row.get('neighbor_delta_mean'))} °C · 최고 {fmt(row.get('neighbor_delta_max'))} °C ({e(row.get('neighbor_delta_status') or '기존 결과: 미계산')})</p>
        <p>온도 상태: {e(row.get('temperature_status') or '기존 결과: 품질 정보 없음')}<br>
        위치 상태: {e(row.get('geo_status') or '미확인')} · 설비 후보 ID: {e(row.get('module_uid') or row.get('snap_mid'))}<br>
        판정 근거: {e(row.get('decision_reason') or '기존 결과: 근거 기록 없음')}</p>{links}</div></article>''')
    count = sum(r['review_required'] for r in rows)
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>태양광 현장 검토표</title><style>
    body{font:16px system-ui,sans-serif;background:#f0f4f8;color:#152c40;margin:24px auto;max-width:1180px;padding:0 16px}
    header{background:#16354a;color:white;padding:24px;border-radius:12px}h1{margin-top:0}h2{font-size:16px;overflow-wrap:anywhere}
    article{display:flex;gap:22px;background:white;padding:20px;margin:14px 0;border-radius:10px;border:1px solid #cbd5df}
    img{width:160px;height:160px;object-fit:contain;background:#172330}article div{flex:1}a{color:#08798b;margin-right:12px}
    input[type=search]{padding:12px;width:55%;margin:18px 10px 8px 0} [hidden]{display:none!important}
    @media(max-width:600px){article{display:block}img{width:100%}}
    </style><header><h1>태양광 현장 검토표</h1>'''
    condition = {'ok': '일사량 기준 충족', 'low_irradiance': '일사량 기준 미달 — 정상 판정은 판독 보류',
                 'irradiance_unrecorded': '일사량 미기록 — 촬영 조건 적합 여부를 확인할 수 없음'}.get(
                     rows[0].get('capture_condition') if rows else None, '촬영 조건 기록 없음')
    html += f'<p>관측 {len(rows)}건 · 검토 대상 {count}건 (동일 설비의 중복 촬영 포함)<br>촬영 조건: {condition}</p></header>'
    html += f'''<p>ΔT는 해당 모듈 내부의 최고−평균 온도입니다. 분류 점수는 진단 정확도를 뜻하지 않습니다.
    검토 기준: 최고 점수 &lt; {min_score:g}, 상위 두 점수 차이 &lt; {min_margin:g}. 현장 검증 전 임시 기준입니다.</p>
    <p>위치는 근사 좌표일 수 있습니다. 원본·오버레이와 실제 설비 ID를 대조하세요. 미검출 모듈은 이 표에 나타나지 않습니다.</p>
    <p><a href="field_review_template.csv" download>검수 CSV 양식 다운로드</a>검수자·정답(normal/attention/abnormal)·실제 설비 ID·메모를 입력하고 다른 이름으로 저장하세요.</p>
    <input id="query" type="search" placeholder="촬영명, 모듈 ID, 사유 검색" aria-label="검색">
    <label><input id="only" type="checkbox" checked>검토 대상만</label><span id="count"></span><main>'''
    html += ''.join(cards) if rows else '<p>검출 관측이 없습니다. 정상 판정을 의미하지 않습니다. 입력 영상과 검출 로그를 확인하세요.</p>'
    html += '''</main><script>
    const query=document.getElementById('query'), only=document.getElementById('only');
    function filter(){let n=0;document.querySelectorAll('article').forEach(a=>{
      a.hidden=(only.checked&&a.dataset.review!=='1')||!a.textContent.toLowerCase().includes(query.value.toLowerCase());
      if(!a.hidden)n++;});document.getElementById('count').textContent=' 표시 '+n+'건';}
    query.addEventListener('input',filter);only.addEventListener('change',filter);filter();
    </script></html>'''
    path = output / 'field_review.html'
    path.write_text(html, encoding='utf-8')
    (output / 'field_review_summary.json').write_text(json.dumps({
        'observations': len(rows), 'review_required': count,
        'min_score': min_score, 'min_margin': min_margin,
        'scope': 'observations_not_unique_modules'}, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description='기존 마스터 CSV에서 현장 검토표 생성 (모델 실행 없음)')
    parser.add_argument('--master', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-base', help='CSV 상대 이미지 경로의 기준 폴더 (기본: 현재 폴더)')
    parser.add_argument('--min-score', type=float, default=0.7)
    parser.add_argument('--min-margin', type=float, default=0.15)
    args = parser.parse_args()
    with Path(args.master).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    print(write_field_review(rows, args.output, args.source_base, args.min_score, args.min_margin))


if __name__ == '__main__':
    main()

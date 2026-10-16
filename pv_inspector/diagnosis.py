"""Rule-based cause candidates for flagged modules (과제_기획서 4.4).

Every flagged module gets cause candidates from the knowledge base, each with the
evidence it rests on (which frame, which number) and a confidence. Rules always run;
the LLM step (llm_agent.py) only adds to them and never removes a warning.
Deciding whether a module is a candidate stays with the verdict rules; this module
only explains it.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

KB_PATH = Path(__file__).with_name('data') / 'knowledge_base.json'
WIDE_UNIT_C = 2.0        # a junction box or inverter this much above its peers is hot as a whole
WIDE_UNIT_MIN_MODULES = 40
PID_END = 5              # modules counted as one end of a string
PID_MIN_MODULES = 3
SOILING_DARK_SHARE = 0.5
TYPE_LABEL = {'single_cell': '단일 셀 핫스팟', 'multi_cell': '다중 셀 핫스팟', 'diode': '바이패스 다이오드 띠',
              'whole_module': '모듈 전체 발열', 'low_edge_band': '하단 띠', 'high_edge_band': '상단 띠',
              'partial_shade': '부분 그늘', 'none': '뚜렷한 패턴 없음'}


def load_kb(path=KB_PATH):
    kb = json.loads(Path(path).read_text(encoding='utf-8'))
    kb['by_rule'] = {r['rule']: r for r in kb['rules']}
    return kb


def frame_no(image_id):
    parts = str(image_id).split('_')
    return parts[2] if len(parts) > 2 else str(image_id)


def unit_flags(verdicts):
    """Junction boxes and inverters whose modules run hot as a whole (4.2 wide comparison)."""
    v = verdicts.dropna(subset=['relative_temp'])
    jb = v.groupby(['inverter_id', 'jb_id']).agg(mean=('relative_temp', 'mean'), n=('relative_temp', 'size')).reset_index()
    jb['peer'] = jb.groupby('inverter_id')['mean'].transform('median')
    jb_hot = {r.jb_id: r.mean - r.peer for r in jb.itertuples()
              if r.n >= WIDE_UNIT_MIN_MODULES and r.mean - r.peer >= WIDE_UNIT_C}
    inv = v.groupby('inverter_id').agg(mean=('relative_temp', 'mean'), n=('relative_temp', 'size'))
    site = inv['mean'].median()
    inv_hot = {k: r['mean'] - site for k, r in inv.iterrows() if r['n'] >= WIDE_UNIT_MIN_MODULES and r['mean'] - site >= WIDE_UNIT_C}
    return jb_hot, inv_hot


def string_positions(cable_model):
    """{module_id: (string_id, index, length)} in wiring order."""
    out = {}
    for s in (cable_model or {}).get('strings', []):
        for i, m in enumerate(s['modules']):
            out[m] = (s['id'], i, len(s['modules']))
    return out


def pid_strings(flagged_ids, positions):
    """Strings where three or more flagged modules sit at the same end (PID starts at one pole)."""
    by_string = {}
    for m in flagged_ids:
        if m in positions:
            sid, i, n = positions[m]
            by_string.setdefault(sid, []).append((i, n))
    hits = set()
    for sid, items in by_string.items():
        head = sum(i < PID_END for i, n in items)
        tail = sum(i >= n - PID_END for i, n in items)
        if max(head, tail) >= PID_MIN_MODULES:
            hits.add(sid)
    return hits


def module_observations(module_id, patterns, linked):
    """Usable flagged views of one module with the numbers the evidence cites."""
    p = patterns[patterns['module'] == module_id]
    rows = []
    for r in p.to_dict('records'):
        key = (r['image_id'], int(r['module_id']))
        extra = linked.get(key, {})
        rows.append(dict(image_id=r['image_id'], final=r['final'], edge=bool(r['edge']), type=r['type'],
                         shadow=str(r.get('shadow_suspect')) == 'True', dark=_num(r.get('hot_on_rgb_dark')),
                         delta=_num(extra.get('neighbor_delta_mean')), max_temp=_num(extra.get('max_temp'))))
    return rows


def _num(value):
    try:
        out = float(value)
        return None if np.isnan(out) else out
    except (TypeError, ValueError):
        return None


def _cite(o, text):
    return {'text': f"프레임 {frame_no(o['image_id'])}: {text}", 'ref': o['image_id']}


def flagged_views(observations):
    return [o for o in observations if o['final'] != 'normal' and not o['edge']] or [o for o in observations if o['final'] != 'normal']


def main_type(observations):
    """Most frequent thermal pattern over the module's usable flagged views, and how often."""
    types = Counter(o['type'] for o in flagged_views(observations) if o['type'] != 'none')
    return types.most_common(1)[0] if types else ('none', 0)


def diagnose_module(row, observations, kb, string_hot, jb_hot, inv_hot, pid_hit):
    """Cause candidates for one flagged module, primary first."""
    rule = kb['by_rule']
    flagged = flagged_views(observations)
    main, count = main_type(observations)
    consistent = count >= 2
    votes, views = int(row.get('flagged_votes') or 0), int(row.get('usable_views') or 0)
    shadow = any(o['shadow'] for o in flagged)
    dark = max([o['dark'] for o in flagged if o['dark'] is not None] or [0])
    picks = []

    def add(name, confidence, evidence):
        picks.append(dict(rule=name, cause=rule[name]['cause'], action=rule[name]['action'], urgency=rule[name]['urgency'],
                          kind=rule[name]['kind'], safety=bool(rule[name].get('safety')), confidence=confidence, evidence=evidence))

    if row.get('inverter_id') in inv_hot:
        add('inverter_wide', '중간', [{'text': f"{row['inverter_id']} 전체 모듈 평균이 다른 인버터보다 {inv_hot[row['inverter_id']]:+.1f}℃", 'ref': row['inverter_id']}])
    if row.get('jb_id') in jb_hot:
        add('jb_wide', '중간', [{'text': f"{row['jb_id']} 모듈 평균이 같은 인버터의 다른 접속반보다 {jb_hot[row['jb_id']]:+.1f}℃", 'ref': row['jb_id']}])
    if row.get('string_id') in string_hot:
        add('string_wide', '높음', [{'text': f"{row['string_id']} 평균이 이웃 스트링보다 {string_hot[row['string_id']]:+.1f}℃", 'ref': row['string_id']}])

    by_type = [_cite(o, f"{TYPE_LABEL.get(o['type'], o['type'])}, 주변 대비 {o['delta']:+.1f}℃" if o['delta'] is not None
                     else TYPE_LABEL.get(o['type'], o['type'])) for o in flagged[:4]]
    confidence = '높음' if votes >= 2 and consistent else ('중간' if votes >= 2 or consistent else '낮음')
    if votes == 1 and views >= 3 and not picks:
        add('reflection', '중간', [{'text': f"{views}회 촬영 중 1회만 이상 (반사는 프레임마다 위치가 바뀜)", 'ref': row['drawing_module_id']}] + by_type[:1])
    if main == 'diode':
        add('diode', confidence, by_type)
    elif main == 'whole_module':
        add('whole_module', confidence, by_type)
    elif main == 'low_edge_band':
        add('vegetation' if shadow else 'edge_band_high', confidence, by_type)
    elif main == 'partial_shade' or (shadow and main == 'none'):
        add('structure_shade', confidence, by_type)
    elif main in ('single_cell', 'multi_cell'):
        if dark >= SOILING_DARK_SHARE:
            add('soiling', confidence, by_type + [{'text': f"발열 영역의 {dark:.0%}가 가시광에서 어두운 곳과 겹침", 'ref': flagged[0]['image_id']}])
        add('cell_defect', '중간' if dark >= SOILING_DARK_SHARE else confidence, by_type)
    elif main == 'high_edge_band':
        add('edge_band_high', confidence, by_type)
    # Views disagree and one looks shaded: the shade stays on the list, and the electrical reading weakens.
    shade_rules = ('vegetation', 'structure_shade', 'soiling')
    if shadow and not any(p['rule'] in shade_rules for p in picks) and len({o['type'] for o in flagged if o['type'] != 'none'}) > 1:
        for p in picks:
            if p['kind'] in ('electrical', 'field_check') and p['confidence'] == '높음':
                p['confidence'] = '중간'
        add('structure_shade', '중간', [_cite(o, '그림자 의심 관측') for o in flagged if o['shadow']][:2])
    if pid_hit:
        add('pid', '낮음', [{'text': f"{row['string_id']}의 셀 핫스팟 모듈 {PID_MIN_MODULES}장 이상이 스트링 한쪽 끝 {PID_END}장 안에 몰려 있음", 'ref': row['string_id']}])
    if not picks or all(p['rule'] in ('reflection', 'pid') for p in picks) and main == 'none':
        add('unknown', '낮음', by_type or [{'text': '뚜렷한 열 패턴이 없음', 'ref': row['drawing_module_id']}])

    if row.get('only_untrusted') in (True, 'True'):
        for p in picks:
            p['confidence'] = '낮음'
    order = {'높음': 0, '중간': 1, '낮음': 2}
    picks.sort(key=lambda p: (not p['safety'], p['rule'] == 'unknown', order[p['confidence']]))
    primary = picks[0]
    return dict(module_id=row['drawing_module_id'], string_id=row.get('string_id'), jb_id=row.get('jb_id'),
                inverter_id=row.get('inverter_id'), verdict=row.get('verdict'), anomaly_type=main,
                source='rule', candidates=picks, primary=primary['cause'], action=primary['action'],
                urgency=primary['urgency'], kind=primary['kind'], safety=any(p['safety'] for p in picks),
                exclude=primary['kind'] == 'exclude',
                needs_review=primary['confidence'] == '낮음' or primary['rule'] == 'unknown',
                appearance=None, views=views, votes=votes, relative_temp=_num(row.get('relative_temp')),
                east_m=_num(row.get('east_m')), north_m=_num(row.get('north_m')))


def diagnose(verdicts, strings, patterns, linked, cable_model=None, kb=None, skip_images=()):
    """Diagnoses for every inspect/recheck module; views from `skip_images` (turn frames) are not evidence."""
    kb = kb or load_kb()
    flagged = verdicts[verdicts['verdict'].isin(['inspect', 'recheck'])]
    if len(skip_images):
        patterns = patterns[~patterns['image_id'].isin(set(skip_images))]
    string_hot = {r.string_id: r.string_delta for r in strings.itertuples() if str(r.string_flag) == 'True'}
    jb_hot, inv_hot = unit_flags(verdicts)
    positions = string_positions(cable_model)
    lookup = {(r['image_id'], int(r['module_id'])): r for r in linked.to_dict('records')}
    records = flagged.to_dict('records')
    views = {r['drawing_module_id']: module_observations(r['drawing_module_id'], patterns, lookup) for r in records}
    cells = {m for m, obs in views.items() if main_type(obs)[0] in ('single_cell', 'multi_cell')}
    pid = pid_strings(cells, positions)
    out = []
    for row in records:
        pos = positions.get(row['drawing_module_id'])
        at_end = pos is not None and (pos[1] < PID_END or pos[1] >= pos[2] - PID_END)
        hit = row.get('string_id') in pid and at_end and row['drawing_module_id'] in cells
        out.append(diagnose_module(row, views[row['drawing_module_id']], kb, string_hot, jb_hot, inv_hot, hit))
    return out


def summary(diagnoses):
    return dict(modules=len(diagnoses),
                primary=pd.Series([d['primary'] for d in diagnoses]).value_counts().to_dict() if diagnoses else {},
                needs_review=sum(d['needs_review'] for d in diagnoses),
                excluded=sum(d['exclude'] for d in diagnoses),
                safety=sum(d['safety'] for d in diagnoses))

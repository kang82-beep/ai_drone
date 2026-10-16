"""Cause estimation, priority and draft work orders for one flight; stored in the history DB.

Reads the verdicts, anomaly patterns and linked observations of a flight, writes
diagnoses.json / orders.json under --output and replaces the flight's draft orders in
results/history.db (issued orders and field results are kept).
The LLM review runs only with --llm-model, --llm-send and OPENAI_API_KEY in the environment.
"""
import argparse
import json
import re
from pathlib import Path

SECRET = re.compile(r'(sk-|key[=:]\s*)[A-Za-z0-9_\-*]{4,}', re.IGNORECASE)

import pandas as pd

from export_web_data import local, rgb_crop
from pv_inspector import config, history
from pv_inspector.diagnosis import diagnose, load_kb, summary
from pv_inspector.llm_agent import Agent, anon_id, available, clean_jpeg, evidence_items, load_salt, merge
import copy
import hashlib

from pv_inspector.work_orders import FIELD_KINDS, build, loss_w, priority_key, work_kind

ROOT = Path(__file__).resolve().parent


def flight_id_of(linked):
    """Capture date and start time of the flight, e.g. 20251030-0911."""
    first = sorted(linked['image_id'].dropna().astype(str))[0]
    found = re.search(r'DJI_(\d{8})(\d{4})', first)
    return f'{found[1]}-{found[2]}' if found else first


def crops_for(diagnosis, linked, alignment, cache, skip=frozenset()):
    """Thermal + visible crop of the module's strongest usable view (never a turn frame), metadata stripped."""
    rows = linked[(linked['drawing_module_id'] == diagnosis['module_id']) & ~linked['image_id'].isin(skip)]
    if rows.empty:
        return []
    rows = rows.sort_values('neighbor_delta_mean', ascending=False)
    item = rows.iloc[0]
    images = []
    thermal = local(item['dst_path'])
    thermal = thermal if thermal.is_file() else local(item['crop_path'])
    data = clean_jpeg(thermal) if thermal.is_file() else None
    if data:
        images.append(('열화상 크롭', data))
    if alignment and isinstance(item.get('rgb_path'), str):
        target = cache / f"{item['image_id']}_{item['module_id']}.jpg"
        if rgb_crop(local(item['rgb_path']), [item['bbox_x1'], item['bbox_y1'], item['bbox_x2'], item['bbox_y2']],
                    alignment['fixed_thermal_to_rgb'], target):
            data = clean_jpeg(target)
            if data:
                images.append(('가시광 크롭 (주변 포함)', data))
    return images


def review_key(d, model):
    """Same evidence → same review: the reply is reused instead of sending the crops again."""
    text = json.dumps([model, d['verdict'], d['anomaly_type'], sorted(t for _, t in evidence_items(d))], ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def load_cache(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def seed_cache(path, previous, model):
    """Rebuild the reply cache from an earlier diagnoses.json that already holds merged reviews."""
    cache = load_cache(path)
    for d in previous:
        if not str(d.get('source', '')).startswith(f'rule+llm:{model}'):
            continue
        causes = [dict(cause=c['cause'], confidence=c['confidence'], evidence=c.get('llm_evidence') or [], reason=c['llm_reason'])
                  for c in d['candidates'] if c.get('llm_reason')]
        rule_view = dict(d, candidates=[c for c in d['candidates'] if 'rule' in c and c.get('evidence')] or d['candidates'])
        if causes:
            cache.setdefault(d['module_id'], {})[review_key(rule_view, model)] = dict(
                appearance=d['appearance'], causes=causes, action=d['action'], urgency=d['urgency'], needs_review=d['needs_review'])
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')
    return cache


def review_with_llm(diagnoses, linked, alignment, kb, flight, db, model, limit, output, skip=frozenset()):
    agent = Agent(model)
    cache_path = output / 'llm_cache.json'
    cache = load_cache(cache_path)
    reused = 0
    salt = load_salt(ROOT / 'results' / 'llm_salt.txt')
    reviewed = 0
    for d in diagnoses:
        d['loss_w'] = loss_w(d, kb)  # the review order follows the work-order priority
    # Only modules the rules would send to the field: the review is there to save field visits.
    field = [(i, d) for i, d in enumerate(diagnoses) if work_kind(copy.deepcopy(d), kb) in FIELD_KINDS]
    for i, d in sorted(field, key=lambda t: (t[1]['verdict'] != 'inspect', priority_key(t[1])))[:limit]:
        token = anon_id(d['module_id'], salt)
        key = review_key(d, model)
        stored = cache.get(d['module_id'], {}).get(key)
        if stored:
            diagnoses[i] = merge(d, stored, kb, model)
            reviewed += 1; reused += 1
            continue
        images = crops_for(d, linked, alignment, output / 'rgb_crops', skip)
        if not any(name.startswith('열화상') for name, _ in images):
            history.log_llm(db, flight, token, d['module_id'], model, False, 'skipped: thermal crop unreadable')
            continue  # a review without the thermal view would rest on the visible image alone
        try:
            review = agent.review(d, kb, images)
        except Exception as error:  # network, quota: keep the rule result and go on
            # API errors can quote part of the key: never let it reach the log.
            history.log_llm(db, flight, token, d['module_id'], model, False, SECRET.sub(r'***', f'{type(error).__name__}: {error}')[:300])
            continue
        history.log_llm(db, flight, token, d['module_id'], model, review is not None, '' if review else 'invalid reply')
        if review:
            diagnoses[i] = merge(d, review, kb, model)
            reviewed += 1
            cache.setdefault(d['module_id'], {})[key] = review
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding='utf-8')  # survive a stop
    print(f'GPT 보강 {reviewed}건 (저장된 응답 재사용 {reused}건, 새로 전송 {reviewed - reused}건)', flush=True)
    return reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', default='results/shinan3_full_20261030/reg')
    parser.add_argument('--verdicts', default='results/module_verdicts')
    parser.add_argument('--patterns', default='results/anomaly_patterns/anomaly_patterns.csv')
    parser.add_argument('--cable-model', default='results/shinan3_cables/cable_model.json')
    parser.add_argument('--alignment', default='results/ir_rgb_alignment/alignment.json')
    parser.add_argument('--db', default='results/history.db')
    parser.add_argument('--output', default='results/orders')
    parser.add_argument('--flight', help='비행 이름 (기본: 첫 촬영 시각)')
    parser.add_argument('--llm-model', default=config.LLM_MODEL)
    parser.add_argument('--llm-send', action='store_true', default=config.LLM_SEND_IMAGES, help='크롭을 외부 LLM으로 보낸다')
    parser.add_argument('--llm-max', type=int, default=config.LLM_MAX_MODULES)
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)

    verdicts = pd.read_csv(Path(args.verdicts) / 'module_verdicts.csv', encoding='utf-8-sig', low_memory=False)
    strings = pd.read_csv(Path(args.verdicts) / 'string_verdicts.csv', encoding='utf-8-sig')
    patterns = pd.read_csv(args.patterns, encoding='utf-8-sig', low_memory=False)
    linked = pd.read_csv(Path(args.registration) / 'master_linked.csv', encoding='utf-8-sig', low_memory=False,
                         usecols=['image_id', 'module_id', 'drawing_module_id', 'neighbor_delta_mean', 'max_temp', 'dst_path',
                                  'crop_path', 'rgb_path', 'bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2'])
    cable = json.loads(Path(args.cable_model).read_text(encoding='utf-8-sig')) if Path(args.cable_model).is_file() else None
    alignment = json.loads(Path(args.alignment).read_text(encoding='utf-8')) if Path(args.alignment).is_file() else None
    flight = args.flight or flight_id_of(linked)
    kb = load_kb()
    turn_path = Path(args.verdicts) / 'turn_frames.json'
    turning = frozenset(json.loads(turn_path.read_text(encoding='utf-8'))) if turn_path.is_file() else frozenset()
    retake = verdicts.loc[verdicts['verdict'] == 'retake', 'drawing_module_id'].tolist()

    db = history.connect(args.db)
    types = {}
    diagnoses = diagnose(verdicts, strings, patterns, linked, cable, kb, skip_images=turning)
    reviewed = 0
    rule_field = sum(work_kind(copy.deepcopy(d), kb) in FIELD_KINDS for d in diagnoses)
    if available(args.llm_model, args.llm_send):
        reviewed = review_with_llm(diagnoses, linked, alignment, kb, flight, db, args.llm_model, args.llm_max, output, turning)
    for d in diagnoses:
        types[d['module_id']] = d['anomaly_type']
    times = sorted(linked['image_id'].dropna().astype(str))
    history.import_flight(db, flight, Path(args.registration).parent, verdicts.to_dict('records'), types, times[0], times[-1])
    orders, safety = build(diagnoses, kb, flight, viewer_link=lambda m: f'viewer/Shinan3_Viewer.html?module={m}', retake=retake)
    history.save_diagnoses(db, flight, diagnoses)
    history.save_orders(db, flight, orders)
    report = dict(flight_id=flight, diagnosis=summary(diagnoses), llm_reviewed=reviewed,
                  llm='off' if not available(args.llm_model, args.llm_send) else args.llm_model,
                  field_modules_rules_only=rule_field,
                  ai_downgraded=sum(bool(d.get('ai_downgraded')) for d in diagnoses),
                  ai_audit_samples=sum(bool(d.get('ai_audit')) for d in diagnoses),
                  orders=len(orders), field_modules=sum(len(o['modules']) for o in orders if o['action_kind'] not in ('recheck', 'reshoot', 'retake')),
                  recheck_modules=sum(len(o['modules']) for o in orders if o['action_kind'] == 'recheck'),
                  retake_modules=len(retake), turn_frames=len(turning),
                  safety_notify=safety, comparison=pd.Series(history.compare(db, flight)).value_counts().to_dict(),
                  knowledge_base=kb['version'])
    (output / 'diagnoses.json').write_text(json.dumps(diagnoses, ensure_ascii=False, indent=1), encoding='utf-8')
    (output / 'orders.json').write_text(json.dumps(orders, ensure_ascii=False, indent=1), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if safety:
        print(f'[즉시 통보] 안전 위험 모듈 {len(safety)}장: ' + ', '.join(safety[:20]))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

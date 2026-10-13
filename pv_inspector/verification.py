"""Field-verification sample and scoring. Model output is never used as truth.

sample: every flagged unit plus a seeded, evenly spread sample of units the
program called normal, so missed defects can be estimated, not only false alarms.
score: reads the sheet after the site crew filled `reviewed_label`.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

from .field_review import review_record, write_field_review

TRUTH = ('normal', 'attention', 'abnormal')
RANK = {'abnormal': 0, 'attention': 1}


def _read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def _is_hold(row):
    return str(row.get('reading_hold')).lower() == 'true'


def build_sample(rows, normals=250, seed=20261012, unit_column=None):
    """One row per unit; a unit is flagged if any of its observations is."""
    units = {}
    for index, row in enumerate(rows):
        key = (row.get(unit_column) or '').strip() if unit_column else ''
        units.setdefault(key or f'observation:{index}', []).append(row)
    flagged, normal = [], []
    for key, group in units.items():
        group.sort(key=lambda r: RANK.get(r.get('final'), 2))
        best = dict(group[0], verification_unit=key, unit_observations=len(group))
        (flagged if best.get('final') != 'normal' else normal).append(best)
    normal.sort(key=lambda r: (str(r.get('image_id')), str(r.get('module_id'))))
    count = min(normals, len(normal))
    picked = []
    if count:
        step = len(normal) / count
        start = random.Random(seed).random() * step
        picked = [normal[int(start + i * step)] for i in range(count)]
    out = []
    for stratum, group, weight in (('flagged', flagged, 1.0), ('normal_sample', picked, len(normal) / count if count else 0.0)):
        for row in group:
            out.append(dict(review_record(row), sample_stratum=stratum, sampling_weight=weight))
    summary = dict(units=len(units), flagged_units=len(flagged), normal_units=len(normal),
                   normal_sampled=count, seed=seed, unit_column=unit_column or 'observation',
                   reading_hold_units=sum(_is_hold(r) for r in flagged + normal))
    return out, summary


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def score(rows):
    """False-alarm and miss rates from reviewed rows only; unreviewed rows are reported, not assumed."""
    reviewed = [r for r in rows if (r.get('reviewed_label') or '').strip().lower() in TRUTH]
    result = dict(rows=len(rows), reviewed=len(reviewed), unreviewed=len(rows) - len(reviewed))
    defect = lambda r: r['reviewed_label'].strip().lower() != 'normal'
    flagged = [r for r in reviewed if r.get('sample_stratum') == 'flagged']
    normal = [r for r in reviewed if r.get('sample_stratum') == 'normal_sample']
    false_alarm = sum(not defect(r) for r in flagged)
    missed = sum(defect(r) for r in normal)
    result['flagged'] = dict(reviewed=len(flagged), confirmed_defect=len(flagged) - false_alarm, false_alarm=false_alarm,
                             false_alarm_rate=false_alarm / len(flagged) if flagged else None,
                             false_alarm_rate_ci95=wilson(false_alarm, len(flagged)))
    result['normal_sample'] = dict(reviewed=len(normal), missed_defect=missed,
                                   miss_rate_among_normal=missed / len(normal) if normal else None,
                                   miss_rate_ci95=wilson(missed, len(normal)))
    weight = lambda r: float(r.get('sampling_weight') or 0)
    total_flagged = sum(r.get('sample_stratum') == 'flagged' for r in rows)
    total_normal = sum(weight(r) for r in rows if r.get('sample_stratum') == 'normal_sample')
    if flagged and normal:
        found = (len(flagged) - false_alarm) / len(flagged) * total_flagged
        lost = missed / len(normal) * total_normal
        result['estimated'] = dict(defects_found=found, defects_missed=lost,
                                   detection_rate=found / (found + lost) if found + lost else None,
                                   note='표본에서 추정한 값이며 미검출(검출기가 놓친 모듈)은 포함하지 않습니다.')
    result['confusion'] = {}
    for r in reviewed:
        key = f"{r.get('final')}->{r['reviewed_label'].strip().lower()}"
        result['confusion'][key] = result['confusion'].get(key, 0) + 1
    return result


def main():
    parser = argparse.ArgumentParser(description='현장 검증 표본 생성과 채점')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sample')
    s.add_argument('--master', required=True)
    s.add_argument('--output', required=True)
    s.add_argument('--normals', type=int, default=250)
    s.add_argument('--seed', type=int, default=20261012)
    s.add_argument('--unit-column', help='같은 설비를 묶을 열 (예: drawing_module_id)')
    s.add_argument('--source-base')
    c = sub.add_parser('score')
    c.add_argument('--reviewed', required=True)
    args = parser.parse_args()
    if args.command == 'score':
        print(json.dumps(score(_read(args.reviewed)), ensure_ascii=False, indent=2))
        return
    rows, summary = build_sample(_read(args.master), args.normals, args.seed, args.unit_column)
    output = Path(args.output)
    # The review page writes the fill-in sheet; rename it so a re-run never looks like a completed review.
    write_field_review(rows, output, args.source_base or Path(args.master).parent)
    (output / 'field_review_template.csv').replace(output / 'verification_sample.csv')
    (output / 'verification_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()

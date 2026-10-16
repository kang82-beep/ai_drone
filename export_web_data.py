"""Export analysis and drawing-link results for the web console (web/index.html).

Writes web/data/site.js and the images it references. Only measured values are
exported; stages that are not implemented yet stay empty in the output.
"""
from pathlib import Path
import argparse, json, re, shutil
from datetime import datetime
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent
RANK = {'abnormal': 2, 'attention': 1, 'normal': 0}
RGB_SIZE = (4032, 3024)
VERDICT_STATE = {'normal': 1, 'recheck': 2, 'inspect': 3, 'retake': 0}  # map.js state: 0 unobserved (retake: seen only while turning)
VERDICT_RANK = {'inspect': 2, 'recheck': 1, 'normal': 0}
MASTER_COLUMNS = ['image_id', 'final', 'hs_is_hotspot', 'neighbor_flag', 'structure_status', 'capture_condition',
                  'camera_to_surface_m', 'gsd_x_m_per_px', 'irradiance_w_m2']


def local(path):
    """Results were written under an older project folder name; resolve them under ROOT."""
    text = str(path).replace('/', '\\')
    index = text.lower().find('\\results\\')
    return ROOT / text[index + 1:] if index >= 0 else Path(text)


def clean(value):
    if isinstance(value, float):
        return None if pd.isna(value) else round(value, 3)
    if hasattr(value, 'item'):
        return clean(value.item())
    return value


def capture_time(image_id):
    match = re.match(r'DJI_(\d{14})_', str(image_id))
    return datetime.strptime(match[1], '%Y%m%d%H%M%S').isoformat() if match else None


def read_hierarchy():
    text = (ROOT / 'shinan3_viewer/cable_data.js').read_text(encoding='utf-8')
    return json.loads(text[text.index('{'):].rstrip().rstrip(';'))


def site_map(cables, modules):
    """Per-module drawing position, string and inspection state for the 3D map, in catalog order."""
    catalog = pd.read_csv(ROOT / 'shinan3_viewer/assets/module_catalog.csv', encoding='utf-8-sig')
    layout = json.loads((ROOT / 'shinan3_viewer/assets/layout.json').read_text(encoding='utf-8'))
    index = {module_id: i for i, module_id in enumerate(catalog['module_id'])}
    state = ['0'] * len(catalog)
    delta = {}
    for row in modules.to_dict('records'):
        i = index.get(row['drawing_module_id'])
        if i is not None:
            state[i] = str(VERDICT_STATE.get(row.get('verdict'), 1))
            if not pd.isna(row['max_neighbor_delta']):
                delta[i] = round(row['max_neighbor_delta'], 2)
    return {'ids': catalog['module_id'].tolist(), 'x': catalog['east_m'].round(2).tolist(), 'y': catalog['north_m'].round(2).tolist(),
            'string': cables['module_to_string'], 'strings': [[s['id'], s['jb'], s['inverter']] for s in cables['strings']],
            'state': ''.join(state), 'delta': delta, 'boundary': [[round(v, 2) for v in point] for point in layout['boundary']],
            'buildings': [{k: b[k] for k in ('id', 'center', 'length', 'width', 'rotation')} for b in layout['buildings']],
            'spec': {k: layout['spec'][k] for k in ('module_width_m', 'module_length_m', 'tilt_deg')}}


def read_chunks(analysis):
    chunks, frames = [], []
    for folder in sorted((analysis / 'chunks').glob('*')):
        done = folder / 'done.json'
        entry = {'id': folder.name, 'status': 'done' if done.exists() else 'running' if (folder / 'analysis').exists() else 'pending'}
        if done.exists():
            entry.update(json.loads(done.read_text(encoding='utf-8')))
            frame = pd.read_csv(folder / 'analysis/master_results.csv', encoding='utf-8-sig', usecols=MASTER_COLUMNS, low_memory=False)
            entry['observations'] = len(frame)
            entry['flagged'] = int((frame['final'] != 'normal').sum())
            frames.append(frame)
        chunks.append(entry)
    return chunks, pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=MASTER_COLUMNS)


def save_image(source, target, width=None):
    if target.exists() or not source.is_file():
        return target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    if width is None:
        shutil.copyfile(source, target)
    else:
        with Image.open(source) as image:
            image.thumbnail((width, width))
            # A fresh save drops EXIF/XMP, so the web copy carries no GPS position.
            image.convert('RGB').save(target, quality=82)
    return True


def rgb_crop(source, bbox, transform, target, margin=.35):
    """Cut the visible-image region of a thermal bbox using the fixed thermal→visible transform.

    Returns the module box in the visible frame (normalised 0–1); the crop keeps a margin
    so the operator can judge the alignment against neighbouring panels.
    """
    x1, y1, x2, y2 = bbox
    corners = np.array([[x1, y1, 1], [x2, y1, 1], [x2, y2, 1], [x1, y2, 1]], float) @ np.array(transform).T
    (u1, v1), (u2, v2) = corners.min(0), corners.max(0)
    if not source.is_file():
        return None
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            pad_u, pad_v = (u2 - u1) * margin, (v2 - v1) * margin
            box = tuple(int(round(v)) for v in (max(0, u1 - pad_u), max(0, v1 - pad_v), min(image.width, u2 + pad_u), min(image.height, v2 + pad_v)))
            crop = image.crop(box)
            crop.thumbnail((360, 360))
            crop.convert('RGB').save(target, quality=85)
    return [round(u1 / RGB_SIZE[0], 4), round(v1 / RGB_SIZE[1], 4), round(u2 / RGB_SIZE[0], 4), round(v2 / RGB_SIZE[1], 4)]


def module_pattern(observations):
    """Module-level shape from its most central flagged view; oblique views near the frame edge misread.

    edge_only marks modules flagged only near the frame edge while a central view looked normal,
    the reflection pattern operators reported.
    """
    readable = [o for o in observations if o.get('type') and o['type'] != 'unreadable']
    flagged = [o for o in readable if o['final'] != 'normal']
    if not flagged:
        return {'type': 'unreadable' if observations else None, 'shadow': False, 'edge_only': False}
    best = min(flagged, key=lambda o: o.get('radius') if o.get('radius') is not None else 9)
    central_normal = any(o['final'] == 'normal' and (o.get('radius') or 9) <= .6 for o in readable)
    return {'type': best['type'], 'shadow': any(o.get('shadow') for o in flagged),
            'edge_only': all(o.get('edge') for o in flagged) and central_normal}


def read_summary(folder):
    path = folder / 'summary.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def read_diagnoses(folder):
    """Cause candidates per flagged module, trimmed to what the console shows."""
    path = folder / 'diagnoses.json'
    if not path.is_file():
        return []
    keep = ('cause', 'confidence', 'action', 'urgency', 'kind', 'safety', 'evidence', 'llm_reason')
    return [{'id': d['module_id'], 'primary': d['primary'], 'action': d['action'], 'urgency': d['urgency'],
             'kind': d['kind'], 'source': d['source'], 'needs_review': d['needs_review'], 'exclude': d['exclude'],
             'safety': d['safety'], 'appearance': d.get('appearance'), 'loss_w': d.get('loss_w'),
             'ai_downgraded': d.get('ai_downgraded'), 'ai_audit': d.get('ai_audit'), 'field_kind_kept': d.get('field_kind_kept'),
             'rule_primary': d.get('rule_primary'),
             'candidates': [{k: c.get(k) for k in keep} for c in d['candidates']]}
            for d in json.loads(path.read_text(encoding='utf-8'))]


def read_kb():
    from pv_inspector.diagnosis import load_kb
    kb = load_kb()
    return {'version': kb['version'], 'causes': [r['cause'] for r in kb['rules']],
            'kinds': {k: v['label'] for k, v in kb['kinds'].items()},
            'rules': [{k: r[k] for k in ('observation', 'cause', 'action', 'urgency')} for r in kb['rules']]}


def read_orders(folder):
    path = folder / 'orders.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', default='results/shinan3_full_20261030')
    parser.add_argument('--registration', default='results/shinan3_full_20261030/reg')
    parser.add_argument('--output', default='web/data')
    parser.add_argument('--alignment', default='results/ir_rgb_alignment/alignment.json')
    parser.add_argument('--patterns', default='results/anomaly_patterns/anomaly_patterns.csv')
    parser.add_argument('--verdicts', default='results/module_verdicts')
    parser.add_argument('--orders', default='results/orders', help='generate_orders.py 출력 (원인 추정·작업지시)')
    args = parser.parse_args()
    alignment_path = ROOT / args.alignment
    alignment = json.loads(alignment_path.read_text(encoding='utf-8')) if alignment_path.is_file() else None
    patterns = {}
    if (ROOT / args.patterns).is_file():
        for p in pd.read_csv(ROOT / args.patterns, encoding='utf-8-sig').to_dict('records'):
            patterns[(p['image_id'], int(p['module_id']))] = p
    analysis, registration, output = (ROOT / args.analysis, ROOT / args.registration, ROOT / args.output)
    images = output / 'img'

    cables = read_hierarchy()
    strings = cables['strings']
    chunks, master = read_chunks(analysis)
    runner = (analysis / 'runner.log').read_text(encoding='utf-8', errors='ignore') if (analysis / 'runner.log').is_file() else ''
    total = re.search(r'(\d+)\D+(\d+)\D*\n', runner)
    thermal_total = int(total[1]) if total else None
    chunk_total = int(total[2]) if total else len(chunks)
    chunks += [{'id': f'{i:03d}', 'status': 'pending'} for i in range(len(chunks), chunk_total)]
    times = sorted(filter(None, map(capture_time, master['image_id'].unique())))
    irradiance = master['irradiance_w_m2'].dropna()

    report = json.loads((registration / 'registration_report.json').read_text(encoding='utf-8'))
    linked = pd.read_csv(registration / 'master_linked.csv', encoding='utf-8-sig', low_memory=False)
    modules = pd.read_csv(registration / 'module_summary.csv', encoding='utf-8-sig')
    string_summary = pd.read_csv(registration / 'string_summary.csv', encoding='utf-8-sig')
    frame_registration = pd.read_csv(registration / 'frame_registration.csv', encoding='utf-8-sig')

    # Module verdicts from repeated views (judge_modules.py); without them every flagged module is a candidate.
    verdict_dir = ROOT / args.verdicts
    string_verdicts = pd.DataFrame(columns=['string_id', 'string_delta', 'string_flag'])
    if (verdict_dir / 'module_verdicts.csv').is_file():
        verdicts = pd.read_csv(verdict_dir / 'module_verdicts.csv', encoding='utf-8-sig')
        modules = modules.merge(verdicts[['drawing_module_id', 'verdict', 'verdict_reason', 'usable_views', 'flagged_votes',
                                          'wide_delta', 'wide_neighbours']], on='drawing_module_id', how='left')
        string_verdicts = pd.read_csv(verdict_dir / 'string_verdicts.csv', encoding='utf-8-sig')
    else:
        modules['verdict'] = np.where(modules['flagged_observations'] > 0, 'inspect', 'normal')
        modules['verdict_reason'] = ''
    modules['verdict'] = modules['verdict'].fillna('normal')
    string_summary = string_summary.merge(string_verdicts[['string_id', 'string_delta', 'string_flag']], on='string_id', how='left')
    flagged = modules[modules['verdict'].isin(['inspect', 'recheck'])]
    inverters = {}
    for item in strings:
        jb = inverters.setdefault(item['inverter'], {}).setdefault(item['jb'], {'id': item['jb'], 'strings': 0, 'modules': 0})
        jb['strings'] += 1
        jb['modules'] += len(item['modules'])
    observed = modules.groupby('jb_id').size()
    flagged_count = flagged.groupby('jb_id').size()
    abnormal = modules[modules['verdict'] == 'inspect'].groupby('jb_id').size()
    for jbs in inverters.values():
        for jb in jbs.values():
            jb.update(observed=int(observed.get(jb['id'], 0)), flagged=int(flagged_count.get(jb['id'], 0)),
                      abnormal=int(abnormal.get(jb['id'], 0)),
                      string_rows=[{k: clean(v) for k, v in row.items() if k != 'flagged_modules'}
                                   for row in string_summary[string_summary['jb_id'] == jb['id']].to_dict('records')])

    linked['rank'] = linked['final'].map(RANK).fillna(0)
    candidates = []
    for row in flagged.to_dict('records'):
        rows = linked[linked['drawing_module_id'] == row['drawing_module_id']].sort_values(
            ['rank', 'neighbor_delta_max'], ascending=False)
        observations = []
        for item in rows.to_dict('records'):
            image_id = item['image_id']
            crop = local(item['dst_path'])
            crop = crop if crop.is_file() else local(item['crop_path'])
            reasons = [r for r in str(item['decision_reason']).split(';') if r != 'hierarchical']
            if item['hs_is_hotspot'] and 'hotspot' not in reasons:
                reasons.append('hotspot')
            entry = {'image_id': image_id, 'time': capture_time(image_id), 'final': item['final'], 'reasons': reasons,
                     'hotspot': bool(item['hs_is_hotspot']),
                     'bbox': [round(item['bbox_x1'] / item['img_w'], 4), round(item['bbox_y1'] / item['img_h'], 4),
                              round(item['bbox_x2'] / item['img_w'], 4), round(item['bbox_y2'] / item['img_h'], 4)]}
            for key in ('max_temp', 'mean_temp', 'delta_temp', 'neighbor_ref_temp', 'neighbor_delta_max', 'neighbor_delta_mean',
                        'prob_abnormal', 'prob_attention', 'prob_normal', 'link_distance_m'):
                entry[key] = clean(item[key])
            if save_image(crop, images / 'crops' / f'{image_id}_{item["module_id"]}.jpg'):
                entry['crop'] = f'data/img/crops/{image_id}_{item["module_id"]}.jpg'
            if save_image(local(item['det_base']), images / 'thermal' / f'{image_id}.jpg', 1280):
                entry['thermal'] = f'data/img/thermal/{image_id}.jpg'
            if save_image(local(item['rgb_path']), images / 'rgb' / f'{image_id}.jpg', 1600):
                entry['rgb'] = f'data/img/rgb/{image_id}.jpg'
            if alignment:
                name = f'{image_id}_{item["module_id"]}.jpg'
                rgb_box = rgb_crop(local(item['rgb_path']), [item['bbox_x1'], item['bbox_y1'], item['bbox_x2'], item['bbox_y2']],
                                   alignment['fixed_thermal_to_rgb'], images / 'rgb_crops' / name)
                if rgb_box:
                    entry['rgb_bbox'] = rgb_box
                    entry['rgb_crop'] = f'data/img/rgb_crops/{name}'
            pattern = patterns.get((image_id, int(item['module_id'])))
            if pattern:
                entry.update(type=pattern['type'], radius=clean(pattern['radius']), edge=bool(pattern['edge']),
                             shadow=bool(pattern.get('shadow_suspect') is True or pattern.get('shadow_suspect') == 'True'),
                             cautions=[c for c in str(pattern.get('cautions') or '').split(' | ') if c and c != 'nan'],
                             hot_on_rgb_dark=clean(pattern.get('hot_on_rgb_dark')))
            observations.append(entry)
        candidates.append({'id': row['drawing_module_id'], 'string': row['string_id'], 'jb': row['jb_id'],
                           'inverter': row['inverter_id'], 'final': row['worst_final'],
                           'observation_count': int(row['observations']), 'flagged_count': int(row['flagged_observations']),
                           'repeatability': clean(row['repeatability']), 'max_delta_temp': clean(row['max_delta_temp']),
                           'max_neighbor_delta': clean(row['max_neighbor_delta']), 'observations': observations,
                           'verdict': row['verdict'], 'verdict_reason': row.get('verdict_reason') if isinstance(row.get('verdict_reason'), str) else '',
                           'usable_views': clean(row.get('usable_views')), 'flagged_votes': clean(row.get('flagged_votes')),
                           'wide_delta': clean(row.get('wide_delta')), 'wide_neighbours': clean(row.get('wide_neighbours')),
                           **module_pattern(observations)})
    candidates.sort(key=lambda c: (-VERDICT_RANK.get(c['verdict'], 0), -RANK.get(c['final'], 0), -(c['max_neighbor_delta'] or -99)))

    link_counts = linked['link_status'].value_counts()
    matched = int(link_counts.drop('unmatched', errors='ignore').sum())
    reasons = linked[linked['final'] != 'normal']['decision_reason'].str.split(';').explode().value_counts()
    site = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'site': {'name': '신안3호기', 'modules': sum(len(s['modules']) for s in strings), 'strings': len(strings),
                 'jbs': len({s['jb'] for s in strings}), 'inverters': len(inverters), 'rated_w': 250},
        'flight': {'first': times[0] if times else None, 'last': times[-1] if times else None,
                   'thermal_images': thermal_total, 'analysed': sum(c.get('thermal_images', 0) for c in chunks),
                   'irradiance_w_m2': clean(float(irradiance.iloc[0])) if len(irradiance) else None,
                   'wind_m_s': None, 'height_m': clean(float(master['camera_to_surface_m'].median())) if len(master) else None,
                   'gsd_cm': clean(float(master['gsd_x_m_per_px'].median()) * 100) if len(master) else None},
        'chunks': chunks,
        'observations': {'total': len(master), 'by_final': master['final'].value_counts().to_dict(),
                         'hotspot': int(master['hs_is_hotspot'].sum()), 'neighbor_flag': int(master['neighbor_flag'].sum()),
                         'structure': master['structure_status'].value_counts().to_dict()},
        'registration': {'status': report['status'], 'frames': report['frames'], 'frames_registered': report['frames_registered'],
                         'observations': report['observations'], 'linked': matched,
                         'modules_observed': report['drawing_modules_observed'], 'strings_observed': report['strings_observed'],
                         'pitch_resolved': report['whole_pitch_test']['resolved'],
                         'lines': None if not report.get('flight_lines') else {
                             'total': report['flight_lines']['lines'], 'resolved': report['flight_lines']['resolved'],
                             'decided_by': report['flight_lines'].get('decided_by', {}),
                             'unresolved_observations': report.get('module_candidates_line_unresolved', 0)},
                         'visual_agreement': clean(report.get('visual_link_agreement', {}).get('agreement')),
                         'frame_shift_std_m': report.get('frame_shift_std_m'), 'limitations': report.get('limitations', []),
                         'modules_by_final': modules['worst_final'].value_counts().to_dict(),
                         'reasons': {k: int(v) for k, v in reasons.items()},
                         'frame_rows': [{k: clean(v) for k, v in row.items()} for row in frame_registration.to_dict('records')]},
        'inverters': [{'id': key, 'jbs': list(value.values())} for key, value in sorted(inverters.items())],
        'candidates': candidates,
        'rgb_alignment': {k: alignment[k] for k in ('scale_rgb_px_per_thermal_px', 'frames_sampled', 'frames_voting',
                                                    'offset_from_fixed_px_median', 'offset_from_fixed_px_p90')} if alignment else None,
        'verdicts': modules['verdict'].value_counts().to_dict(),
        'strings_flagged': [{k: clean(v) for k, v in row.items()} for row in string_summary[string_summary['string_flag'] == True][
            ['inverter_id', 'jb_id', 'string_id', 'string_delta', 'modules_observed']].to_dict('records')],
        'pattern_types': pd.Series([c.get('type') for c in candidates if c.get('type')]).value_counts().to_dict() if candidates else {},
        'diagnoses': read_diagnoses(ROOT / args.orders),
        'work_orders': read_orders(ROOT / args.orders),
        'flight_id': read_summary(ROOT / args.orders).get('flight_id'),
        'orders_summary': read_summary(ROOT / args.orders),
        'kb': read_kb(),
        'metrics': {'false_alarm_rate': None, 'miss_rate': None, 'cause_match_rate': None},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / 'site.js').write_text('window.SITE = ' + json.dumps(site, ensure_ascii=False, allow_nan=False) + ';\n', encoding='utf-8')
    (output / 'map.js').write_text('window.SITE_MAP = ' + json.dumps(site_map(cables, modules), ensure_ascii=False, allow_nan=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    print(json.dumps({'candidates': len(candidates), 'observations': len(master), 'chunks_done': sum(c['status'] == 'done' for c in chunks),
                      'images': sum(1 for _ in images.rglob('*.jpg')), 'output': str(output / 'site.js')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

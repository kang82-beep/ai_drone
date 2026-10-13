"""Connect drawing IDs to frozen analysis observations without inventing confirmations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .site_structures import raised_modules

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / 'results/module_links/module_links.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assemble(records, modules, dataset_id, confirmed=None, rejected=()):
    """Only externally revalidated evidence may supply confirmed observation IDs."""
    confirmed = confirmed or {}
    index = {m['id']: {'id': m['id'], 'polygon': m['vertices'][:4], 'records': []} for m in modules}
    if len(index) != len(modules):
        raise ValueError('Duplicate drawing module IDs')
    result = []
    seen = set()
    for i, source in enumerate(records):
        identity = (source['image_id'], str(source['module_id']))
        if identity in seen:
            raise ValueError('Duplicate observation identity')
        seen.add(identity)
        record = dict(source)
        record['observation_id'] = dataset_id + ':' + str(i)
        uid = source['module_uid']
        module_id = confirmed.get(uid) or source.get('drawing_candidate_id')
        status = 'confirmed' if uid in confirmed else 'historical_candidate'
        if uid in rejected:
            status = 'rejected'; module_id = None
        elif module_id not in index:
            status = 'unmatched'; module_id = None
        record.update(drawing_module_id=module_id, link_status=status)
        result.append(record)
        if module_id:
            index[module_id]['records'].append(i)
    return {'schema_version': 1, 'dataset_id': dataset_id, 'scope': 'A-zone frozen observations',
            'records': result, 'modules': index,
            'counts': dict(Counter(r['link_status'] for r in result))}


def build(root=ROOT, output=DEFAULT_INDEX):
    root = Path(root)
    review_path = root / 'results/blender_site/thermal_review_registered_a.json'
    layout_path = root / 'results/drawing_site/site_layout.json'
    review = read(review_path)
    # Cached associations may be shown only on the exact drawing they were made for.
    for name, expected in review['registration']['fingerprints'].items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'정합 기준 자료가 없거나 변경되었습니다: {name}')
    modules = [m for row in read(layout_path)['rows'] for m in raised_modules(row)]
    warnings = []
    confirmed = {}; rejected = set(); evidence_fingerprints = {}
    state_path = root / 'results/a_module_review/review_state.json'
    if state_path.is_file():
        try:
            from .module_review import ReviewSession
            session = ReviewSession(root / 'results/a_module_review', root, verify=True)
            evidence_fingerprints.update(session.manifest['source_hashes'])
            evidence_fingerprints.update(session.manifest['asset_hashes'])
            for uid, evidence in session.state['cases'].items():
                if evidence['status'] == 'confirmed':
                    confirmed[uid] = session.propose(uid, evidence)['module_id']
                elif evidence['status'] == 'rejected':
                    rejected.add(uid)
        except (ValueError, OSError) as exc:
            warnings.append('검토 근거 재검증 실패: ' + str(exc))
            # Never silently reactivate rejected links from cached guesses.
            state = read(state_path)
            manifest = read(root / 'results/a_module_review/manifest.json')
            if state.get('dataset_id') == manifest.get('dataset_id'):
                rejected = {uid for uid, e in state['cases'].items() if e.get('status') == 'rejected'}
    if not confirmed:
        warnings.append('확정 연결 없음. 후보는 기존 A구역 정합 결과이며 신규 분석이나 현장 정답이 아닙니다.')
    dataset = digest(review_path)
    result = assemble(review['records'], modules, dataset, confirmed, rejected)
    result['warnings'] = warnings
    paths = [review_path, layout_path, *[root/name for name in review['registration']['fingerprints']]]
    result['fingerprints'] = {str(p.relative_to(root)): digest(p) for p in paths}
    if confirmed:
        result['fingerprints'].update(evidence_fingerprints)
    # Review state changes invalidate the displayed snapshot too.
    if state_path.is_file(): result['fingerprints'][str(state_path.relative_to(root))] = digest(state_path)
    result['source_review'] = str(review_path)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    return result


def load_index(path=DEFAULT_INDEX, root=ROOT):
    data = read(path)
    for name, expected in data['fingerprints'].items():
        source = Path(root) / name
        if not source.is_file() or digest(source) != expected:
            raise ValueError('3D 연결 자료가 변경되었습니다. 연결 인덱스를 다시 생성하세요.')
    return data


def validate_blender_export(scene, root=ROOT):
    scene = Path(scene)
    metadata = read(scene.with_suffix('.links.json'))
    if digest(scene) != metadata['blend_sha256']:
        raise ValueError('Blender 장면이 내보내기 이후 변경되었습니다. 연결 장면을 다시 생성하세요.')
    index = Path(root) / metadata['index_path']
    if digest(index) != metadata['index_sha256']:
        raise ValueError('분석 연결 인덱스가 갱신되었습니다. Blender 장면도 다시 생성하세요.')
    return load_index(index, root)


def main():
    parser = argparse.ArgumentParser(description='A구역 기존 정합 결과를 3D 모듈 ID별로 연결')
    parser.add_argument('--output', default=str(DEFAULT_INDEX))
    args = parser.parse_args()
    data = build(output=args.output)
    print(json.dumps({'records': len(data['records']), 'linked_modules': sum(bool(m['records']) for m in data['modules'].values()),
                      'counts': data['counts'], 'warnings': data['warnings']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

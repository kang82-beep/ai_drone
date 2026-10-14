"""Run a whole flight in resumable chunks and merge the observations.

Each chunk is an ordinary pv_inspector run on hard-linked inputs, so a failure
costs one chunk, not the flight. Cross-frame links are not made across chunk
boundaries; provisional module_uid values are prefixed with the chunk number.
"""
from pathlib import Path
import argparse, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT = Path(__file__).resolve().parent


def link_chunk(files, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for source in files:
        target = folder / source.name
        if not target.exists():
            try:
                os.link(source, target)
            except OSError:  # images on another drive cannot be hard-linked
                shutil.copy2(source, target)


def run_chunk(index, files, base, output, threads):
    chunk = output / 'chunks' / f'{index:03d}'
    done = chunk / 'done.json'
    if done.exists():
        return index, 'already_done'
    analysis = chunk / 'analysis'
    if analysis.exists():
        raise FileExistsError(f'{analysis}: 중단된 실행의 결과가 남아 있습니다. 확인 후 폴더를 지우고 다시 실행하세요.')
    link_chunk(files, chunk / 'input')
    settings = dict(base, INPUT_IMG_DIR=str(chunk / 'input'), OUTPUT_ROOT=str(analysis), RESUME_RUN=False)
    (chunk / 'config.json').write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads), PYTHONIOENCODING='utf-8')
    started = time.time()
    with (chunk / 'run.log').open('w', encoding='utf-8') as log:
        code = subprocess.run([sys.executable, '-m', 'pv_inspector', '--config', str(chunk / 'config.json')],
                              cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    if code or not (analysis / 'master_results.csv').is_file():
        return index, f'failed (exit {code}); see {chunk / "run.log"}'
    done.write_text(json.dumps({'thermal_images': sum(f.name.upper().endswith('_T.JPG') for f in files),
                                'seconds': round(time.time() - started)}), encoding='utf-8')
    return index, 'ok'


def merge(output):
    frames, links, images, rows = [], [], 0, 0
    for done in sorted((output / 'chunks').glob('*/done.json')):
        images += json.loads(done.read_text(encoding='utf-8'))['thermal_images']
        path = done.parent / 'analysis' / 'master_results.csv'
        if path.stat().st_size < 10:
            continue
        frame = pd.read_csv(path, encoding='utf-8-sig')
        frame.insert(0, 'chunk', done.parent.name)
        if 'module_uid' in frame:
            frame['module_uid'] = done.parent.name + '-' + frame['module_uid'].astype(str)
        frames.append(frame)
        link_path = done.parent / 'analysis' / 'association_links.csv'
        if link_path.is_file() and link_path.stat().st_size > 10:
            link = pd.read_csv(link_path, encoding='utf-8-sig')
            # Link indices are rows of that chunk's table; shift them to the merged table.
            link[['source_index', 'target_index']] += rows
            links.append(link)
        rows += len(frame)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    merged.to_csv(output / 'master_results.csv', index=False, encoding='utf-8-sig')
    if links:
        pd.concat(links, ignore_index=True).to_csv(output / 'association_links.csv', index=False, encoding='utf-8-sig')
    return merged, images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--chunk-size', type=int, default=100)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--from-chunk', type=int, default=0,
                        help='Skip earlier chunks, e.g. when they were analysed on another PC (see make_transfer_package.py)')
    args = parser.parse_args()
    if os.name == 'nt':
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: idle sleep would stall a chunk for hours.
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    base = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    captures = {}
    for path in sorted(Path(args.input).iterdir()):
        match = re.fullmatch(r'DJI_\d{14}_(\d+)_[TV]\.JPE?G', path.name, re.IGNORECASE)
        if match:
            captures.setdefault(int(match[1]), []).append(path)
    keys = sorted(k for k, v in captures.items() if any(p.stem.upper().endswith('_T') for p in v))
    chunks = [[p for k in keys[i:i + args.chunk_size] for p in captures[k]] for i in range(0, len(keys), args.chunk_size)]
    print(f'열화상 {len(keys)}장, {len(chunks)}개 묶음', flush=True)
    todo = [(i, files) for i, files in enumerate(chunks) if i >= args.from_chunk]
    with ThreadPoolExecutor(args.workers) as pool:
        for index, status in pool.map(lambda item: run_chunk(item[0], item[1], base, output, args.threads), todo):
            print(f'[{index + 1}/{len(chunks)}] {status}', flush=True)
    merged, images = merge(output)
    summary = {'thermal_images_input': len(keys), 'thermal_images_analysed': images,
               'chunks': len(chunks), 'chunks_done': len(list((output / 'chunks').glob('*/done.json'))),
               'observations': len(merged),
               'decisions': merged['final'].value_counts().to_dict() if len(merged) else {},
               'temperature_status': merged['temperature_status'].value_counts().to_dict() if len(merged) else {},
               'note': '관측 수는 중복 촬영을 포함하며 설치 모듈 수가 아닙니다.'}
    (output / 'run_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

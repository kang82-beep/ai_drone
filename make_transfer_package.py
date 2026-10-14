"""Build a small copy of this project for finishing the full-site analysis on another Windows PC.

The other PC already holds the drone images, so the package carries only the analysis
code, model weights, the DJI SDK binaries and the run settings (a few hundred MB instead
of the whole project with its results). It mirrors this project's layout and is copied
to C:\\ai_drone on the other PC. Chunks already done here are skipped with --from-chunk.
To bring results back, copy the new chunks/NNN folders (without input/) into this
project's run folder and re-run run_full_site.py, which then only merges.
"""
from pathlib import Path
import argparse, json, shutil

ROOT = Path(__file__).resolve().parent
CODE = ['pv_inspector', 'run_full_site.py', 'requirements.txt']
SDK = 'dji_thermal_sdk_v1.7_20241205/utility/bin/windows/release_x64'
WEIGHTS = ['model/maskrcnn_trained_drone_shinan_0904.pth', 'model/classifier_b3_2025_1013.pth']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='results/shinan3_full_20261030')
    parser.add_argument('--chunk-size', type=int, default=50)
    parser.add_argument('--output', default=r'C:\ai_drone_package\ai_drone')
    args = parser.parse_args()
    run, output = ROOT / args.run, Path(args.output)
    if output.exists():
        raise SystemExit(f'{output} already exists; remove it first.')
    # Chunks are numbered in capture order, so the first missing done.json is where the other PC starts.
    first = 0
    while (run / 'chunks' / f'{first:03d}' / 'done.json').exists():
        first += 1

    for item in CODE:
        source, target = ROOT / item, output / item
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__'))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    shutil.copytree(ROOT / SDK, output / SDK)
    for item in WEIGHTS:
        (output / item).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / item, output / item)
    (output / args.run).mkdir(parents=True)
    shutil.copy2(run / 'base_config.json', output / args.run / 'base_config.json')

    run_dir = args.run.replace('/', '\\')
    (output / '분석 실행.bat').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\n'
        'if /i not "%~dp0"=="C:\\ai_drone\\" (echo 이 폴더를 C:\\ai_drone 위치에 두고 실행하세요. & pause & exit /b 1)\r\n'
        'set "IMAGES=C:\\drone 3"\r\n'
        'set /p "IMAGES=드론 영상 폴더 경로 [C:\\drone 3]: "\r\n'
        f'python run_full_site.py --config {run_dir}\\base_config.json --input "%IMAGES%" --output {run_dir} '
        f'--chunk-size {args.chunk_size} --from-chunk {first} --workers 1 --threads 4\r\npause\r\n', encoding='cp949')
    (output / '처음 설치.bat').write_text(
        '@echo off\r\ncd /d "%~dp0"\r\npython -m pip install -r requirements.txt\r\npause\r\n', encoding='cp949')
    size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    print(json.dumps({'output': str(output), 'from_chunk': first, 'size_mb': round(size / 2**20)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

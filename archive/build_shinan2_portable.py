"""Bundle the Shinan 2 viewer into an offline, file:// compatible HTML file."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'shinan2_viewer'
OUT = ROOT / 'results/shinan2_delivery/ThreeJS'
DEPS = ROOT / 'shinan3_viewer/node_modules'

def main():
    entry = SRC / 'app.js'
    if not entry.exists():
        raise SystemExit(f'Viewer entry is not ready: {entry}')
    OUT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'tmp').mkdir(exist_ok=True)
    bundle = ROOT / 'tmp/shinan2-portable-bundle.js'
    env = dict(os.environ)
    env['NODE_PATH'] = str(DEPS)
    subprocess.run(['node', str(DEPS / 'esbuild/bin/esbuild'), str(entry),
        '--bundle', '--format=iife', '--minify', '--legal-comments=inline',
        '--loader:.jpg=dataurl', '--loader:.png=dataurl',
        '--outfile=' + str(bundle)], check=True, env=env, cwd=ROOT)
    script = bundle.read_text(encoding='utf-8').replace('</script', '<\\/script')
    html = '''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>신안2호기 — 도면·사진 기반 3D</title>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#111820}canvas{display:block}</style>
</head><body><script>''' + script + '</script></body></html>'
    target = OUT / 'Shinan2_Viewer.html'
    target.write_text(html, encoding='utf-8')
    licenses=[]
    for package in ('three','cannon-es'):
        path=DEPS/package/'LICENSE'
        if path.exists():
            licenses.append(package+'\n'+path.read_text(encoding='utf-8'))
    (OUT/'THIRD_PARTY_LICENSES.txt').write_text('\n\n'.join(licenses),encoding='utf-8')
    print(f'Offline viewer: {target}\nBytes: {target.stat().st_size:,}')

if __name__ == '__main__':
    main()

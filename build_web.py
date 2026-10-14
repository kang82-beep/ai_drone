"""Bundle the console's 3D map (web/src/map3d.js + Three.js) into web/vendor/map3d.js.

Only needed after editing web/src/map3d.js. The bundle is committed so the console
opens from file:// without Node or a server.
"""
from pathlib import Path
import os, subprocess

ROOT = Path(__file__).resolve().parent
MODULES = ROOT / 'shinan3_viewer/node_modules'
subprocess.run(['node', str(MODULES / 'esbuild/bin/esbuild'), str(ROOT / 'web/src/map3d.js'), '--bundle', '--format=iife',
                '--global-name=SiteMap', '--minify', '--legal-comments=inline', '--outfile=' + str(ROOT / 'web/vendor/map3d.js')],
               check=True, env={**os.environ, 'NODE_PATH': str(MODULES)})

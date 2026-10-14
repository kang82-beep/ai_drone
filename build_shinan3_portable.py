"""Bundle a file:// compatible Three.js viewer; browsing requires no Python/Node."""
from pathlib import Path
import argparse, base64, json, re, shutil, subprocess

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'shinan3_viewer'
parser=argparse.ArgumentParser()
parser.add_argument('--output',default=str(ROOT/'results/shinan3_delivery/ThreeJS'))
parser.add_argument('--console-data',action='append',default=[],help='Script loaded before the viewer, e.g. ../data/site.js for the web console link')
ARGS=parser.parse_args()
OUT=Path(ARGS.output)
OUT.mkdir(parents=True,exist_ok=True)
app=(SRC/'app.js').read_text(encoding='utf-8')
imports='\n'.join(re.findall(r'^import .*?;\s*$',app,re.M))
body=re.sub(r'^import .*?;\s*$','',app,flags=re.M)
layout=(SRC/'assets/layout.json').read_text(encoding='utf-8')
body,count=re.subn(r"const data=await fetch\('assets/layout.json'\)[^\n]*",lambda _: 'const data='+layout+';',body)
assert count==1,'Expected exactly one layout load to make offline'
textures={p.name:'data:image/jpeg;base64,'+base64.b64encode(p.read_bytes()).decode('ascii') for p in (SRC/'assets').glob('*.jpg')}
body=body.replace("loader.load('assets/'+name",'loader.load(window.SHINAN_TEXTURES[name]')
entry=SRC/'.portable-entry.js'
entry.write_text(imports+'\n(async()=>{\n'+body+'\n})().catch(e=>{console.error(e);const p=document.getElementById("loadtext");if(p)p.textContent="모형을 열지 못했습니다: "+e.message;});',encoding='utf-8')
bundle=ROOT/'tmp/shinan3-portable-bundle.js'
subprocess.run(['node',str(SRC/'node_modules/esbuild/bin/esbuild'),str(entry),'--bundle','--format=iife','--minify','--legal-comments=inline','--outfile='+str(bundle)],check=True)
html=(SRC/'index.html').read_text(encoding='utf-8')
html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(SRC/'style.css').read_text(encoding='utf-8')+'</style>')
html=re.sub(r'<script type="importmap">.*?</script>','',html,flags=re.S)
script='window.SHINAN_TEXTURES='+json.dumps(textures,separators=(',',':'))+';\n'+bundle.read_text(encoding='utf-8')
script=script.replace('</script','<\\/script')
data_tags=''.join(f'<script src="{src}"></script>' for src in ARGS.console_data)
html=html.replace('<script type="module" src="app.js"></script>',data_tags+'<script>'+script+'</script>')
(OUT/'Shinan3_Viewer.html').write_text(html,encoding='utf-8')
refs=OUT/'assets/reference';refs.mkdir(parents=True,exist_ok=True)
for p in (SRC/'assets/reference').iterdir():
    if p.is_file():shutil.copy2(p,refs/p.name)
for name in ('module_catalog.csv','asset_manifest.json'):
    shutil.copy2(SRC/'assets'/name,OUT/'assets'/name)
ref=(SRC/'assets/source_reference.html').read_text(encoding='utf-8').replace('../index.html','../Shinan3_Viewer.html')
(OUT/'assets/source_reference.html').write_text(ref,encoding='utf-8')
if (SRC/'assets/cable_reference.html').exists():
    ref=(SRC/'assets/cable_reference.html').read_text(encoding='utf-8').replace('../index.html','../Shinan3_Viewer.html')
    (OUT/'assets/cable_reference.html').write_text(ref,encoding='utf-8')
licenses=[]
for package in ('three','cannon-es'):
    p=SRC/'node_modules'/package/'LICENSE'
    if p.exists():licenses.append(package+'\n'+p.read_text(encoding='utf-8'))
(OUT/'THIRD_PARTY_LICENSES.txt').write_text('\n\n'.join(licenses),encoding='utf-8')
print('Standalone HTML:',OUT/'Shinan3_Viewer.html')
print('Bytes:',(OUT/'Shinan3_Viewer.html').stat().st_size)

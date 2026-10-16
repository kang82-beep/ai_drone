"""Verify data conservation independently from the viewer implementation."""
from pathlib import Path
import csv,json,math,hashlib
ROOT=Path(__file__).resolve().parent
source=json.loads((ROOT/'results/shinan3_blender/layout.json').read_text(encoding='utf-8'))
viewer=json.loads((ROOT/'shinan3_viewer/assets/layout.json').read_text(encoding='utf-8'))
assert source['source_sha256']==viewer['source_sha256']
assert len(viewer['groups'])==1500 and len(viewer['buildings'])==3
assert source['boundary']==viewer['boundary']
catalog=list(csv.DictReader((ROOT/'shinan3_viewer/assets/module_catalog.csv').open(encoding='utf-8-sig')))
expected={m['id']:m for m in source['modules']}
assert len(catalog)==len(expected)==30000
max_error=0
for g in viewer['groups']:
    for row in range(2):
        for col in range(10):
            mid=f"{g['id']}-R{row+1}-M{col+1:02}"
            center=(g['bounds'][0]+col*1.008+.4915,g['bounds'][1]+row*1.425+.7125)
            max_error=max(max_error,math.dist(center,expected[mid]['center_xy_m']))
assert max_error<1e-7
assert {r['module_id'] for r in catalog}==set(expected)
assert all(r['link_status']=='unlinked' for r in catalog)
for b in viewer['buildings']:
    original=next(x for x in source['buildings'] if x['id']==b['id'])
    assert b['center']==original['center'] and b['rotation']==original['rotation']
html=(ROOT/'results/shinan3_delivery/ThreeJS/Shinan3_Viewer.html').read_text(encoding='utf-8')
assert 'type="module"' not in html and 'type="importmap"' not in html
assert 'window.SHINAN_TEXTURES=' in html and 'data:image/jpeg;base64,' in html
report={'module_ids':len(expected),'groups':1500,'buildings':3,'cad_source_sha256':source['source_sha256'],'max_module_center_error_m':max_error,'cad_boundary_unchanged':True,'thermal_results_linked':False,'offline_html_contains_runtime_data_and_textures':True}
(ROOT/'results/shinan3_review/data_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

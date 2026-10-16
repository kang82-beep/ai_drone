"""Package only deliverables; exclude caches, credentials and node_modules."""
from pathlib import Path
import shutil,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan3_delivery'
for folder in ('Blender','Previews','Review','Electrical'):(OUT/folder).mkdir(exist_ok=True)
for name in ('Shinan3_Refined.blend','refinement_manifest.json','validation.json','environment_validation.json','cable_validation.json','Shinan3_Interiors.glb','interior_validation.json'):
    shutil.copy2(ROOT/'results/shinan3_refined'/name,OUT/'Blender'/name)
shutil.copy2(ROOT/'results/shinan3_blender/inspect_modules.py',OUT/'Blender/inspect_modules.py')
for p in (ROOT/'results/shinan3_refined').glob('*_refined.png'):shutil.copy2(p,OUT/'Previews'/p.name)
review_names=['source_audit.md','visual_critique.md','data_validation.json','functional_suite.json','physics_validation.json',
              'environment_review.md','environment_browser_validation.json','environment_data_validation.json',
              'layers_validation.json','layers_overview.png','layers_supports.png','layers_laptop.png',
              'cables_review.md','cables_browser_validation.json','cables_overview.png','cables_module_trace.png','cables_single.png','cables_detail.png','cables_laptop.png',
              'environment_overview.png','environment_top.png','environment_detail.png','environment_building.png',
              'browser_state.json','portable_state.json','portable_functional_suite.json',
              'viewer_overview.png','viewer_detail.png','viewer_building.png','viewer_top.png','viewer_walk.png',
              'portable_overview.png','portable_building.png']
review_names += ['interior_browser_validation.json','interior_review.md','interior_independent_review.md','interior_laptop.png','interior_monitor.png','interior_entry.png','interior_click_validation.json','interior_validation_summary.json']
review_names += [p.name for p in (ROOT/'results/shinan3_review').glob('interior_[123]_*.png')]
review_names += ['solar_math_validation.json','solar_browser_validation.json','solar_review.md','solar_morning.png','solar_noon.png','solar_evening.png','solar_winter.png','solar_laptop.png']
for name in review_names:
    p=ROOT/'results/shinan3_review'/name
    if p.exists():shutil.copy2(p,OUT/'Review'/name)
for name in ('cable_model.json','extraction_validation.json','model_validation.json','independent_validation.json','source_manifest.json'):
    shutil.copy2(ROOT/'results/shinan3_cables'/name,OUT/'Electrical'/name)
manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name!='MANIFEST_SHA256.json':
        manifest.append({'file':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
archive=ROOT/'results/Shinan3_3D_Improved_Package.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,Path('Shinan3_3D')/p.relative_to(OUT))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert 'Shinan3_3D/ThreeJS/Shinan3_Viewer.html' in z.namelist()
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(manifest)+1,'crc_check':'passed'},indent=2))

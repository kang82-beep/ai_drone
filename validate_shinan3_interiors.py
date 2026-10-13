from pathlib import Path
import json, hashlib, struct
ROOT=Path(__file__).resolve().parent
REVIEW=ROOT/'results/shinan3_review';MODEL=ROOT/'results/shinan3_refined'
d=json.loads((REVIEW/'interior_browser_validation.json').read_text(encoding='utf-8'))
assert len(d[:3])==3 and all(r['closedBlocked'] and r['entered'] for r in d[:3])
physical=d[-1]['doorPhysics'];doors=[r for r in physical if 'door' in r]
assert len(doors)==7
assert all(all(r[k] for k in ['closedBlocked','entered','occupiedProtected','insideClosedBlocked','exited']) for r in doors)
assert all(r['blocked'] for r in physical if 'door' not in r)
assert d[-1]['arrayCollision']['passed']
assert d[-1]['inventory']['equipment']==62
click=json.loads((REVIEW/'interior_click_validation.json').read_text(encoding='utf-8'))
assert abs(click['angle'])>1.5
native=json.loads((MODEL/'interior_validation.json').read_text(encoding='utf-8'))
assert native['reopen_passed'] and native['pv_groups']==1500 and len(native['room_roots'])==3 and len(native['door_hinges'])==7
glb=(MODEL/'Shinan3_Interiors.glb').read_bytes()
magic,version,size=struct.unpack_from('<III',glb)
assert magic==0x46546c67 and version==2 and size==len(glb)
chunk_size=struct.unpack_from('<I',glb,12)[0];gltf=json.loads(glb[20:20+chunk_size])
assert len([n for n in gltf['nodes'] if 'walkable interior' in n.get('name','')])==3
browser=json.loads((REVIEW/'browser_state.json').read_text(encoding='utf-8'))
assert not [e for e in browser['errors'] if e['method']=='Runtime.exceptionThrown']
result={'status':'passed','keyboard_door_entries':3,'bidirectional_doors':7,'walls':3,'representative_equipment_collisions':3,'equipment_ids':62,'mouse_click_open':True,'array_collision':True,'blender_reopen':True,'preserved_pv_groups':1500,'browser_exceptions':0,'photoreal_aaa_approved':False,'glb_sha256':hashlib.sha256(glb).hexdigest(),'html_sha256':hashlib.sha256((ROOT/'results/shinan3_delivery/ThreeJS/Shinan3_Viewer.html').read_bytes()).hexdigest()}
(REVIEW/'interior_validation_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

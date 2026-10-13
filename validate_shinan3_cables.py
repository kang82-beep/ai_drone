from pathlib import Path
import json,collections,math
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/shinan3_cables'
d=json.loads((OUT/'cable_model.json').read_text(encoding='utf-8'))
t=json.loads((OUT/'3SA-E-11240_D.json').read_text(encoding='utf-8'))['texts']
expected={}
for row in t:
 if not row['text'].startswith('JB-'):continue
 x,y=row['xy'][:2]
 # The parallel-string column is 60 drawing units to the right of the JB identifier.
 values=[v for v in t if v['text'].isdigit() and abs(v['xy'][1]-y)<.2 and 57<v['xy'][0]-x<64]
 assert len(values)==1,(row['text'],values)
 expected[row['text']]=int(values[0]['text'])
actual=collections.Counter(s['jb'] for s in d['strings'])
assert dict(actual)==expected,(actual,expected)
assert len(expected)==82 and sum(expected.values())==1500
assert len(d['module_to_string'])==30000
assert all(len(s['modules'])==20 and len(set(s['modules']))==20 for s in d['strings'])
assert len({m for s in d['strings'] for m in s['modules']})==30000
assert len(set(c['id'] for c in d['paths']))==3506
assert len(set(c['id'] for c in d['schedule']))==3836
eq={e['id']:e for e in d['equipment']};strings={s['id']:s for s in d['strings']}
for p in d['paths']:
 assert p['from'] in eq or p['from'] in strings
 assert p['to'] in eq
 assert all(len(v)==3 and all(math.isfinite(n) for n in v) for v in p['points'])
 if p['kind']=='dc_feeder':
  assert math.dist(p['points'][0],eq[p['from']]['pos'])<.0001
  assert math.dist(p['points'][-1],eq[p['to']]['pos'])<.0001
for index,si in enumerate(d['module_to_string']):assert index in d['strings'][si]['module_indices']
report={'parallel_circuit_table_11240_matches_all_82_junction_boxes':True,'strings':1500,'modules':30000,'inverters':len({s['inverter'] for s in d['strings']}),'unique_cable_paths':3506,'schedule_records':3836,'finite_geometry':True,'dc_feeder_endpoints_coincident':True,'bijective_module_mapping':True,'physical_routing_verified':False}
(OUT/'independent_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

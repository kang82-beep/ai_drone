"""Build an A-only thermal overlay in the existing drawing model coordinates."""
import json
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results/blender_site'
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'Shinan_Character.blend'))
scene = bpy.context.scene
reviewed = '--reviewed' in sys.argv
data = json.loads((OUT / ('thermal_review_verified_a.json' if reviewed else 'thermal_review_registered_a.json')).read_text(encoding='utf-8'))

def collection(name):
    c = bpy.data.collections.new(name); scene.collection.children.link(c); return c

def material(name, color):
    m = bpy.data.materials.new(name); m.diffuse_color = (*color, 1)
    return m

red = material('A_THERMAL_ABNORMAL_PROVISIONAL', (1, .025, .015))
orange = material('A_THERMAL_ATTENTION_PROVISIONAL', (1, .45, .01))
abnormal = collection('11_A_Abnormal_REGISTERED_PROVISIONAL')
attention = collection('12_A_Attention_REGISTERED_PROVISIONAL')
pending = collection('10_A_Module_Links_PENDING') if reviewed else abnormal

def mesh(name, vertices, faces, mat, coll):
    me = bpy.data.meshes.new(name); me.from_pydata(vertices, [], faces); me.update()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob); me.materials.append(mat); return ob

for candidate in data['highlight_modules']:
    bad = candidate['severity'] == 'abnormal'
    confirmed = candidate.get('review_status') == 'confirmed'
    if reviewed and not confirmed:
        # Outline a candidate; do not fill its panel as if identity were verified.
        curve = bpy.data.curves.new('PENDING_' + candidate['id'], 'CURVE')
        curve.dimensions = '3D'; curve.bevel_depth = .035; curve.bevel_resolution = 0
        spline = curve.splines.new('POLY'); spline.points.add(len(candidate['polygon'])-1)
        for point, xyz in zip(spline.points, candidate['polygon']): point.co = (*xyz, 1)
        spline.use_cyclic_u = True
        ob = bpy.data.objects.new('DRAWING_CANDIDATE_' + candidate['id'], curve)
        (pending if bad else attention).objects.link(ob); curve.materials.append(orange)
    else:
        ob = mesh('DRAWING_CANDIDATE_' + candidate['id'], candidate['polygon'], [(0, 1, 2, 3)],
                  red if bad else orange, abnormal if bad else attention)
    ob['result_record_indices'] = json.dumps(candidate['records'])
    ob['matching_status'] = 'Reviewed visual module link; anomaly not a confirmed failure' if confirmed else 'Provisional RGB-to-drawing candidate; thermal GPS not corrected'
    ob['review_status'] = candidate.get('review_status', 'pending')

for index in data['navigation_order']:
    record = data['records'][index]; a, b, z = record['position']
    ob = mesh('RESULT_' + record['module_uid'],
              [(a-.25,b-.25,z),(a+.25,b-.25,z),(a+.25,b+.25,z),(a-.25,b+.25,z),(a,b,z+1.8)],
              [(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)],
              red if not reviewed or record.get('review_status') == 'confirmed' else orange, abnormal)
    for key in ('module_uid', 'validation_zone', 'matching_status', 'drawing_candidate_id', 'max_temp', 'delta_temp'):
        if record.get(key) is not None: ob[key] = record[key]
    ob['record_index'] = index
    ob['review_status'] = record.get('review_status', 'pending')

attention.hide_viewport = True; attention.hide_render = True
root = bpy.data.objects['PLAYER']
for name in ('PLAYER', 'LEG_L', 'LEG_R', 'ARM_L', 'ARM_R'):
    ob = bpy.data.objects[name]
    if ob.animation_data: ob.animation_data.action = None
if data['navigation_order']:
    x, y, z = data['records'][data['navigation_order'][0]]['position']
    root.location = (x, y+4, 8); root.rotation_euler.z = 0
scene.camera = bpy.data.objects['06_Character_follow']
scene['thermal_review_enabled'] = True
scene['thermal_validation_zone'] = 'A'
scene['thermal_coordinate_frame'] = 'drawing_registered_A'
scene['thermal_evidence_review'] = reviewed
scene['thermal_summary'] = f"A-only provisional registration. {data['counts'].get('abnormal', 0)} abnormal records. Thermal GPS requires flight-specific review."
bpy.data.texts.new('THERMAL_REVIEW_JSON').write(json.dumps(data, ensure_ascii=False))
bpy.data.texts.new('A_REGISTRATION_JSON').write(json.dumps(data['registration'], indent=2))
bpy.data.texts.new('THERMAL_README_KO').write('A구역 정사영상과 도면을 정합한 검토용 장면입니다. 빨간 표식은 변환된 GPS 위치이며 모듈 중심으로 강제 이동하지 않았습니다. 패널 색상은 임시 대응 후보입니다. N/P로 이상 결과 이동, I로 원본/크롭 전환. E구역은 정합·검증 대상에서 제외했습니다.')
bpy.data.texts.new('MODULE_LINK_REVIEW_LEGEND').write('빨간 패널: 사람이 영상 근거로 연결을 확인한 이상 의심 결과. 주황 테두리/사각뿔: 모듈 연결 검토 대기. 링크 기각은 정상 판정이 아닙니다. 미표시 모듈은 정상 확정이 아닙니다.' if reviewed else 'Provisional registration preview')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / ('Shinan_Thermal_A_Reviewed.blend' if reviewed else 'Shinan_Thermal_A_Registered.blend')))
print('REGISTERED_A_SAVED', len(data['highlight_modules']), len(data['navigation_order']), flush=True)

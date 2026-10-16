import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from PIL import Image

from pv_inspector import history
from pv_inspector.diagnosis import diagnose, load_kb
from pv_inspector.llm_agent import Agent, build_messages, clean_jpeg, merge, validate
from pv_inspector.work_orders import build

KB = load_kb()


def verdict(module, verdict='inspect', string='S1', jb='JB-1', votes=2, views=3, rel=3.0, east=0.0):
    return dict(drawing_module_id=module, string_id=string, jb_id=jb, inverter_id='INV1', verdict=verdict,
                flagged_votes=votes, usable_views=views, relative_temp=rel, only_untrusted=False, east_m=east, north_m=0.0,
                verdict_reason='')


def views(module, kinds, start=0, shadow=False, dark=0.0):
    return [dict(image_id=f'DJI_20251030091{start + i:03d}_{start + i:04d}_T', module_id=i, module=module, final='attention',
                 edge=False, type=k, shadow_suspect=str(shadow), hot_on_rgb_dark=dark) for i, k in enumerate(kinds)]


def run(verdicts, patterns, strings=None, cable=None):
    v = pd.DataFrame(verdicts)
    p = pd.DataFrame(patterns)
    s = pd.DataFrame(strings or [dict(string_id='S1', string_delta=0.0, string_flag=False)])
    linked = pd.DataFrame([dict(image_id=r['image_id'], module_id=r['module_id'], neighbor_delta_mean=3.0, max_temp=40.0)
                           for r in patterns])
    return {d['module_id']: d for d in diagnose(v, s, p, linked, cable, KB)}


class DiagnosisTests(unittest.TestCase):
    def test_repeated_diode_band_is_an_electrical_check(self):
        d = run([verdict('A')], views('A', ['diode', 'diode']))['A']
        self.assertEqual(d['primary'], '바이패스 다이오드 동작 또는 고장')
        self.assertEqual((d['kind'], d['urgency'], d['candidates'][0]['confidence']), ('electrical', '우선', '높음'))
        self.assertTrue(all('프레임' in e['text'] for e in d['candidates'][0]['evidence']))

    def test_hot_string_comes_first_and_counts_its_loss_once(self):
        strings = [dict(string_id='S1', string_delta=2.5, string_flag=True)]
        out = run([verdict('A'), verdict('B')], views('A', ['single_cell', 'single_cell']) + views('B', ['whole_module'] * 2, 10), strings)
        self.assertEqual(out['A']['primary'], '스트링 단선, 퓨즈 용단, 커넥터 이탈')
        orders, _ = build(list(out.values()), KB, 'F1')
        self.assertEqual(sum(o['loss_w'] for o in orders), 5000)

    def test_one_hit_in_many_views_is_a_reflection(self):
        d = run([verdict('A', 'recheck', votes=1, views=4)], views('A', ['single_cell']))['A']
        self.assertEqual(d['primary'], '태양 반사')
        self.assertTrue(d['exclude'])

    def test_cell_hotspot_on_a_dark_patch_is_soiling_but_keeps_the_defect(self):
        d = run([verdict('A')], views('A', ['multi_cell', 'multi_cell'], dark=0.8))['A']
        self.assertEqual([c['rule'] for c in d['candidates']][:2], ['soiling', 'cell_defect'])

    def test_mixed_views_with_a_shadow_keep_the_shade_as_a_candidate(self):
        patterns = views('A', ['whole_module']) + [dict(views('A', ['partial_shade'], 5)[0], shadow_suspect='True')]
        d = run([verdict('A')], patterns)['A']
        self.assertIn('structure_shade', [c['rule'] for c in d['candidates']])

    def test_pid_needs_three_cell_hotspots_at_one_end(self):
        cable = {'strings': [{'id': 'S1', 'modules': [f'M{i:02}' for i in range(20)]}]}
        rows = [verdict(f'M{i:02}') for i in (0, 1, 2)]
        patterns = sum((views(f'M{i:02}', ['single_cell'] * 2, 10 * i) for i in (0, 1, 2)), [])
        out = run(rows, patterns, cable=cable)
        self.assertIn('pid', [c['rule'] for c in out['M00']['candidates']])
        out = run(rows[:2], patterns[:4], cable=cable)
        self.assertNotIn('pid', [c['rule'] for c in out['M00']['candidates']])


class WorkOrderTests(unittest.TestCase):
    def test_single_hit_recheck_waits_for_the_next_flight(self):
        out = run([verdict('A'), verdict('B', 'recheck', votes=1, views=2)],
                  views('A', ['diode', 'diode']) + views('B', ['single_cell'], 10))
        orders, _ = build(list(out.values()), KB, 'F1')
        kinds = {o['action_kind']: o['modules'] for o in orders}
        self.assertEqual(kinds['electrical'], ['A'])
        self.assertEqual(kinds['recheck'], ['B'])

    def test_orders_group_by_junction_box_and_kind_and_get_a_route(self):
        out = run([verdict('A', jb='JB-1', east=0), verdict('B', jb='JB-1', east=1), verdict('C', jb='JB-2', east=500)],
                  views('A', ['diode'] * 2) + views('B', ['diode'] * 2, 10) + views('C', ['multi_cell'] * 2, 20))
        orders, _ = build(list(out.values()), KB, 'F1')
        jb1 = [o for o in orders if o['jb_id'] == 'JB-1']
        self.assertEqual(len(jb1), 1)
        self.assertEqual(sorted(jb1[0]['modules']), ['A', 'B'])
        self.assertEqual(sorted(o['route_order'] for o in orders), list(range(1, len(orders) + 1)))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = history.connect(Path(self.tmp.name) / 'h.db')

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def flight(self, name, flagged):
        rows = [dict(verdict(m, 'inspect' if m in flagged else 'normal'), observations=3) for m in ('A', 'B', 'C')]
        history.import_flight(self.db, name, '.', rows)

    def test_issue_then_all_clear_closes_the_order(self):
        self.flight('F1', ['A', 'B'])
        out = run([verdict('A'), verdict('B')], views('A', ['diode'] * 2) + views('B', ['diode'] * 2, 10))
        orders, _ = build(list(out.values()), KB, 'F1')
        history.save_orders(self.db, 'F1', orders)
        oid = orders[0]['order_id']
        history.set_status(self.db, oid, '발행', '운영자')
        history.save_result(self.db, oid, 'A', cause='이상 없음', inspector='현장')
        self.assertEqual(history.snapshot(self.db, 'F1')['orders'][0]['status'], '발행')
        history.save_result(self.db, oid, 'B', cause='이상 없음', inspector='현장')
        order = history.snapshot(self.db, 'F1')['orders'][0]
        self.assertEqual((order['status'], order['approved_by']), ('종결', '운영자'))

    def test_regenerating_keeps_issued_orders_and_open_ones_carry_over(self):
        self.flight('F1', ['A'])
        out = run([verdict('A')], views('A', ['diode'] * 2))
        orders, _ = build(list(out.values()), KB, 'F1')
        history.save_orders(self.db, 'F1', orders)
        history.set_status(self.db, orders[0]['order_id'], '발행')
        history.save_orders(self.db, 'F1', orders)
        self.assertEqual(history.snapshot(self.db, 'F1')['orders'][0]['status'], '발행')
        self.flight('F2', ['B'])
        snap = history.snapshot(self.db, 'F2')
        self.assertEqual([o['order_id'] for o in snap['carried_over']], [orders[0]['order_id']])
        self.assertEqual(snap['comparison'], {'B': 'new', 'A': 'resolved'})

    def test_manual_add_and_remove_from_a_draft(self):
        self.flight('F1', [])
        oid = history.add_manual(self.db, 'F1', 'C', '운영자')
        self.assertEqual(history.snapshot(self.db, 'F1')['orders'][0]['modules'], ['C'])
        history.remove_module(self.db, oid, 'C')
        self.assertEqual(history.snapshot(self.db, 'F1')['orders'], [])


class FakeClient:
    def __init__(self, replies):
        self.replies, self.sent = list(replies), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.sent.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.replies.pop(0), ensure_ascii=False)))])


class LlmAgentTests(unittest.TestCase):
    def diagnosis(self):
        strings = [dict(string_id='S1', string_delta=2.5, string_flag=True)]
        return run([verdict('A')], views('A', ['multi_cell'] * 2, dark=0.0), strings)['A']

    def reply(self, cause='오염에 의한 부분 음영', evidence=('E1',)):
        return {'appearance': {'label': '오염·새똥', 'confidence': '높음', 'note': '셀 위에 얼룩'},
                'causes': [{'cause': cause, 'confidence': '중간', 'evidence': list(evidence), 'reason': '발열 위치에 얼룩'}],
                'action': '청소 후 재촬영', 'urgency': '보통', 'needs_review': False}

    def test_reply_outside_the_rules_is_refused(self):
        _, ids = build_messages(self.diagnosis(), KB, [])
        self.assertIsNone(validate(self.reply(cause='외계인'), KB, ids))
        self.assertIsNone(validate(self.reply(evidence=('E99',)), KB, ids))
        self.assertIsNotNone(validate(self.reply(), KB, ids))

    def test_merge_keeps_every_rule_warning_and_the_stricter_urgency(self):
        d = self.diagnosis()
        _, ids = build_messages(d, KB, [])
        merged = merge(d, validate(self.reply(), KB, ids), KB, 'test-model')
        rules = [c['rule'] for c in merged['candidates']]
        self.assertEqual(merged['primary'], '오염에 의한 부분 음영')
        self.assertIn('string_wide', rules)
        self.assertEqual(merged['urgency'], '우선')
        self.assertEqual(merged['appearance']['label'], '오염·새똥')
        self.assertEqual(merged['kind'], 'electrical')  # the hot string still gets its field check

    def test_reranking_cannot_take_a_field_check_out_of_the_field(self):
        d = run([verdict('A')], views('A', ['multi_cell', 'multi_cell']))['A']
        self.assertEqual(d['kind'], 'field_check')
        _, ids = build_messages(d, KB, [])
        reply = dict(self.reply(cause='구조물·수목 음영'), appearance={'label': '그림자', 'confidence': '중간', 'note': ''})
        self.assertEqual(merge(d, validate(reply, KB, ids), KB, 'm')['kind'], 'field_check')

    def test_agent_retries_once_then_gives_up(self):
        bad = dict(self.reply(), urgency='당장')
        agent = Agent('test-model', client=FakeClient([bad, bad]))
        self.assertIsNone(agent.review(self.diagnosis(), KB, []))
        agent = Agent('test-model', client=FakeClient([bad, self.reply()]))
        self.assertIsNotNone(agent.review(self.diagnosis(), KB, []))

    def test_sent_text_has_no_equipment_address(self):
        client = FakeClient([self.reply()])
        Agent('test-model', client=client).review(self.diagnosis(), KB, [])
        text = json.dumps(client.sent[0]['messages'], ensure_ascii=False)
        self.assertNotIn('S1', text.replace('E1', ''))
        self.assertNotIn('JB-1', text)

    def test_crops_lose_their_exif(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'crop.jpg'
            image = Image.fromarray(np.full((64, 64, 3), 128, np.uint8))
            exif = Image.Exif()
            exif[0x010F] = 'DJI'          # make; GPS IFD would ride the same block
            image.save(path, exif=exif.tobytes())
            self.assertIn(b'Exif', path.read_bytes())
            import base64
            data = base64.b64decode(clean_jpeg(path))
            self.assertNotIn(b'Exif', data)
            self.assertNotIn(b'DJI', data)
            Image.open(io.BytesIO(data)).verify()


class AiDowngradeTests(unittest.TestCase):
    def reviewed(self, rule_kind, label, confidence='높음', rules=('cell_defect', 'structure_shade'), module='A'):
        return dict(module_id=module, verdict='inspect', safety=False, kind=rule_kind, rule_kind=rule_kind,
                    rule_rules=list(rules), candidates=[{'rule': r} for r in rules],
                    appearance={'label': label, 'confidence': confidence, 'note': ''})

    def kind(self, d, every=0):
        from pv_inspector.work_orders import work_kind
        kb = dict(KB, ai_downgrade=dict(KB['ai_downgrade'], audit_every=every))
        return work_kind(d, kb)

    def test_shadow_confirmed_by_model_and_rules_waits_for_the_next_flight(self):
        d = self.reviewed('field_check', '그림자')
        self.assertEqual(self.kind(d), 'recheck')
        self.assertIn('그림자', d['ai_downgraded'])

    def test_grass_turns_a_field_check_into_weeding(self):
        self.assertEqual(self.kind(self.reviewed('field_check', '풀·식생')), 'weed')

    def test_no_downgrade_without_a_shade_cause_from_the_rules_or_a_firm_look(self):
        self.assertEqual(self.kind(self.reviewed('field_check', '그림자', rules=('cell_defect',))), 'field_check')
        self.assertEqual(self.kind(self.reviewed('field_check', '그림자', confidence='낮음')), 'field_check')

    def test_a_medium_confidence_look_is_enough(self):
        self.assertEqual(self.kind(self.reviewed('field_check', '그림자', confidence='중간')), 'recheck')
        self.assertEqual(self.kind(self.reviewed('weed', '이상 없음', confidence='중간', rules=('vegetation',))), 'recheck')

    def test_no_downgrade_when_the_model_itself_raised_the_work(self):
        d = self.reviewed('weed', '이상 없음', confidence='중간', rules=('vegetation',))
        d['kind'] = 'field_check'
        self.assertEqual(self.kind(d), 'field_check')
        d = self.reviewed('field_check', '풀·식생', rules=('cell_defect', 'vegetation'))
        d['kind'] = 'electrical'
        self.assertEqual(self.kind(d), 'electrical')

    def test_electrical_checks_are_never_downgraded(self):
        self.assertEqual(self.kind(self.reviewed('electrical', '그림자', rules=('string_wide', 'structure_shade'))), 'electrical')

    def test_audit_sample_stays_in_the_field(self):
        d = self.reviewed('field_check', '그림자')
        self.assertEqual(self.kind(d, every=1), 'field_check')
        self.assertIn('검증 표본', d['ai_audit'])


if __name__ == '__main__':
    unittest.main()

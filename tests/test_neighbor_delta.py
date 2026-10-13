import unittest

from pv_inspector.field_review import review_record
from pv_inspector.neighbor_delta import add_neighbor_delta, capture_condition


class NeighborDeltaTests(unittest.TestCase):
    def frame(self, extra=None, count=40, image='A'):
        rows = []
        for i in range(count):
            u, v = 100 + 110 * (i % 10), 100 + 200 * (i // 10)
            # Smooth gradient across the frame must not look like a defect.
            mean = 40 + 0.002 * u + 0.001 * v
            rows.append(dict(image_id=image, temperature_status='ok', mean_temp=mean,
                             max_temp=mean + 2, centroid_u=u, centroid_v=v))
        for index, offset in (extra or {}).items():
            rows[index]['mean_temp'] += offset
            rows[index]['max_temp'] += offset
        return rows

    def test_gradient_is_not_flagged_and_warm_module_is(self):
        rows = add_neighbor_delta(self.frame({17: 4.0}))
        self.assertTrue(rows[17]['neighbor_flag'])
        self.assertAlmostEqual(rows[17]['neighbor_delta_mean'], 4.0, places=1)
        self.assertEqual(sum(r['neighbor_flag'] for r in rows), 1)
        self.assertLess(abs(rows[0]['neighbor_delta_mean']), 0.2)

    def test_warm_string_does_not_hide_itself(self):
        rows = add_neighbor_delta(self.frame({i: 3.5 for i in range(10, 20)}))
        self.assertTrue(all(rows[i]['neighbor_flag'] for i in range(10, 20)))
        self.assertFalse(any(rows[i]['neighbor_flag'] for i in range(10)))

    def test_missing_temperature_and_small_frames_are_not_zero(self):
        rows = self.frame(count=3)
        rows.append(dict(image_id='B', temperature_status='invalid_raw_pixels', mean_temp=None,
                         max_temp=None, centroid_u=1, centroid_v=1))
        add_neighbor_delta(rows)
        self.assertEqual(rows[0]['neighbor_delta_status'], 'insufficient_modules')
        self.assertEqual(rows[3]['neighbor_delta_status'], 'temperature_unavailable')
        self.assertTrue(all(r['neighbor_delta_mean'] is None and not r['neighbor_flag'] for r in rows))

    def test_irradiance_scaling_and_hold(self):
        self.assertEqual(capture_condition(0, 600), 'irradiance_unrecorded')
        self.assertEqual(capture_condition(None, 600), 'irradiance_unrecorded')
        rows = add_neighbor_delta(self.frame({5: 2.0}), irradiance=500)
        self.assertAlmostEqual(rows[5]['neighbor_delta_norm'], 4.0, places=1)
        self.assertTrue(rows[5]['neighbor_flag'])
        self.assertTrue(all(r['reading_hold'] and r['capture_condition'] == 'low_irradiance' for r in rows))
        rows = add_neighbor_delta(self.frame({5: 2.0}), irradiance=900)
        self.assertFalse(rows[5]['neighbor_flag'])
        self.assertFalse(rows[5]['reading_hold'])
        self.assertIsNone(add_neighbor_delta(self.frame())[0]['neighbor_delta_norm'])

    def test_hold_reaches_field_review(self):
        row = dict(final='normal', temperature_status='ok', mean_temp=40, max_temp=41, delta_temp=1,
                   prob_normal=.9, prob_attention=.08, prob_abnormal=.02, mod_lat=34, mod_lon=126,
                   reading_hold=True)
        self.assertIn('판독 보류', review_record(row)['review_reason'])
        self.assertFalse(review_record(dict(row, reading_hold=False))['review_required'])


if __name__ == '__main__':
    unittest.main()

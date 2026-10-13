import json
import unittest
from unittest.mock import patch
import numpy as np
from register_thermal_a import transform_points, check_sources


class RegistrationTests(unittest.TestCase):
    def test_affine_round_trip_includes_rotation_scale_translation(self):
        matrix = np.array([[.98, -.04], [.03, 1.02], [-24., -15.]])
        points = np.array([[50., 70.], [175., 120.]])
        mapped = transform_points(points, matrix)
        np.testing.assert_allclose((mapped-matrix[2]) @ np.linalg.inv(matrix[:2]), points)

    def test_stale_sources_are_rejected(self):
        calibration = {'fingerprints': {'layout': 'old'}, 'orthomosaic': {'transform': [1]}}
        with patch('register_thermal_a.fingerprints', return_value={'layout': 'new'}):
            with self.assertRaises(ValueError):
                check_sources(calibration, {'orthomosaic': calibration['orthomosaic']})
        with patch('register_thermal_a.fingerprints', return_value={'layout': 'old'}):
            with self.assertRaises(ValueError):
                check_sources(calibration, {'orthomosaic': {'transform': [2]}})

    def test_saved_result_preserves_unsnapped_gps(self):
        from register_thermal_a import OUT
        data = json.loads((OUT/'thermal_review_registered_a.json').read_text(encoding='utf-8'))
        for record in data['records']:
            self.assertTrue(record['validation_zone'].startswith('A'))
            if record['orthomosaic_position']:
                old = np.array(record['orthomosaic_position'][:2]) - [data['orthomosaic']['offset_x'], 0]
                expected = transform_points([old], data['registration']['matrix_3x2'])[0]
                np.testing.assert_allclose(record['position'][:2], expected)
        calibration = data['registration']
        self.assertFalse(set(calibration['training_strips']) & set(calibration['holdout_strips']))
        self.assertLess(calibration['holdout']['p95_m'], .8)


if __name__ == '__main__': unittest.main()

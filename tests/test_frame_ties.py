import unittest

import cv2
import numpy as np
import pandas as pd

from pv_inspector.frame_ties import measure, pixel_to_ground


class FrameTieTests(unittest.TestCase):
    def test_tie_is_the_gps_error_between_two_frames(self):
        frame = pd.Series(dict(img_w=640, img_h=512, gimbal_yaw=90.0, gimbal_pitch=-90.0, gimbal_roll=180.0))
        jacobian = pixel_to_ground(frame, 30.0)
        rng = np.random.default_rng(0)
        ground = cv2.GaussianBlur(rng.normal(0, 1, (700, 1100)).astype(np.float32), (0, 0), 3)
        true_motion = np.array([0.3, 6.0])                      # north, east metres
        pixels = -np.linalg.solve(jacobian, true_motion)        # content moves the other way
        a = ground[100:612, 100:740]
        shift = np.float32([[1, 0, pixels[0]], [0, 1, pixels[1]]])
        b = cv2.warpAffine(ground, shift, (1100, 700))[100:612, 100:740]
        gps_error = np.array([0.1, -0.2])
        tie = measure(a, b, jacobian, true_motion + gps_error)
        np.testing.assert_allclose([tie['tie_north_m'], tie['tie_east_m']], -gps_error, atol=0.02)
        self.assertGreater(tie['response'], 0.3)

    def test_no_tie_without_overlap(self):
        frame = pd.Series(dict(img_w=640, img_h=512, gimbal_yaw=90.0, gimbal_pitch=-90.0, gimbal_roll=180.0))
        image = np.zeros((512, 640), np.float32)
        self.assertIsNone(measure(image, image, pixel_to_ground(frame, 30.0), np.array([0.0, 40.0])))


if __name__ == '__main__':
    unittest.main()

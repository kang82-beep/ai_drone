import math
import unittest

import numpy as np
import pandas as pd

from pv_inspector.camera_calibration import EARTH_R, camera_positions, fit, ground_offsets, reproject
from pv_inspector.geolocation import camera_model_text, ground_offset

LAT0, LON0 = 34.8, 126.1


class Flat:
    """Stand-in for GeoTransform: drawing metres are local east/north metres."""

    def __call__(self, latlon):
        latlon = np.asarray(latlon, float)
        north = np.radians(latlon[:, 0] - LAT0) * EARTH_R
        east = np.radians(latlon[:, 1] - LON0) * EARTH_R * math.cos(math.radians(LAT0))
        return np.column_stack((east, north))


def latlon(east, north):
    return LAT0 + math.degrees(north / EARTH_R), LON0 + math.degrees(east / (EARTH_R * math.cos(math.radians(LAT0))))


def flight(true_height=28.5, yaw_bias=-0.7, right=-0.09, stored_height=30.0, seed=0):
    """Frames on east/west lines over a module grid, projected with the uncorrected model."""
    rng = np.random.default_rng(seed)
    site = pd.DataFrame([dict(drawing_module_id=f'M{i}-{j}', x=i * 1.008, n=j * 1.425) for i in range(60) for j in range(30)])
    width, height = 1280, 1024
    focal = math.hypot(width, height) * 52.0 / math.hypot(36, 24)
    rows = []
    for k, (cx, cn, yaw) in enumerate([(e, n, y) for n, y in ((12, 90.0), (28, -90.0)) for e in range(12, 50, 6)]):
        gps = np.array([cx, cn]) + rng.normal(0, 0.1, 2)
        t = math.radians(yaw + yaw_bias)
        lens = np.array([-right * math.sin(t), right * math.cos(t)])  # camera sits beside the GPS point
        true_cam = gps + lens[::-1]  # (east, north)
        for _, m in site[(abs(site.x - cx) < 8) & (abs(site.n - cn) < 6)].iterrows():
            north, east = m.n - true_cam[1], m.x - true_cam[0]
            # Invert the nadir projection: ground offset = height * rotation * (x, y).
            a = ground_offset(width / 2 + 1, height / 2, width, height, yaw + yaw_bias, -90, 180, true_height)
            b = ground_offset(width / 2, height / 2 + 1, width, height, yaw + yaw_bias, -90, 180, true_height)
            uv = np.linalg.solve(np.column_stack((a, b)), [north, east])
            u, v = width / 2 + uv[0], height / 2 + uv[1]
            n_off, e_off = ground_offset(u, v, width, height, yaw, -90, 180, stored_height)
            lat, lon = latlon(gps[0] + e_off, gps[1] + n_off)
            rows.append(dict(image_id=f'F{k:02}', drawing_module_id=m.drawing_module_id, centroid_u=u, centroid_v=v,
                             img_w=width, img_h=height, gimbal_yaw=yaw, gimbal_pitch=-90.0, gimbal_roll=180.0,
                             camera_to_surface_m=stored_height, mod_lat=lat, mod_lon=lon))
    return site, pd.DataFrame(rows)


class CameraCalibrationTests(unittest.TestCase):
    def test_vectorised_offsets_match_scalar_projection(self):
        _, linked = flight()
        camera = dict(yaw_offset_deg=0.4, forward_m=0.05, right_m=-0.1)
        fast = ground_offsets(linked.head(5), camera)
        for (_, r), expected in zip(linked.head(5).iterrows(), fast):
            got = ground_offset(r.centroid_u, r.centroid_v, r.img_w, r.img_h, r.gimbal_yaw, r.gimbal_pitch,
                                r.gimbal_roll, r.camera_to_surface_m, camera=camera)
            np.testing.assert_allclose(got, expected, atol=1e-9)

    def test_recovers_height_yaw_and_side_offset(self):
        site, linked = flight()
        camera, lower, report = fit(linked, site, Flat())
        self.assertAlmostEqual(lower, 1.5, delta=0.05)
        self.assertAlmostEqual(camera['yaw_offset_deg'], -0.7, delta=0.05)
        self.assertAlmostEqual(camera['right_m'], -0.09, delta=0.03)
        self.assertLess(report['residual_in_frame_after']['median_m'], 0.02)

    def test_reprojection_keeps_camera_position_and_records_model(self):
        _, linked = flight()
        camera = dict(yaw_offset_deg=-0.7, forward_m=0.0, right_m=0.0)
        out = reproject(linked, camera, lower_m=1.5)
        self.assertTrue((out.geo_camera_model == camera_model_text(camera)).all())
        np.testing.assert_allclose(out.camera_to_surface_m, 28.5)
        np.testing.assert_allclose(camera_positions(out), camera_positions(linked), atol=1e-9)


if __name__ == '__main__':
    unittest.main()

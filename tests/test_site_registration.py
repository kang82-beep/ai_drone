import math
import unittest

import numpy as np
import pandas as pd

from pv_inspector.site_registration import register, summarise

LAT0, LON0 = 34.775, 126.161
M_LAT, M_LON = 110950.0, 111320.0 * math.cos(math.radians(LAT0))


def latlon(x, n):
    return LAT0 + n / M_LAT, LON0 + x / M_LON


def make_site(rows=12, columns=40):
    """Paired rows like the drawing; every third pair starts later so row ends are visible."""
    records = []
    for r in range(rows):
        n = (r // 2) * 5.82 + (r % 2) * 1.425
        start = 6 if (r // 2) % 3 == 0 else 0
        for c in range(start, columns):
            records.append(dict(drawing_module_id=f'R{r:02}-M{c:02}', x=c * 1.008, n=n,
                                string_id=f'S{r:02}-{c // 20}', jb_id='JB-1', inverter_id='INV1'))
    return pd.DataFrame(records)


def observe(site, shift=(0.0, 0.0), scale=1.05, seed=1):
    """Frames see every module in a window; projection has a scale error and noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for fx in range(0, 36, 5):
        for fn in (0, 10, 20):
            seen = site[(site.x.between(fx, fx + 14)) & (site.n.between(fn, fn + 14))]
            if len(seen) < 8:
                continue
            centre = seen[['x', 'n']].mean().to_numpy()
            for _, m in seen.iterrows():
                p = centre + scale * (np.array([m.x, m.n]) - centre) + shift + rng.normal(0, 0.04, 2)
                lat, lon = latlon(*p)
                rows.append(dict(image_id=f'F{fx:02}{fn:02}', mod_lat=lat, mod_lon=lon, truth=m.drawing_module_id,
                                 final='attention' if m.drawing_module_id == 'R03-M10' else 'normal', delta_temp=2.0))
    return pd.DataFrame(rows)


def reference(site, shift=(0.0, 0.0)):
    out = []
    for _, m in site.iloc[::7].iterrows():
        lat, lon = latlon(m.x + shift[0], m.n + shift[1])
        out.append(dict(x=m.x, n=m.n, latitude=lat, longitude=lon))
    return out


class SiteRegistrationTests(unittest.TestCase):
    def test_scale_error_and_small_offset_are_absorbed(self):
        site = make_site()
        work, frames, report = register(observe(site, shift=(0.2, -0.15)), site, reference(site))
        linked = work[work.link_status == 'module_candidate']
        self.assertGreater(len(linked) / len(work), 0.97)
        self.assertTrue((linked.drawing_module_id == linked.truth).all())
        self.assertTrue(report['whole_pitch_test']['resolved'])

    def test_row_ends_correct_a_one_module_map_error(self):
        site = make_site()
        # The map alignment is wrong by exactly one module pitch to the east.
        work, _, report = register(observe(site), site, reference(site, shift=(1.008, 0.0)))
        linked = work[work.link_status == 'module_candidate']
        self.assertTrue(report['whole_pitch_test']['resolved'])
        self.assertGreater((linked.drawing_module_id == linked.truth).mean(), 0.99)

    def test_offset_growing_across_the_site_is_absorbed(self):
        # A map alignment with a small rotation/scale error: the offset drifts by
        # more than a module over the site, beyond what one shift can absorb.
        site = make_site(rows=24, columns=80)
        rng = np.random.default_rng(3)
        rows = []
        for fx in range(0, 70, 6):
            for fn in range(0, 60, 8):
                seen = site[(site.x.between(fx, fx + 14)) & (site.n.between(fn, fn + 14))]
                if len(seen) < 8:
                    continue
                for _, m in seen.iterrows():
                    drift = np.array([0.006 * m.n, 0.02 * m.x - 0.4])
                    lat, lon = latlon(*(np.array([m.x, m.n]) + drift + rng.normal(0, 0.04, 2)))
                    rows.append(dict(image_id=f'F{fx:02}{fn:02}', mod_lat=lat, mod_lon=lon,
                                     truth=m.drawing_module_id, final='normal', delta_temp=1.0))
        work, frames, _ = register(pd.DataFrame(rows), site, reference(site))
        self.assertGreater((frames.status == 'registered').mean(), 0.9)
        linked = work[work.drawing_module_id.notna()]
        self.assertGreater((linked.drawing_module_id == linked.truth).mean(), 0.99)

    def test_flight_lines_carry_the_module_count_through_drifting_gps(self):
        # Lines fly along long rows; GPS drifts along the track by more than half a module
        # and flips its offset with the flight direction. Frames alone snap to wrong modules.
        site = make_site(rows=24, columns=120)
        site = site[~site.x.between(55, 62)]  # a road across the rows, as on the real site
        rng = np.random.default_rng(5)
        rows, second = [], 0
        for line, fn in enumerate((0, 5.8, 11.6, 17.4, 23.2, 29.0, 34.8, 40.6)):
            east = line % 2 == 0
            drift = 0.0
            for step in range(20):
                fx = step * 5.5 if east else 105 - step * 5.5
                drift += rng.normal(0, 0.12)
                error = np.array([0.45 * (1 if east else -1) + drift + 0.004 * fn, 0.0])
                seen = site[(site.x.between(fx - 6, fx + 6)) & (site.n.between(fn - 1, fn + 8))]
                second += 1
                image = f'DJI_20251030{9 + second // 3600:02}{second // 60 % 60:02}{second % 60:02}_{second:04}_T'
                for _, m in seen.iterrows():
                    lat, lon = latlon(*(np.array([m.x, m.n]) + error + rng.normal(0, 0.03, 2)))
                    rows.append(dict(image_id=image, mod_lat=lat, mod_lon=lon, truth=m.drawing_module_id,
                                     gimbal_yaw=90.0 if east else -90.0, final='normal', delta_temp=1.0))
            second += 30  # turn between lines
        work, frames, report = register(pd.DataFrame(rows), site, reference(site))
        linked = work[work.drawing_module_id.notna()]
        self.assertGreater((linked.drawing_module_id == linked.truth).mean(), 0.99)
        self.assertEqual(report['flight_lines']['lines'], 8)
        self.assertAlmostEqual(report['flight_lines']['trend']['along_track_m'], -0.45, delta=0.1)  # correction undoes the error

    def test_periodic_interior_is_reported_unresolved(self):
        site = make_site()
        interior = site[site.x.between(12, 30)]
        frame = observe(interior.assign(x=interior.x), scale=1.0)
        frame = frame[frame.image_id == frame.image_id.iloc[0]]
        work, _, report = register(frame, site, reference(site))
        self.assertFalse(report['whole_pitch_test']['resolved'])
        self.assertFalse((work.link_status == 'module_candidate').any())
        self.assertTrue((work.link_status == 'module_candidate_pitch_unresolved').any())

    def test_no_two_observations_share_a_module_in_one_frame(self):
        site = make_site()
        obs = observe(site)
        obs = pd.concat([obs, obs.iloc[:5]], ignore_index=True)
        work, _, _ = register(obs, site, reference(site))
        linked = work[work.drawing_module_id.notna()]
        self.assertFalse(linked.duplicated(['image_id', 'drawing_module_id']).any())
        self.assertIn('same_frame_collision', set(work.link_reason))

    def test_summary_groups_by_string_and_keeps_worst(self):
        site = make_site()
        work, _, _ = register(observe(site), site, reference(site))
        modules, strings = summarise(work)
        hit = modules[modules.drawing_module_id == 'R03-M10'].iloc[0]
        self.assertEqual(hit.worst_final, 'attention')
        self.assertGreater(hit.observations, 1)
        top = strings.iloc[0]
        self.assertEqual((top.string_id, top.modules_flagged, top.flagged_modules), ('S03-0', 1, 'R03-M10'))


if __name__ == '__main__':
    unittest.main()

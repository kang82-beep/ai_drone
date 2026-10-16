import unittest

import pandas as pd

from pv_inspector.module_verdict import judge, turn_frames


def frame(second, yaw):
    return dict(image_id=f'DJI_20251030{9:02}{second // 60:02}{second % 60:02}_{second:04}_T', gimbal_yaw=yaw)


def flight():
    """Two straight lines (east, then west) with one turn frame between them."""
    frames = [frame(s, 90.0) for s in range(0, 10, 2)] + [frame(20, 0.0)] + [frame(s, -90.0) for s in range(40, 50, 2)]
    return frames, frames[5]['image_id']


def view(f, module, hot=False):
    return dict(f, drawing_module_id=module, string_id='S1', jb_id='JB-1', inverter_id='INV1',
                final='abnormal' if hot else 'normal', prob_abnormal=0.9 if hot else 0.05, delta_temp=3.0,
                mean_temp=40.0 if hot else 30.0, centroid_u=640, centroid_v=512, img_w=1280, img_h=1024)


class TurnFrameTests(unittest.TestCase):
    def setUp(self):
        self.frames, self.turn = flight()
        catalog = pd.DataFrame([dict(module_id=m, east_m=i * 1.0, north_m=0.0) for i, m in enumerate('ABCD')])
        rows = []
        for f in self.frames:
            if f['image_id'] == self.turn:
                rows += [view(f, 'A', hot=True), view(f, 'C', hot=True)]   # a glint while turning
            else:
                rows += [view(f, 'A'), view(f, 'B', hot=True), view(f, 'D')]
        self.linked = pd.DataFrame(rows)
        modules, _ = judge(self.linked, catalog)
        self.verdict = modules.set_index('drawing_module_id').verdict

    def test_turn_frame_is_found(self):
        self.assertEqual(turn_frames(self.linked), {self.turn})

    def test_heat_seen_only_while_turning_does_not_flag(self):
        self.assertEqual(self.verdict['A'], 'normal')

    def test_module_seen_only_while_turning_needs_a_retake(self):
        self.assertEqual(self.verdict['C'], 'retake')

    def test_straight_line_evidence_still_counts(self):
        self.assertEqual(self.verdict['B'], 'inspect')
        self.assertEqual(self.verdict['D'], 'normal')


if __name__ == '__main__':
    unittest.main()

import math
import unittest
from pv_inspector.drawing_model import SPEC, build_array


class DrawingModelTests(unittest.TestCase):
    def test_dimension_chain_and_count(self):
        modules=build_array()
        self.assertEqual(len(modules),80)
        self.assertEqual(len({m['id'] for m in modules}),80)
        self.assertAlmostEqual(SPEC.group_width,10.235)
        self.assertAlmostEqual(SPEC.width,41.240)
        xs=[v[0] for m in modules for v in m['vertices']]
        self.assertAlmostEqual(max(xs)-min(xs),41.240)

    def test_module_edges_and_slope(self):
        for m in build_array():
            v=m['vertices']
            self.assertAlmostEqual(math.dist(v[0],v[1]),1.001)
            self.assertAlmostEqual(math.dist(v[1],v[2]),1.675)
            self.assertAlmostEqual(math.dist(v[0],v[4]),.034)
            self.assertAlmostEqual(math.degrees(math.atan2(v[2][2]-v[1][2],v[2][1]-v[1][1])),22)

    def test_gaps_and_datum(self):
        modules=build_array()
        self.assertAlmostEqual(modules[1]['vertices'][0][0]-modules[0]['vertices'][1][0],.025)
        self.assertAlmostEqual(modules[20]['vertices'][0][0]-modules[9]['vertices'][1][0],.100)
        self.assertIsNone(SPEC.ground_clearance)
        self.assertAlmostEqual(modules[0]['vertices'][0][2],0)


if __name__=='__main__':unittest.main()

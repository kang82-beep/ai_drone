import unittest
from shapely.geometry import box, Polygon
from prepare_blender_thermal import validation_zone

class ValidationScopeTests(unittest.TestCase):
    def test_only_a_module_positions_are_selected(self):
        zones=[('A1',box(0,0,1,1)),('E1',box(2,0,3,1)),('B1',box(4,0,5,1))]
        self.assertEqual(validation_zone(.5,.5,zones),'A1')
        for lon in (2.5,4.5,9):self.assertIsNone(validation_zone(lon,.5,zones))
        self.assertIsNone(validation_zone(None,.5,zones))
        self.assertIsNone(validation_zone(float('nan'),.5,zones))
    def test_ambiguous_boundary_and_holes_are_excluded(self):
        zones=[('A1',box(0,0,1,1)),('E1',box(1,0,2,1))]
        self.assertIsNone(validation_zone(1,.5,zones))
        polygon=Polygon([(0,0),(3,0),(3,3),(0,3)],holes=[[(1,1),(2,1),(2,2),(1,2)]])
        self.assertIsNone(validation_zone(1.5,1.5,[('A1',polygon)]))

if __name__=='__main__':unittest.main()

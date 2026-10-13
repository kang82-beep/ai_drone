import tempfile
import unittest
import pandas as pd
from pv_inspector.association import Tracks, associate_modules


class AssociationTests(unittest.TestCase):
    def test_transitive_same_frame_conflict(self):
        t=Tracks(['a','b','c','a'])
        self.assertTrue(t.join(0,1))
        self.assertTrue(t.join(1,2))
        self.assertFalse(t.join(2,3))
        self.assertNotEqual(t.root(0),t.root(3))

    def test_missing_gps_preserves_observations(self):
        df=pd.DataFrame([dict(image_id='a',mod_lat=None,mod_lon=None),dict(image_id='b',mod_lat=None,mod_lon=None)])
        with tempfile.TemporaryDirectory() as d:
            full,reps=associate_modules(df,{'a':'missing','b':'missing'},d)
        self.assertEqual(len(full),2)
        self.assertEqual(len(reps),2)
        self.assertTrue((full.association_status=='unlinked').all())

    def test_bad_image_becomes_review(self):
        df=pd.DataFrame([dict(image_id='a',mod_lat=37,mod_lon=127),dict(image_id='b',mod_lat=37,mod_lon=127)])
        with tempfile.TemporaryDirectory() as d:
            full,reps=associate_modules(df,{'a':'missing','b':'missing'},d)
        self.assertEqual(len(reps),2)
        self.assertTrue(full.rgb_review_needed.all())

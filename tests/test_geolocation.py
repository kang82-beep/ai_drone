import unittest
import tempfile
from pathlib import Path
from pv_inspector.geolocation import project_pixel, read_mrk, match_mrk, read_dji_pose


class GeoTests(unittest.TestCase):
    def project(self, u=320, v=256, yaw=0, pitch=-90, roll=0):
        return project_pixel(u,v,640,512,37,127,dict(GimbalYawDegree=yaw,GimbalPitchDegree=pitch,GimbalRollDegree=roll),30)

    def test_nadir_center(self):
        lat,lon,status=self.project()
        self.assertAlmostEqual(lat,37)
        self.assertAlmostEqual(lon,127)
        self.assertEqual(status,'approximate_flat_plane')

    def test_cardinal_directions(self):
        self.assertGreater(self.project(v=100)[0],37)
        self.assertGreater(self.project(u=500)[1],127)
        self.assertGreater(self.project(v=100,yaw=90)[1],127)
        self.assertLess(self.project(u=500,yaw=90)[0],37)

    def test_roll_180_equivalence_at_nadir(self):
        a=self.project(u=450,v=130,yaw=-90,roll=180)
        b=self.project(u=450,v=130,yaw=90,roll=0)
        self.assertAlmostEqual(a[0],b[0])
        self.assertAlmostEqual(a[1],b[1])

    def test_oblique_center(self):
        self.assertGreater(self.project(pitch=-45)[0],37)

    def test_horizon_and_missing_attitude(self):
        self.assertIsNone(self.project(pitch=0)[0])
        self.assertEqual(project_pixel(1,1,640,512,37,127,{},30)[2],'missing_gimbal_attitude')

    def test_xmp_and_mrk(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'DJI_20260731000000_0001_T.JPG'
            p.write_bytes(b'drone-dji:GimbalYawDegree="-90.2" drone-dji:RelativeAltitude="nan"')
            self.assertEqual(read_dji_pose(p),{'GimbalYawDegree':-90.2})
            mrk=Path(d)/'DJI_20260731000000_D.MRK'
            mrk.write_text('1\t432883.9\t[2429]\t20,N\t144,E\t113,V\t34.7,Lat\t126.1,Lon\t55.1,Ellh\t50,Q\n')
            records=read_mrk(mrk)
            self.assertEqual(match_mrk(p,records)['lat'],34.7)
            self.assertIsNone(match_mrk(Path(d)/'DJI_20260801000000_0001_T.JPG',records))


if __name__=='__main__':
    unittest.main()

import math
import unittest
from collections import Counter
from pv_inspector.site_model import load_site
from pv_inspector.site_structures import buildings,building_parts,raised_modules,supports,module_frames


class StructureTests(unittest.TestCase):
    def test_depth_renderer_occlusion_is_independent_of_object_order(self):
        import numpy as np
        from pv_inspector.mesh_render import rasterize
        from pv_inspector.site_structures import box
        near=box('near',-1,-1,2,2,2,.1,'roof')
        far=box('far',-.5,-.5,0,1,1,.1,'inverter')
        im,pick=rasterize([near,far],64,64,0,math.pi/2,20,0,0)
        other,_=rasterize([far,near],64,64,0,math.pi/2,20,0,0)
        self.assertTrue(np.array_equal(np.asarray(im),np.asarray(other)))
        self.assertEqual(int(pick[32,32]),0)

    def test_equipment_schedule_and_building_elevations(self):
        bs=buildings(load_site())
        for b,inv,tr,vcb in [(bs[0],10,3,4),(bs[1],15,3,4)]:
            parts=building_parts(b)
            self.assertEqual(sum(p['kind']=='inverter' for p in parts),inv)
            self.assertEqual(sum('-TR-' in p['id'] and p['kind']=='equipment' for p in parts),tr)
            self.assertEqual(sum('-VCB-' in p['id'] and p['kind']=='equipment' for p in parts),vcb)
            roofs=[v[2] for p in parts if '-ROOF-' in p['id'] and '-PHOTO-' not in p['id'] for v in p['vertices']]
            self.assertAlmostEqual(min(roofs),4.5)
            self.assertAlmostEqual(max(roofs),6.12)
            for p in parts:
                if p['kind'] not in ('inverter','equipment'):continue
                for x,y,z in p['vertices']:
                    dx,dy=(b['depth'],b['length']) if b['rotated'] else (b['length'],b['depth'])
                    self.assertTrue(b['x']<=x<=b['x']+dx and b['y']<=y<=b['y']+dy)
                    self.assertLess(z,4.5)

    def test_solids_and_foundation_contact(self):
        r=load_site()['rows'][0];mm=raised_modules(r);ss=supports(r)
        parts=mm+list(module_frames(mm))+ss
        self.assertEqual(len({p['id'] for p in parts}),len(parts))
        self.assertAlmostEqual(min(v[2] for p in mm for v in p['vertices'][:4]),.9)
        for p in parts:
            self.assertTrue(all(math.isfinite(c) for v in p['vertices'] for c in v))
            for face in p['faces']:self.assertTrue(all(0<=i<len(p['vertices']) for i in face))
        feet=[p for p in ss if p['kind']=='foundation' and '-PHOTO-' not in p['id']]
        self.assertEqual(len(feet),r['groups']*10)
        for p in feet:
            self.assertAlmostEqual(min(v[2] for v in p['vertices']),-.6)
            self.assertAlmostEqual(max(v[2] for v in p['vertices']),.2)

    def test_buildings_do_not_overlap_modules(self):
        data=load_site()
        for b in buildings(data):
            w,d=(b['depth'],b['length']) if b['rotated'] else (b['length'],b['depth'])
            for r in data['rows']:
                ox=min(b['x']+w,r['x']+r['width'])-max(b['x'],r['x'])
                oy=min(b['y']+d,r['y']+3.1061)-max(b['y'],r['y'])
                self.assertFalse(ox>0 and oy>0,(b['id'],r['id']))

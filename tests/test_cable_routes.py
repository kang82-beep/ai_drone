import math
import unittest
from pv_inspector.site_model import load_site
from pv_inspector.site_structures import buildings
from pv_inspector.cable_routes import all_routes,indoor_routes,route_parts


class CableRouteTests(unittest.TestCase):
    def test_drawing_heights_and_indoor_schedule(self):
        bs=buildings(load_site())
        for b in bs:
            rr=indoor_routes(b)
            overhead=[r for r in rr if r['elevation_basis']=='FL+2600']
            self.assertEqual(len(overhead),2 if b['id']=='ER-01' else 3)
            for r in rr:
                z=.25 if r['elevation_basis']=='FL-250' else 3.1
                for x,y,zz in r['points']:
                    self.assertAlmostEqual(zz,z)
                    w,d=(b['depth'],b['length']) if b['rotated'] else (b['length'],b['depth'])
                    self.assertTrue(b['x']<=x<=b['x']+w)
                    self.assertTrue(b['y']<=y<=b['y']+d)
            self.assertTrue(all(r['width_m']==.5 for r in overhead))

    def test_route_geometry_provenance_and_mesh_ids(self):
        rr=all_routes(load_site());self.assertEqual(len(rr),len({r['id'] for r in rr}))
        ids=set()
        for r in rr:
            self.assertTrue(r['source'].startswith('PDF p.'))
            self.assertTrue(r['note']);self.assertTrue(r['position_status'])
            for a,b in zip(r['points'],r['points'][1:]):self.assertGreater(math.dist(a,b),1e-6)
            for p in route_parts(r):
                self.assertNotIn(p['id'],ids);ids.add(p['id'])
                self.assertEqual(p['route_id'],r['id'])
                self.assertTrue(all(math.isfinite(c) for v in p['vertices'] for c in v))
                for face in p['faces']:self.assertTrue(all(0<=i<len(p['vertices']) for i in face))

    def test_conduits_connect_tray_endpoints_and_have_drawing_cover(self):
        rr=all_routes(load_site())
        ends=[p for r in rr if r['containment']=='tray' for p in [r['points'][0],r['points'][-1]]]
        for r in rr:
            if r['containment']!='conduit':continue
            self.assertIn(r['points'][0],ends);self.assertIn(r['points'][-1],ends)
            outer=max(r['outer_diameters_m'])
            self.assertAlmostEqual(min(p[2] for p in r['points'])+outer/2,-1.2)
            self.assertIn('inferred',r['position_status'])

    def test_cover_removal_keeps_tray_and_representative_cables(self):
        r=all_routes(load_site())[0]
        closed=route_parts(r);opened=route_parts(r,covers=False)
        self.assertTrue(any(p['kind']=='tray_cover' for p in closed))
        self.assertFalse(any(p['kind']=='tray_cover' for p in opened))
        self.assertEqual({p['id'] for p in opened},{p['id'] for p in closed if p['kind']!='tray_cover'})
        self.assertTrue(any(p['kind'].startswith('cable_') for p in opened))

import unittest
from pv_inspector.site_model import load_site,strip_modules,strip_outline


class SiteModelTests(unittest.TestCase):
    def test_counts_bounds_ids(self):
        d=load_site();rows=d['rows']
        self.assertEqual(len(rows),156)
        self.assertEqual(sum(r['columns']*2 for r in rows),d['module_count'])
        ids=set()
        for r in rows:
            modules=strip_modules(r)
            self.assertEqual(len(modules),r['columns']*2)
            for m in modules:
                self.assertNotIn(m['id'],ids);ids.add(m['id'])
                self.assertTrue(all(-.001<=p[0]<=344.321 for p in m['vertices']))
            xs=[p[0] for m in modules for p in m['vertices']]
            self.assertAlmostEqual(max(xs)-min(xs),r['width'])

    def test_no_overlapping_strips(self):
        rows=load_site()['rows']
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                x_overlap=min(a['x']+a['width'],b['x']+b['width'])-max(a['x'],b['x'])
                y_overlap=min(a['y']+3.1061,b['y']+3.1061)-max(a['y'],b['y'])
                self.assertFalse(x_overlap>.001 and y_overlap>.001,(a['id'],b['id']))

    def test_north_high_edge(self):
        r=load_site()['rows'][0];p=strip_outline(r)
        self.assertLess(p[3][1],p[0][1])
        self.assertGreater(p[3][2],p[0][2])


if __name__=='__main__':unittest.main()

import unittest
from pv_inspector.site_model import load_site
from pv_inspector.site_landscape import road_rectangles,landscape_parts


class LandscapeTests(unittest.TestCase):
    def test_roads_clear_all_module_envelopes(self):
        for key,x,y,w,d in road_rectangles():
            for r in load_site()['rows']:
                ox=min(x+w,r['x']+r['width'])-max(x,r['x'])
                oy=min(y+d,r['y']+3.107)-max(y,r['y'])
                self.assertFalse(ox>0 and oy>0,(key,r['id']))

    def test_pavement_has_no_coplanar_overlap(self):
        rects=[]
        for p in landscape_parts():
            if p['kind']!='concrete_road':continue
            xs,ys,_=zip(*p['vertices']);rects.append((min(xs),min(ys),max(xs),max(ys)))
        for i,(a,b,c,d) in enumerate(rects):
            for e,f,g,h in rects[i+1:]:
                self.assertFalse(min(c,g)-max(a,e)>1e-8 and min(d,h)-max(b,f)>1e-8)

import math
import unittest
import numpy as np
from pv_inspector.two_row_structure import assess_two_rows, filter_two_row_candidates


def module(x,y,name,angle=0,w=10,h=16):
    p=np.array([[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]])
    a=math.radians(angle);r=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    return {'id':str(name),'polygon':((p+[x,y])@r.T+[100,100]).tolist()}


class StructureTests(unittest.TestCase):
    def array(self,angle=0,rows=2):return [module(i*11,j*17,f'{j}-{i}',angle) for j in range(rows) for i in range(10)]

    def test_rotated_two_row_array_is_supported(self):
        for angle in (0,35,90,145):
            results=assess_two_rows(self.array(angle))
            self.assertTrue(all(r['status']=='supported' for r in results),angle)

    def test_isolated_and_wrong_size_candidates_are_separated(self):
        items=self.array()+[module(250,200,'noise'),module(300,200,'large',w=30,h=45)]
        results=assess_two_rows(items)
        self.assertTrue(all(r['status']=='supported' for r in results[:20]))
        self.assertEqual(results[-2]['status'],'low');self.assertEqual(results[-1]['status'],'low')

    def test_missing_mate_is_review_not_false_module(self):
        items=[m for m in self.array() if m['id']!='1-4']
        results={m['id']:r for m,r in zip(items,assess_two_rows(items))}
        self.assertEqual(results['0-4']['status'],'review')
        self.assertIn('missing_mate',results['0-4']['reasons'])
        self.assertEqual(results['0-5']['status'],'supported')

    def test_three_rows_cannot_be_treated_as_valid_two_rows(self):
        results=assess_two_rows(self.array(rows=3))
        self.assertFalse(any(r['status']=='supported' for r in results))
        self.assertTrue(all('more_than_two_rows' in r['reasons'] for r in results))

    def test_single_row_and_border_noise_remain_review(self):
        items=self.array(rows=1)+[module(-98,-95,'edge')]
        results=assess_two_rows(items,(500,500))
        self.assertTrue(all(r['status']=='review' for r in results))

    def test_invalid_geometry_does_not_crash(self):
        items=self.array()+[{'id':'bad','polygon':[[float('nan'),1],[2,3],[4,5]]}]
        self.assertEqual(assess_two_rows(items)[-1]['status'],'low')

    def test_filter_rejects_external_noise_but_keeps_array(self):
        for angle in (0, 35, 90, 145):
            items=self.array(angle)+[module(250,200,'noise',angle)]
            kept, decisions=filter_two_row_candidates(items)
            self.assertEqual(kept,list(range(20)))
            self.assertEqual(decisions[-1]['filter_reason'],'outside_two_row_array')

    def test_filter_preserves_missing_mates_edges_and_different_orientation(self):
        items=[m for m in self.array() if m['id']!='1-4']
        items += [module(-98,-95,'edge'),module(300,200,'rotated',45)]
        kept,_=filter_two_row_candidates(items,(700,700))
        self.assertEqual(kept,list(range(len(items))))

    def test_filter_requires_supported_structure(self):
        for items in (self.array(rows=1),self.array(rows=3),[module(0,0,'a')]):
            kept,_=filter_two_row_candidates(items)
            self.assertEqual(kept,list(range(len(items))))

    def test_filter_preserves_size_outlier_inside_array(self):
        items=self.array()+[module(40,8,'large',w=30,h=45)]
        kept,_=filter_two_row_candidates(items)
        self.assertIn(20,kept)

    def test_merged_modules_in_separate_array_are_not_noise(self):
        items=self.array()+[module(i*11,150,f'merged-{i}',w=10,h=34) for i in range(8)]
        kept,_=filter_two_row_candidates(items)
        self.assertEqual(kept,list(range(len(items))))


if __name__=='__main__':unittest.main()

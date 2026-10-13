import unittest
from collections import Counter
from pv_inspector.site_model import load_site
from pv_inspector.circuit_model import build_network,field_parts


class CircuitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_site();cls.net=build_network(cls.data)

    def test_exact_coverage_and_drawing_counts(self):
        ownership=Counter();totals=Counter()
        boxes=[n for n in self.net['nodes'] if n['type']=='junction_box']
        self.assertEqual(len(boxes),60)
        expected={'A':[16,16,16,20,16,16,20,16,16,16,20,16],
                  'B':[16,16,20,16,16,20,16,16,20,20,13,16],
                  'C':[20,16,16]*4,'D':[20,16,16]*4,
                  'E':[20,16,16,20,16,16,16,16,16,12,16,16]}
        for g in 'ABCDE':self.assertEqual([n['parallel_strings'] for n in boxes if n['group']==g],expected[g])
        for n in boxes:
            totals[n['group']]+=n['module_count']
            for s in n['spans']:
                for row in range(2):
                    for col in range(s['column_start'],s['column_end']):ownership[s['strip'],row,col]+=1
        required={(r['id'],i,c) for r in self.data['rows'] for i in range(2) for c in range(r['columns'])}
        self.assertEqual(set(ownership),required);self.assertEqual(set(ownership.values()),{1})
        self.assertEqual(totals,dict(A=4080,B=4100,C=4160,D=4160,E=3920))

    def test_generation_reaches_grid_without_auxiliary_paths(self):
        nodes={n['id']:n for n in self.net['nodes']};nexts={}
        for e in self.net['edges']:
            self.assertIn(e['from'],nodes);self.assertIn(e['to'],nodes)
            if e['type'] in ('pv_dc','dc_input','ac_generation'):
                self.assertNotIn(e['from'],nexts)
                nexts[e['from']]=e['to']
        for key in nodes:
            if not key.startswith('JB-'):continue
            visited=set();at=key
            while at!='GRID':
                self.assertNotIn(at,visited);visited.add(at);at=nexts[at]
            self.assertFalse(any('MCCB' in n or '-PT-' in n or n.startswith('P-') for n in visited))
        self.assertEqual(nexts['JB-D31'],'ER-02-INV-D1')
        self.assertEqual(nexts['JB-D11'],'ER-02-INV-D2')
        self.assertEqual(nexts['JB-D21'],'ER-02-INV-D3')

    def test_field_solids_unique_and_finite(self):
        import math
        parts=field_parts(self.net)
        self.assertEqual(len(parts),len({p['id'] for p in parts}))
        for p in parts:
            self.assertTrue(all(math.isfinite(c) for v in p['vertices'] for c in v))
            self.assertTrue(all(0<=i<len(p['vertices']) for f in p['faces'] for i in f))

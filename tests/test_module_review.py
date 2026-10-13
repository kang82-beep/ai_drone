import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
from pv_inspector.module_review import (ReviewSession, atomic_json, digest, fit_landmarks,
                                       inside_hull, pairing_lookup, project)
from pv_inspector.files import parse_tv_and_key5

PAIRS=[[[10,10],[10,10]],[[80,10],[80,10]],[[80,80],[80,80]],
       [[10,80],[10,80]],[[45,15],[45,15]],[[15,45],[15,45]],[[75,45],[75,45]],[[45,75],[45,75]]]


class GeometryTests(unittest.TestCase):
    def test_holdout_fit_and_composition(self):
        pairs=copy.deepcopy(PAIRS)
        for a,b in pairs:b[:]=[a[0]*1.2+4,a[1]*.8+7]
        fit=fit_landmarks(pairs,1)
        np.testing.assert_allclose(project([[30,40]],fit['matrix']),[[40,39]],atol=1e-5)
        self.assertLess(fit['loo_max_px'],1e-4)

    def test_wrong_pair_collinear_duplicates_and_four_points_rejected(self):
        wrong=copy.deepcopy(PAIRS);wrong[0][1]=[50,70]
        for pairs in (wrong, PAIRS[:4], [PAIRS[0]]*6,
                      [[[i,i],[i,i]] for i in range(6)]):
            with self.assertRaises(ValueError):fit_landmarks(pairs,2)

    def test_extrapolation_not_supported(self):
        self.assertTrue(inside_hull([[30,30]],np.array(PAIRS)[:,0]))
        self.assertFalse(inside_hull([[90,90]],np.array(PAIRS)[:,0]))

    def test_pairing_accepts_one_second_offset_but_not_ambiguous_rgb(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            for f in ('DJI_20260731092004_0312_V.JPG','DJI_20260731092005_0312_V.JPG',
                      'DJI_20260732092004_0312_V.JPG'):(root/f).touch()
            lookup=pairing_lookup(root)
            key=parse_tv_and_key5(str(root/'DJI_20260731092005_0312_T.JPG'))[2]
            self.assertEqual(len(lookup[key]),2)


class ReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.out=self.root/'review';self.out.mkdir()
        self.raw=self.root/'raw.bin';raw=np.full((100,100),40,dtype=np.float32);raw[30:35,30:35]=70;raw.tofile(self.raw)
        self.case={'key':'M1','module_uid':'M1','image_id':'capture_T','final':'abnormal','thermal_size':[100,100],
                   'rgb':'present','raw':str(self.raw),'bbox':[20,20,40,40],
                   'position':[3,3,3],'tile_to_local':[[.1,0,0],[0,.1,0],[0,0,1]],
                   'rgb_alignment':fit_landmarks(PAIRS,1)}
        self.registration={'matrix_3x2':[[1,0],[0,1],[0,0]],
                           'orthomosaic':{'transform':[.1,0,0,0,-.1,10,0,0,1],'crs':'EPSG:4326'}}
        self.modules=[{'id':'DRAW-1','polygon':[[2,2,1],[4,2,1],[4,4,1],[2,4,1]]},
                      {'id':'DRAW-2','polygon':[[6,2,1],[8,2,1],[8,4,1],[6,4,1]]}]
        atomic_json(self.out/'manifest.json',{'dataset_id':'test','source_hashes':{},'asset_hashes':{},
                    'registration':self.registration,'cases':[self.case],'modules':self.modules})
        atomic_json(self.root/'model/zones shinan2 .geojson',{'features':[{'properties':{'zone_id':'A1'},
                    'geometry':{'type':'Polygon','coordinates':[[[0,0],[10,0],[10,10],[0,10],[0,0]]]}}]})
        atomic_json(self.root/'results/blender_site/thermal_review_registered_a.json',
                    {'records':[self.case], 'highlight_modules':[{'id':'DRAW-1','records':[0],'polygon':self.modules[0]['polygon'],'severity':'abnormal'}],
                     'notes':[]})
        self.session=ReviewSession(self.out,self.root)
        self.evidence=self.session.evidence('M1');self.evidence['thermal_rgb_pairs']=copy.deepcopy(PAIRS)
        self.evidence['thermal_polygon']=[[20,20],[40,20],[40,40],[20,40]]

    def tearDown(self):self.tmp.cleanup()

    def test_visual_link_raw_temperature_and_export(self):
        proposal=self.session.propose('M1',self.evidence)
        self.assertEqual(proposal['module_id'],'DRAW-1')
        self.assertEqual(proposal['temperature']['max_temp'],70)
        self.assertEqual(proposal['temperature']['temperature_status'],'ok')
        self.session.save('M1',self.evidence,'confirmed','Tester','Matched corners and checked row order')
        path=self.session.export();data=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(data['records'][0]['confirmed_module_id'],'DRAW-1')
        self.assertEqual(data['highlight_modules'][0]['review_status'],'confirmed')
        self.assertEqual(len(data['module_history']),1)
        self.assertEqual(data['records'][0]['gps_registered_position'],[3,3,3])

    def test_confirmation_requires_human_evidence_and_region(self):
        with self.assertRaises(ValueError):self.session.save('M1',self.evidence,'confirmed','','')
        self.evidence['thermal_polygon']=[]
        with self.assertRaises(ValueError):self.session.save('M1',self.evidence,'confirmed','Tester','Check')

    def test_changed_corners_revoke_confirmation_and_stale_windows_cannot_overwrite(self):
        other=ReviewSession(self.out,self.root)
        self.session.save('M1',self.evidence,'confirmed','Tester','Check')
        self.session.save('M1',self.evidence,'pending')
        self.assertNotIn('proposal',self.session.state['cases']['M1'])
        with self.assertRaises(ValueError):other.save('M1',self.evidence)
        self.assertEqual(len(self.session.state['audit']),2)
        reopened=ReviewSession(self.out,self.root);self.assertEqual(reopened.state['revision'],2)

    def test_pending_and_rejected_links_do_not_export_red_surfaces(self):
        pending=json.loads(self.session.export().read_text(encoding='utf-8'))
        self.assertEqual(pending['highlight_modules'][0]['review_status'],'pending')
        self.session.save('M1',self.evidence,'rejected',note='Wrong identity')
        rejected=json.loads(self.session.export().read_text(encoding='utf-8'))
        self.assertEqual(rejected['highlight_modules'],[])
        self.assertEqual(rejected['records'][0]['final'],'abnormal')

    def test_outside_a_or_support_is_not_confirmable(self):
        self.evidence['thermal_polygon']=[[85,85],[95,85],[95,95],[85,95]]
        with self.assertRaises(ValueError):self.session.propose('M1',self.evidence)

    def test_cannot_replace_anomaly_with_another_thermal_module(self):
        self.evidence['thermal_polygon']=[[50,20],[70,20],[70,40],[50,40]]
        with self.assertRaisesRegex(ValueError,'검출 중심'):
            self.session.propose('M1',self.evidence)
        self.evidence['thermal_polygon']=[[20,20],[40,20],[40,40],[20,40]]
        p=self.root/'model/zones shinan2 .geojson';zones=json.loads(p.read_text());zones['features'][0]['properties']['zone_id']='E1';atomic_json(p,zones)
        with self.assertRaises(ValueError):self.session.propose('M1',self.evidence)

    def test_modified_evidence_file_refuses_reload(self):
        manifest=json.loads((self.out/'manifest.json').read_text())
        manifest['asset_hashes']={str(self.raw):digest(self.raw)};atomic_json(self.out/'manifest.json',manifest)
        self.raw.write_bytes(b'changed')
        with self.assertRaises(ValueError):ReviewSession(self.out,self.root)


if __name__=='__main__':unittest.main()

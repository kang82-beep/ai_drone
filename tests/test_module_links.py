import unittest
import tempfile
import json
from pathlib import Path
from pv_inspector.module_links import assemble, digest, validate_blender_export


class ModuleLinkTests(unittest.TestCase):
    def test_stale_blender_or_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);scene=root/'scene.blend';scene.write_bytes(b'scene')
            index=root/'index.json';index.write_text(json.dumps({'fingerprints':{}}))
            sidecar=scene.with_suffix('.links.json')
            sidecar.write_text(json.dumps({'blend_sha256':digest(scene),'index_sha256':digest(index),'index_path':'index.json'}))
            self.assertEqual(validate_blender_export(scene,root),{'fingerprints':{}})
            index.write_text('{}')
            with self.assertRaises(ValueError):validate_blender_export(scene,root)
            scene.write_bytes(b'edited')
            with self.assertRaises(ValueError):validate_blender_export(scene,root)

    def module(self):
        return {'id':'DRAW-1','vertices':[(0,0,0),(1,0,0),(1,1,0),(0,1,0)]}

    def record(self):
        return dict(module_uid='M1',image_id='image1',module_id=1,final='abnormal',drawing_candidate_id='DRAW-1')

    def test_candidate_never_becomes_confirmation(self):
        r=dict(self.record(),review_status='confirmed',confirmed_module_id='DRAW-1')
        data=assemble([r],[self.module()],'dataset')
        self.assertEqual(data['records'][0]['link_status'],'historical_candidate')
        self.assertEqual(data['modules']['DRAW-1']['records'],[0])

    def test_rejected_link_does_not_become_normal_or_reappear(self):
        data=assemble([self.record()],[self.module()],'dataset',rejected=['M1'])
        self.assertEqual(data['records'][0]['final'],'abnormal')
        self.assertEqual(data['records'][0]['link_status'],'rejected')
        self.assertEqual(data['modules']['DRAW-1']['records'],[])

    def test_unknown_id_is_not_snapped(self):
        data=assemble([dict(self.record(),drawing_candidate_id='unknown')],[self.module()],'dataset')
        self.assertEqual(data['records'][0]['link_status'],'unmatched')

    def test_dataset_identity_and_multiple_observations(self):
        records=[self.record(),dict(self.record(),image_id='image2',module_uid='M2')]
        data=assemble(records,[self.module()],'dataset')
        self.assertEqual(data['modules']['DRAW-1']['records'],[0,1])
        self.assertNotEqual(data['records'][0]['observation_id'],data['records'][1]['observation_id'])
        with self.assertRaises(ValueError):assemble([self.record(),self.record()],[self.module()],'dataset')

    def test_verified_confirmation_uses_reviewed_target(self):
        data=assemble([dict(self.record(),drawing_candidate_id='wrong')],[self.module()],'dataset',{'M1':'DRAW-1'})
        self.assertEqual(data['records'][0]['link_status'],'confirmed')
        self.assertEqual(data['records'][0]['drawing_module_id'],'DRAW-1')

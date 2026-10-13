import json
from pathlib import Path
import tempfile
import unittest

from pv_inspector.orthoview import load_module_layers
from run_array_refinement import globalize


class ArrayViewTests(unittest.TestCase):
    def test_stale_refined_catalog_is_not_displayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.tif';source.write_bytes(b'original')
            folder=root/'results/module_arrays_site';folder.mkdir(parents=True)
            stat=source.stat()
            payload=dict(source=str(source),source_size=stat.st_size,source_mtime_ns=stat.st_mtime_ns,
                         modules=[],slots=[dict(id='a',status='unconfirmed',expected_polygon=[[0,0],[2,0],[2,2],[0,2]])])
            (folder/'modules.json').write_text(json.dumps(payload),encoding='utf-8')
            layers=load_module_layers(source,root)
            self.assertEqual(len(layers['배열 기반 검토']['review']),1)
            self.assertEqual(layers['배열 기반 검토']['modules'],[])
            source.write_bytes(b'changed source')
            self.assertEqual(load_module_layers(source,root),{})

    def test_tile_center_ownership_and_pixel_offsets(self):
        module=dict(id='a',array_id='a',center=[10,10],polygon=[[5,5],[15,5],[15,15],[5,15]],source_ids=['s'])
        result=dict(modules=[module],unresolved=[],slots=[])
        modules,_,_=globalize(result,100,200,'T1-',(100,200,110,220))
        self.assertEqual(modules,[])  # right edge belongs to the next core
        modules,_,_=globalize(result,100,200,'T2-',(110,200,120,220))
        self.assertEqual(modules[0]['center'],[110,210])
        self.assertEqual(modules[0]['polygon'][0],[105,205])
        self.assertEqual(modules[0]['id'],'T2-a')


if __name__=='__main__':unittest.main()

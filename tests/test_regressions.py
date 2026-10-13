import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from pv_inspector import config
from pv_inspector.files import parse_tv_and_key5
from pv_inspector.metadata import _dms_to_dd, _extract_heading_candidates, _heading_from_exif
from pv_inspector.thermal import _compute_temp_stats_in_bbox, extract_temp_and_color_dji
from pv_inspector.dedup import dedup_modules_by_location, save_dedup_geojson
from pv_inspector.catalog import load_module_catalog_json, snap_point_to_catalog


class RegressionTests(unittest.TestCase):
    def test_single_image_row_coordinates_are_finite(self):
        from pv_inspector.geometry import compute_rows_from_gps
        result = compute_rows_from_gps({'one': (34., 126.), 'invalid': (float('nan'), 126.)})
        self.assertEqual(result, {'one': {'row_id': 1, 'xprime': 0., 'yprime': 0.}})

    def test_capture_pairing(self):
        key = lambda p: parse_tv_and_key5(p)[2]
        self.assertEqual(key('DJI_20260101_0001_T.JPG'), key('DJI_20260101_0001_V.JPG'))
        self.assertNotEqual(key('DJI_20260101_0001_T.JPG'), key('DJI_20260102_0001_V.JPG'))

    def test_gps_values(self):
        self.assertEqual(_dms_to_dd((37., 30., 0.), b'S'), -37.5)
        self.assertEqual(_dms_to_dd(((37, 1), (30, 1), (0, 1)), 'N'), 37.5)

    def test_tv_timestamps_can_differ(self):
        key = lambda p: parse_tv_and_key5(p)[2]
        self.assertEqual(key('DJI_20260731093246_1004_T.JPG'), key('DJI_20260731093245_1004_V.JPG'))
        self.assertNotEqual(key('DJI_20260731093246_1004_T.JPG'), key('DJI_20260801093245_1004_V.JPG'))

    def test_no_heading_from_latitude(self):
        self.assertEqual(_extract_heading_candidates('lat=37.5 lon=127.1'), [])
        self.assertEqual(_extract_heading_candidates('Yaw=90'), [90])

    def test_heading_tag(self):
        with patch('pv_inspector.metadata.Image.open') as opened:
            opened.return_value._getexif.return_value = {34853: {16: 'T', 17: 90.0}}
            self.assertEqual(_heading_from_exif('dummy.jpg'), 90)

    def test_temperature_edges_nonfinite(self):
        raw = np.array([[1, np.inf], [np.nan, 5]], dtype=np.float32)
        self.assertEqual(_compute_temp_stats_in_bbox(raw, (0, 0, 2, 2)), (3, 5, 2))

    def test_noise_not_merged(self):
        df = pd.DataFrame([dict(crop_path=str(i), mod_lat=37+i*.001, mod_lon=127, final='normal') for i in range(3)])
        _, dedup = dedup_modules_by_location(df, .8, 2)
        self.assertEqual(len(dedup), 3)
        self.assertEqual(dedup.cluster_id.nunique(), 3)

    def test_dedup_severity_export(self):
        df = pd.DataFrame([dict(crop_path=label, mod_lat=37., mod_lon=127., final=label) for label in ('normal', 'abnormal')])
        _, dedup = dedup_modules_by_location(df, .8, 1)
        self.assertEqual(dedup.iloc[0]['final'], 'abnormal')
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'modules.json'
            save_dedup_geojson(dedup, str(out))
            self.assertEqual(json.loads(out.read_text())['features'][0]['properties']['cluster_id'], 0)

    def test_catalog_radius(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'catalog.json'
            p.write_text(json.dumps([{'id':'panel1','lat':37,'lon':127}]))
            catalog = load_module_catalog_json(str(p))
            self.assertEqual(snap_point_to_catalog(37,127,catalog,1.2)[1]['mid'], 'panel1')
            self.assertEqual(snap_point_to_catalog(38,127,catalog,1.2), (None,None))

    def test_sdk_timeout(self):
        with tempfile.TemporaryDirectory() as d, patch('pv_inspector.thermal.subprocess.run') as run:
            raw = Path(d) / 'a.raw'
            raw.write_bytes(b'1234')
            self.assertTrue(extract_temp_and_color_dji('a.jpg', str(raw), '', 'sdk.exe', max_wait=2))
            self.assertEqual(run.call_args.kwargs['timeout'], 2)

    def test_output_paths(self):
        saved = {k:v for k,v in vars(config).items() if k.isupper()}
        try:
            config.configure(output_root='new_results')
            self.assertEqual(Path(config.MASTER_CSV), Path('new_results/master_results.csv'))
        finally:
            vars(config).update(saved)

    def test_example_config_accepts_boolean_settings(self):
        saved = {k:v for k,v in vars(config).items() if k.isupper()}
        try:
            config.configure(Path(__file__).parents[1] / 'config.example.json')
            self.assertFalse(config.SNAP_ENABLE)
        finally:
            vars(config).update(saved)

    def test_split_modules_have_no_unresolved_globals(self):
        import builtins
        import symtable
        for path in (Path(__file__).parents[1] / 'pv_inspector').glob('*.py'):
            table = symtable.symtable(path.read_text(encoding='utf-8'), str(path), 'exec')
            declared = set(table.get_identifiers()) | set(dir(builtins)) | {'__file__', '__name__', '__package__', '__spec__', '__loader__', '__cached__', '__builtins__'}
            stack = list(table.get_children())
            while stack:
                scope = stack.pop()
                stack.extend(scope.get_children())
                for symbol in scope.get_symbols():
                    if symbol.is_referenced() and symbol.is_global() and not symbol.is_local():
                        self.assertIn(symbol.get_name(), declared, f'{path}: {scope.get_name()}')


if __name__ == '__main__':
    unittest.main()

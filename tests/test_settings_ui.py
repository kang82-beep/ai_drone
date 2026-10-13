import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pv_inspector.settings_ui import prepare_settings, read_settings, save_settings


class SettingsTests(unittest.TestCase):
    def edits(self, folder):
        folder = Path(folder)
        model = folder / '모델.pth'
        model.touch()
        exe = folder / 'dji_irp.exe'
        exe.touch()
        return dict(INPUT_IMG_DIR=str(folder), OUTPUT_ROOT=str(folder / '새 결과'),
                    MASKRCNN_WEIGHTS=str(model), CLF_WEIGHTS=str(model), DJI_IRP_EXE=str(exe))

    def test_roundtrip_preserves_other_settings_and_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            values = prepare_settings({'BATCH_SIZE': 16, 'TH_ABNORMAL': .62}, self.edits(folder))
            path = Path(folder) / '설정.json'
            save_settings(path, values)
            self.assertEqual(read_settings(path), values)
            self.assertEqual(values['TH_ABNORMAL'], .62)
            self.assertFalse(Path(values['OUTPUT_ROOT']).exists())

    def test_missing_model_and_enabled_optional_input_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            edits = self.edits(folder)
            with self.assertRaises(ValueError):
                prepare_settings({}, dict(edits, MASKRCNN_WEIGHTS=''))
            with self.assertRaises(ValueError):
                prepare_settings({}, dict(edits, SNAP_ENABLE=True))
            with self.assertRaises(ValueError):
                prepare_settings({}, dict(edits, CLF_WEIGHTS=str(Path(folder) / 'missing.pth')))

    def test_failed_write_keeps_original_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            save_settings(path, {'BATCH_SIZE': 16})
            with patch('pv_inspector.settings_ui.os.replace', side_effect=OSError('denied')):
                with self.assertRaises(OSError):
                    save_settings(path, {'BATCH_SIZE': 32})
            self.assertEqual(read_settings(path), {'BATCH_SIZE': 16})
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_json_must_be_object(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.json'
            path.write_text('[]')
            with self.assertRaises(ValueError):
                read_settings(path)

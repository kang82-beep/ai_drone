import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
from PIL import Image
from pv_inspector import config
from pv_inspector.classification import classify_and_sort


class ClassificationAuditTests(unittest.TestCase):
    def classify(self, folder, logits, delta=0, hotspot=False):
        path = Path(folder) / 'crop.jpg'
        Image.new('RGB', (16, 16)).save(path)
        clf = lambda x: torch.tensor([logits], dtype=torch.float32).repeat(len(x), 1)
        tf = lambda image: torch.zeros(3, 16, 16)
        with patch.multiple(config, USE_TTA=False, USE_HIERARCHICAL_DECISION=False,
                            DELTA_ATT_ENABLE=True, DELTA_ATT_TH=5):
            return classify_and_sort(clf, ['normal', 'attention', 'abnormal'], [str(path)],
                str(Path(folder) / 'sorted'), tf, tf, 'cpu',
                delta_lookup={str(path): delta}, hotspot_lookup={str(path): hotspot})

    def test_temperature_override_keeps_model_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            row = self.classify(folder, [5, 0, 0], 8, True).iloc[0]
            self.assertEqual(row['model_decision'], 'normal')
            self.assertEqual(row['final'], 'attention')
            self.assertEqual(row['decision_reason'], 'argmax;delta_temperature;hotspot')

    def test_neighbor_delta_raises_normal_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'crop.jpg'
            Image.new('RGB', (16, 16)).save(path)
            clf = lambda x: torch.tensor([[5., 0, 0]]).repeat(len(x), 1)
            tf = lambda image: torch.zeros(3, 16, 16)
            with patch.multiple(config, USE_TTA=False, USE_HIERARCHICAL_DECISION=False):
                row = classify_and_sort(clf, ['normal', 'attention', 'abnormal'], [str(path)],
                    str(Path(folder) / 'sorted'), tf, tf, 'cpu', neighbor_lookup={str(path): True}).iloc[0]
            self.assertEqual((row['model_decision'], row['final']), ('normal', 'attention'))
            self.assertEqual(row['decision_reason'], 'argmax;neighbor_delta')

    def test_invalid_logits_are_not_saved_as_normal(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'invalid probabilities'):
                self.classify(folder, [float('nan'), 0, 0])
            self.assertEqual(list((Path(folder) / 'sorted').rglob('*.jpg')), [])

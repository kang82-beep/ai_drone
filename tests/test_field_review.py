import csv
import tempfile
import unittest
from pathlib import Path

from pv_inspector.field_review import review_record, write_field_review


class FieldReviewTests(unittest.TestCase):
    def normal(self):
        return dict(final='normal', temperature_status='ok', mean_temp=40, max_temp=41,
                    delta_temp=1, prob_normal=.9, prob_attention=.08, prob_abnormal=.02,
                    mod_lat=34, mod_lon=126)

    def test_normal_requires_valid_temperature(self):
        row = self.normal()
        self.assertFalse(review_record(row)['review_required'])
        for value in (None, float('nan'), float('inf')):
            self.assertTrue(review_record(dict(row, max_temp=value))['review_required'])
        row.pop('temperature_status')
        self.assertIn('온도 품질 미확인', review_record(row)['review_reason'])

    def test_bad_scores_and_uncertainty(self):
        row = self.normal()
        for value in (None, float('nan'), -1, 2):
            self.assertIn('분류 점수 미확인', review_record(dict(row, prob_normal=value))['review_reason'])
        self.assertIn('분류 경계', review_record(dict(row, prob_normal=.5, prob_attention=.48))['review_reason'])
        self.assertEqual(review_record(dict(row, final='abnormal'))['review_priority'], 1)

    def test_output_escaping_missing_images_and_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            row = dict(self.normal(), image_id='<script>alert(1)</script>', module_id='=1+1')
            path = write_field_review([row], folder)
            content = path.read_text(encoding='utf-8')
            self.assertIn('&lt;script&gt;', content)
            self.assertNotIn('<script>alert(1)</script>', content)
            self.assertIn('크롭 파일 없음', content)
            with (Path(folder) / 'field_review_template.csv').open(encoding='utf-8-sig') as stream:
                saved = next(csv.DictReader(stream))
            self.assertEqual(saved['module_id'], "'=1+1")
            self.assertIn('검출 관측이 없습니다', write_field_review([], folder).read_text(encoding='utf-8'))

    def test_real_image_links(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / '모듈 #1.jpg'
            image.write_bytes(b'placeholder')
            path = write_field_review([dict(self.normal(), crop_path=image.name)], folder, folder)
            self.assertIn(image.as_uri(), path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

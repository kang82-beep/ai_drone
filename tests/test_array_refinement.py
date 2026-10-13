import unittest
import cv2
import numpy as np

from pv_inspector.array_refinement import refine_arrays


def scene(rows=2, columns=7):
    rgb = np.full((340, 430, 3), 50, np.uint8)
    candidates = []
    for row in range(rows):
        for col in range(columns):
            x, y = 45+col*45, 45+row*70
            poly = [[x,y],[x+40,y],[x+40,y+64],[x,y+64]]
            cv2.rectangle(rgb,(x-2,y-2),(x+42,y+66),(230,230,230),-1)
            cv2.rectangle(rgb,(x,y),(x+40,y+64),(25,55,120),-1)
            candidates.append(dict(id=f'{row}-{col}',polygon=poly,score=.9))
    return rgb,candidates


class ArrayRefinementTests(unittest.TestCase):
    def test_two_rows_have_unique_cells_and_four_boundaries(self):
        image, candidates=scene()
        result=refine_arrays(image,candidates)
        self.assertEqual(result['summary']['arrays'],1)
        self.assertEqual(len(result['modules']),14)
        self.assertEqual(len({m['id'] for m in result['modules']}),14)
        self.assertTrue(all(min(s['evidence']['edge_scores'])>=.3 for s in result['slots']))

    def test_merged_detection_split_and_duplicate_removed(self):
        image,candidates=scene()
        candidates=[c for c in candidates if c['id'] not in ('0-2','0-3')]
        candidates += [dict(id='merged',polygon=[[135,45],[220,45],[220,109],[135,109]],score=.8)]
        candidates += [{**candidates[0],'id':'duplicate','score':.7}]
        result=refine_arrays(image,candidates)
        self.assertEqual(len(result['modules']),14)
        self.assertEqual(result['summary']['duplicates'],1)
        self.assertEqual(result['summary']['split_sources'],1)
        self.assertEqual(sum(m['origin']=='merged_split' for m in result['modules']),2)

    def test_missing_detection_recovered_only_with_real_surface(self):
        image,candidates=scene()
        candidates=[c for c in candidates if c['id']!='1-3']
        result=refine_arrays(image,candidates)
        self.assertEqual(result['summary']['recovered_cells'],1)
        self.assertEqual(len(result['modules']),14)
        image[112:183,177:224]=50  # physically remove the module, not just its detection
        result=refine_arrays(image,candidates)
        self.assertEqual(result['summary']['recovered_cells'],0)
        self.assertLess(len(result['modules']),14)
        self.assertGreater(result['summary']['unconfirmed_slots'],0)

    def test_single_and_three_rows_not_forced_into_two(self):
        for rows in (1,3):
            image,candidates=scene(rows)
            result=refine_arrays(image,candidates)
            self.assertEqual(result['summary']['arrays'],0)
            self.assertEqual(len(result['unresolved']),len(candidates))

    def test_rotation_preserves_array_identity(self):
        image,candidates=scene()
        matrix=cv2.getRotationMatrix2D((215,170),25,1)
        rotated=cv2.warpAffine(image,matrix,(430,340))
        for c in candidates:
            c['polygon']=cv2.transform(np.float32([c['polygon']]),matrix)[0].tolist()
        result=refine_arrays(rotated,candidates)
        self.assertEqual(result['summary']['arrays'],1)
        self.assertGreaterEqual(len(result['modules']),12)

    def test_no_seeds_no_invented_modules_and_invalid_input_preserved(self):
        image=np.zeros((200,200,3),np.uint8)
        result=refine_arrays(image,[dict(id='bad',polygon=[[1,1],[1,1],[1,1]])])
        self.assertEqual(result['modules'],[])
        self.assertEqual(len(result['unresolved']),1)

    def test_duplicate_ids_rejected(self):
        image,candidates=scene()
        with self.assertRaises(ValueError):refine_arrays(image,candidates+[candidates[0]])

    def test_large_background_box_is_not_counted_as_a_merged_module(self):
        image,candidates=scene()
        candidates.append(dict(id='background',polygon=[[5,5],[410,5],[410,310],[5,310]],score=.5))
        result=refine_arrays(image,candidates)
        self.assertEqual(result['summary']['split_sources'],0)
        self.assertTrue(all('background' not in m['source_ids'] for m in result['modules']))

    def test_strided_raster_input_has_same_results(self):
        image,candidates=scene()
        self.assertEqual(refine_arrays(image,candidates),refine_arrays(np.asfortranarray(image),candidates))


if __name__=='__main__':unittest.main()

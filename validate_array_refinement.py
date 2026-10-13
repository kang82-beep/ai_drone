"""Real-image checks; injected detection errors are explicitly not field accuracy."""
import json
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from scipy.optimize import linear_sum_assignment

from pv_inspector.array_refinement import refine_arrays
from run_array_refinement import dump, render

ROOT=Path(__file__).resolve().parent


def main():
    out=ROOT/'results'/'array_refinement'/'validation'
    out.mkdir(parents=True,exist_ok=True)
    reference=json.loads((ROOT/'results/module_split_pilot/modules.json').read_text(encoding='utf-8'))['modules']
    rgb=np.array(Image.open(ROOT/'results/module_split_pilot/original.png').convert('RGB'))
    candidates=[dict(id=m['id'],polygon=m['polygon'],score=.9) for m in reference]
    removed={'P01-R01-M03','P01-R01-M04','P01-R03-M04'}
    challenge=[c for c in candidates if c['id'] not in removed]
    merge=[c for c in candidates if c['id'] in {'P01-R01-M03','P01-R01-M04'}]
    polygon=cv2.boxPoints(cv2.minAreaRect(np.concatenate([np.float32(c['polygon']) for c in merge])))
    challenge.append(dict(id='injected-merged',polygon=polygon.tolist(),score=.8))
    challenge.append({**candidates[8],'id':'injected-duplicate','score':.7})
    result=refine_arrays(rgb,challenge)
    predicted=np.array([m['center'] for m in result['modules']]);truth=np.array([m['center'] for m in reference])
    distance=np.linalg.norm(predicted[:,None]-truth[None,:],axis=2)
    rows,cols=linear_sum_assignment(distance)
    report=dict(scope='Injected merged, duplicate, and missing detections on real pilot RGB; not independent field accuracy',
                reference_count=len(reference),input_candidates=len(challenge),summary=result['summary'],
                one_to_one_matches_within_10px=int(np.count_nonzero(distance[rows,cols]<10)),
                center_error_max_px=float(distance[rows,cols].max()))
    dump(out/'rgb_challenge.json',dict(report=report,result=result,input=challenge))
    render(rgb,result,out/'rgb_challenge.png')
    # Reuse actual detections saved by the previous diagnostic, with bbox geometry.
    # No cross-camera transform is assumed and no temperature/classifier is invoked.
    records=json.loads((ROOT/'results/two_row_filter_check/decisions.json').read_text(encoding='utf-8'))
    by_image=defaultdict(list)
    for record in records:by_image[record['image']].append(record)
    thermal=[]
    for name,records in by_image.items():
        path=ROOT/'image'/name
        with Image.open(path) as image:rgb=np.array(image.convert('RGB'))
        candidates=[]
        for record in records:
            x1,y1,x2,y2=record['bbox']
            candidates.append(dict(id=str(record['candidate']),polygon=[[x1,y1],[x2,y1],[x2,y2],[x1,y2]],score=1.))
        result=refine_arrays(rgb,candidates,mode='thermal')
        dump(out/(path.stem+'.json'),result);render(rgb,result,out/(path.stem+'.jpg'))
        thermal.append(dict(image=name,**result['summary']))
    dump(out/'summary.json',dict(rgb_challenge=report,thermal_bbox_replay=thermal))
    print(json.dumps(dict(rgb_challenge=report,thermal_bbox_replay=thermal),ensure_ascii=False,indent=2))


if __name__=='__main__':main()

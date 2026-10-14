"""Compare module verdicts: detector boxes vs the two-row grid cells (cell_fit).

Three runs over the same linked observations:
  A. current      detector-mask temperatures and classifier output, edge views excluded
  B. fit voting   A, plus boxes that sit off their grid cell do not vote
  C. re-measured  B, with temperature, neighbour delta and classifier re-run on the grid cell
Writes results/cell_measurement/{observations.csv, verdicts.csv, summary.json}.
"""
from pathlib import Path
import argparse, json
import cv2
import numpy as np
import pandas as pd
import torch
from PIL import Image
from pv_inspector import config
from pv_inspector.cell_fit import fit, cell_mask, cell_crop
from pv_inspector.models import build_effb3, make_transforms
from pv_inspector.module_verdict import judge
from pv_inspector.neighbor_delta import add_neighbor_delta
from pv_inspector.thermal import measure_module_raw

ROOT = Path(__file__).resolve().parent


def local(path):
    text = str(path).replace('/', '\\')
    index = text.lower().find('\\results\\')
    return ROOT / text[index + 1:] if index >= 0 else Path(text)


def load_classifier(weights):
    ckpt = torch.load(weights, map_location='cpu')
    model = build_effb3(num_classes=3)
    model.load_state_dict(ckpt['model_state'])
    model.eval()
    tf, tf_flip = make_transforms(int(ckpt.get('img_size', 300)), bool(ckpt.get('use_grayscale', False)))
    return model, ckpt['class_order'], tf, tf_flip


def classify(model, order, tf, tf_flip, images, batch=16):
    out = []
    with torch.no_grad():
        for i in range(0, len(images), batch):
            chunk = images[i:i + batch]
            probs = torch.softmax(model(torch.stack([tf(im) for im in chunk])), 1)
            if config.USE_TTA:
                probs = (probs + torch.softmax(model(torch.stack([tf_flip(im) for im in chunk])), 1)) / 2
            out.extend(probs.numpy())
    return [{name: float(p[order.index(name)]) for name in order} for p in out]


def decide(prob, delta_temp, hotspot, neighbor_flag):
    """Same rule as pv_inspector.classification.classify_and_sort."""
    if prob['abnormal'] >= config.TH_ABNORMAL:
        return 'abnormal'
    within = prob['attention'] / max(prob['attention'] + prob['normal'], 1e-8)
    final = 'attention' if within >= config.TH_ATT_WITHIN else 'normal'
    if final == 'normal' and ((delta_temp or 0) >= config.DELTA_ATT_TH or hotspot or neighbor_flag):
        final = 'attention'
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linked', default='tmp/partial/reg/master_linked.csv')
    parser.add_argument('--catalog', default='shinan3_viewer/assets/module_catalog.csv')
    parser.add_argument('--weights', default='model/classifier_b3_2025_1013.pth')
    parser.add_argument('--output', default='results/cell_measurement')
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    linked = pd.read_csv(ROOT / args.linked, encoding='utf-8-sig', low_memory=False)
    catalog = pd.read_csv(ROOT / args.catalog, encoding='utf-8-sig')
    model, order, tf, tf_flip = load_classifier(ROOT / args.weights)

    records, crops = [], []
    for image_id, frame in linked.groupby('image_id', sort=True):
        first = frame.iloc[0]
        review = local(first['array_review_path'])
        cells = {}
        if isinstance(first['array_review_path'], str) and review.is_file():
            cells = {m['id']: m['polygon'] for m in json.loads(review.read_text(encoding='utf-8'))['modules']
                     if m.get('status') == 'image_supported'}
        raw_path = local(first['temp_raw'])
        raw = np.fromfile(str(raw_path), np.float32).reshape(512, 640) if raw_path.is_file() else None
        image = cv2.cvtColor(cv2.imdecode(np.fromfile(str(local(first['det_base'])), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        rows = []
        for row in frame.to_dict('records'):
            ids = json.loads(row['array_proposed_cells']) if isinstance(row['array_proposed_cells'], str) else []
            polygon = cells.get(ids[0]) if ids else None
            box = (row['bbox_x1'], row['bbox_y1'], row['bbox_x2'], row['bbox_y2'])
            label, iou = fit(box, polygon, list(cells.values()), row['structure_status'], row['link_status'] != 'unmatched')
            record = dict(row, cell_fit=label, cell_iou=iou, remeasured=False)
            if polygon is not None and raw is not None:
                measured = measure_module_raw(raw, cell_mask(polygon))
                if measured['temperature_status'] == 'ok':
                    centre = np.asarray(polygon, float).mean(0)
                    record.update(mean_temp=measured['mean_temp'], max_temp=measured['max_temp'], delta_temp=measured['delta_temp'],
                                  hs_is_hotspot=measured['hs_is_hotspot'], centroid_u=centre[0], centroid_v=centre[1], remeasured=True)
                    crop = cell_crop(image, polygon)
                else:
                    crop = image[int(box[1]):int(box[3]), int(box[0]):int(box[2])]
            else:
                crop = image[int(box[1]):int(box[3]), int(box[0]):int(box[2])]
            crops.append(Image.fromarray(np.ascontiguousarray(crop)))
            rows.append(record)
        add_neighbor_delta(rows, threshold=config.NEIGHBOR_DELTA_ATT_TH)
        records.extend(rows)
        print(f'{image_id} cells={len(cells)} observations={len(rows)}', flush=True)

    probs = classify(model, order, tf, tf_flip, crops)
    for record, prob in zip(records, probs):
        record.update(prob_abnormal_cell=prob['abnormal'], prob_attention_cell=prob['attention'], prob_normal_cell=prob['normal'])
        record['final_cell'] = decide(prob, record['delta_temp'], record['hs_is_hotspot'], record['neighbor_flag'])
    obs = pd.DataFrame(records)
    keep = ['image_id', 'module_id', 'drawing_module_id', 'cell_fit', 'cell_iou', 'remeasured', 'final', 'final_cell',
            'prob_abnormal', 'prob_abnormal_cell', 'mean_temp', 'max_temp', 'delta_temp', 'neighbor_delta_mean', 'hs_is_hotspot']
    obs[keep].to_csv(output / 'observations.csv', index=False, encoding='utf-8-sig')

    a, _ = judge(linked, catalog)
    b, _ = judge(linked.assign(cell_fit=obs['cell_fit'].values), catalog)
    re_measured = linked.copy()
    for column in ('mean_temp', 'max_temp', 'delta_temp', 'centroid_u', 'centroid_v'):
        re_measured[column] = obs[column].values
    re_measured['final'] = obs['final_cell'].values
    re_measured['prob_abnormal'] = obs['prob_abnormal_cell'].values
    re_measured['cell_fit'] = obs['cell_fit'].values
    c, _ = judge(re_measured, catalog)
    verdicts = a[['drawing_module_id', 'verdict', 'verdict_reason']].rename(columns={'verdict': 'A_current', 'verdict_reason': 'A_reason'}) \
        .merge(b[['drawing_module_id', 'verdict', 'verdict_reason']].rename(columns={'verdict': 'B_fit_voting', 'verdict_reason': 'B_reason'}), on='drawing_module_id') \
        .merge(c[['drawing_module_id', 'verdict', 'verdict_reason']].rename(columns={'verdict': 'C_remeasured', 'verdict_reason': 'C_reason'}), on='drawing_module_id')
    verdicts.to_csv(output / 'verdicts.csv', index=False, encoding='utf-8-sig')
    summary = {
        'observations': len(obs), 'cell_fit': obs.cell_fit.value_counts().to_dict(),
        'flag_rate_by_fit': obs.groupby('cell_fit').final.apply(lambda s: round(float((s != 'normal').mean()), 3)).to_dict(),
        'observation_flags': {'detector_box': int((obs.final != 'normal').sum()), 'grid_cell': int((obs.final_cell != 'normal').sum())},
        'verdicts': {name: verdicts[name].value_counts().to_dict() for name in ('A_current', 'B_fit_voting', 'C_remeasured')},
        'A_to_C': pd.crosstab(verdicts.A_current, verdicts.C_remeasured).to_dict(),
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

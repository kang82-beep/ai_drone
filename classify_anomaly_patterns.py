"""Label anomaly shapes, shading and viewing-angle cautions for flagged observations.

Reads a linked or merged master table, classifies every observation of each flagged
module (so central and peripheral views of the same module can be compared), and
writes anomaly_patterns.csv plus a contact sheet of canonical patches for review.
"""
from pathlib import Path
import argparse, json
import cv2
import numpy as np
import pandas as pd
from pv_inspector import anomaly_patterns as ap

ROOT = Path(__file__).resolve().parent


def local(path):
    text = str(path).replace('/', '\\')
    index = text.lower().find('\\results\\')
    return ROOT / text[index + 1:] if index >= 0 else Path(text)


def refined_outline(row, cache):
    """Rotated module outline from the array refinement of this frame, if the cell was image-supported."""
    path = local(row['array_review_path']) if isinstance(row.get('array_review_path'), str) else None
    cells = json.loads(row['array_proposed_cells']) if isinstance(row.get('array_proposed_cells'), str) else []
    if not cells or path is None or not path.is_file():
        return None
    if path not in cache:
        modules = json.loads(path.read_text(encoding='utf-8'))['modules']
        cache.clear()
        cache[path] = {m['id']: m['polygon'] for m in modules if m.get('status') == 'image_supported'}
    return cache[path].get(cells[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master', default='results/shinan3_full_20261030/reg/master_linked.csv')
    parser.add_argument('--module-column', default='drawing_module_id')
    parser.add_argument('--alignment', default='results/ir_rgb_alignment/alignment.json')
    parser.add_argument('--no-rgb', action='store_true')
    parser.add_argument('--output', default='results/anomaly_patterns')
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(ROOT / args.master, encoding='utf-8-sig', low_memory=False)
    flagged_modules = set(master.loc[master['final'] != 'normal', args.module_column].dropna())
    rows = master[master[args.module_column].isin(flagged_modules)]
    transform = None
    if not args.no_rgb and (ROOT / args.alignment).is_file():
        transform = np.array(json.loads((ROOT / args.alignment).read_text(encoding='utf-8'))['fixed_thermal_to_rgb'])
    raws, rgbs, outlines, out, sheet = {}, {}, {}, [], []
    for row in rows.to_dict('records'):
        raw_path = local(row['temp_raw'])
        if raw_path not in raws:
            raws = {raw_path: ap.load_raw(raw_path) if raw_path.is_file() else None}  # frames arrive in order; keep one
        raw = raws[raw_path]
        bbox = [row['bbox_x1'], row['bbox_y1'], row['bbox_x2'], row['bbox_y2']]
        edge_r = ap.radius(row['centroid_u'], row['centroid_v'], row['img_w'], row['img_h'])
        record = {'image_id': row['image_id'], 'module_id': row['module_id'], 'module': row[args.module_column],
                  'final': row['final'], 'radius': round(edge_r, 3), 'edge': edge_r > ap.EDGE_RADIUS}
        outline = refined_outline(row, outlines)
        if raw is None:
            patch = None
        elif outline:
            patch = ap.polygon_patch(raw, outline, row['gimbal_yaw'])
            record['outline'] = 'refined'
        else:
            patch, box, snapped = ap.module_patch(raw, bbox, row['gimbal_yaw'], row['gsd_x_m_per_px'])
            outline = [[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]]]
            record['outline'] = 'snapped_box' if snapped else 'detector_box'
            if not snapped:  # a loose axis-aligned box mixes neighbouring modules into the patch
                patch = None
        if patch is None:
            record['type'] = 'unreadable'
            out.append(record)
            continue
        kind, features = ap.classify(patch, row.get('neighbor_delta_mean'), row.get('neighbor_ref_temp'))
        shading = None
        if transform is not None:
            rgb_path = local(row['rgb_path'])
            if rgb_path.is_file():
                if rgb_path not in rgbs:
                    rgbs = {rgb_path: cv2.imdecode(np.fromfile(str(rgb_path), np.uint8), cv2.IMREAD_COLOR)}
                points = np.c_[np.array(outline, float), np.ones(4)] @ transform.T
                gray = cv2.cvtColor(rgbs[rgb_path], cv2.COLOR_BGR2GRAY)
                rgb_patch = ap.polygon_patch(gray, points, row['gimbal_yaw'], scale=1, trim=False)
                hot = (patch - features['base_c']) >= features['threshold_c']
                shading = ap.rgb_shading(rgb_patch, hot) if rgb_patch is not None else None
        record.update(type=kind, type_label=ap.TYPES[kind], features=json.dumps(features),
                      rgb_dark_fraction=round(shading[0], 3) if shading else None,
                      hot_on_rgb_dark=round(shading[1], 3) if shading else None,
                      shadow_suspect=ap.shadow_suspected(kind, shading),
                      cautions=' | '.join(ap.caution(kind, record['edge'], shading)))
        out.append(record)
        if row['final'] != 'normal':
            sheet.append((patch - features['base_c'], f"{kind} r{edge_r:.2f}", row['final']))
    table = pd.DataFrame(out)
    table.to_csv(output / 'anomaly_patterns.csv', index=False, encoding='utf-8-sig')

    # Contact sheet: each canonical patch (south edge on the right), colour range fixed at -2..+6 °C.
    tiles = []
    for patch, label, final in sheet[:96]:
        image = cv2.applyColorMap(np.clip((patch + 2) / 8 * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        image = cv2.resize(image, (200, 120), interpolation=cv2.INTER_NEAREST)
        image = cv2.copyMakeBorder(image, 18, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(image, label, (3, 13), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 200) if final == 'abnormal' else (0, 0, 0), 1)
        tiles.append(cv2.copyMakeBorder(image, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    if tiles:
        while len(tiles) % 8:
            tiles.append(np.full_like(tiles[0], 255))
        cv2.imwrite(str(output / 'patterns_sheet.jpg'), np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, len(tiles), 8)]))
    flagged = table[table['final'] != 'normal']
    print(json.dumps({'observations': len(table), 'flagged': len(flagged),
                      'types_flagged': flagged['type'].value_counts().to_dict(),
                      'flagged_on_edge': int(flagged['edge'].sum()),
                      'flagged_shadow_suspect': int((flagged['shadow_suspect'] == True).sum()),
                      'flagged_hot_on_dark>=0.5': int((flagged['hot_on_rgb_dark'] >= .5).sum()) if 'hot_on_rgb_dark' in flagged else None},
                     ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

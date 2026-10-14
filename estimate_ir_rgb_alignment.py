"""Estimate the fixed thermal→visible image transform of the M4T (과제_기획서 3.2, step 1).

Both cameras sit on one gimbal, so at the 30 m survey height one affine transform
should map thermal pixels onto the wide-camera image. For a sample of captures this
script finds the transform per frame (multi-scale edge template match, then ECC
affine refinement on edge maps), takes the median as the fixed transform, and
re-scores every sampled frame under that fixed transform. Writes
results/ir_rgb_alignment/alignment.json and blended check images.
"""
from pathlib import Path
import argparse, json, re
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
RGB_SCALE = 0.25  # work on 1008x756 visible images


def edges(gray):
    gray = cv2.GaussianBlur(gray, (0, 0), 1.5)
    magnitude = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    magnitude = cv2.GaussianBlur(magnitude, (0, 0), 2)
    return (magnitude - magnitude.mean()) / (magnitude.std() + 1e-6)


def load(thermal_path, rgb_path):
    thermal = cv2.imdecode(np.fromfile(str(thermal_path), np.uint8), cv2.IMREAD_GRAYSCALE)
    rgb = cv2.imdecode(np.fromfile(str(rgb_path), np.uint8), cv2.IMREAD_COLOR)
    rgb = cv2.resize(rgb, None, fx=RGB_SCALE, fy=RGB_SCALE, interpolation=cv2.INTER_AREA)
    return thermal, rgb


def score(thermal_edges, rgb_edges, warp):
    """Normalised correlation of edge maps inside the warped thermal footprint."""
    h, w = rgb_edges.shape
    moved = cv2.warpAffine(thermal_edges, warp, (w, h), flags=cv2.INTER_LINEAR)
    mask = cv2.warpAffine(np.ones_like(thermal_edges), warp, (w, h)) > .5
    if mask.sum() < 1000:
        return -1.0
    a, b = moved[mask], rgb_edges[mask]
    return float(np.corrcoef(a, b)[0, 1])


def estimate(thermal_edges, rgb_edges):
    best = (-2, None)
    for scale in np.arange(.30, .80, .01):
        template = cv2.resize(thermal_edges, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if template.shape[0] >= rgb_edges.shape[0] or template.shape[1] >= rgb_edges.shape[1]:
            continue
        result = cv2.matchTemplate(rgb_edges, template, cv2.TM_CCOEFF_NORMED)
        _, value, _, (x, y) = cv2.minMaxLoc(result)
        if value > best[0]:
            best = (value, np.float32([[scale, 0, x], [0, scale, y]]))
    coarse = best[1]
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6)
    try:
        # ECC finds W with input(W(x)) ≈ template(x): thermal is the template, so W maps thermal→visible.
        _, warp = cv2.findTransformECC(thermal_edges, rgb_edges, coarse.copy(), cv2.MOTION_AFFINE, criteria, None, 5)
    except cv2.error:
        return coarse, 'coarse'
    # A refinement that wanders far from the template match has locked onto repeated panel rows.
    if abs(np.hypot(*warp[:, 0]) / coarse[0, 0] - 1) > .05 or np.hypot(*(warp[:, 2] - coarse[:, 2])) > 20:
        return coarse, 'coarse'
    return warp, 'ecc'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', default=r'C:\drone 3')
    parser.add_argument('--samples', type=int, default=40)
    parser.add_argument('--output', default='results/ir_rgb_alignment')
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    pairs = {}
    for path in Path(args.images).iterdir():
        match = re.fullmatch(r'DJI_\d{14}_(\d+)_([TV])\.JPE?G', path.name, re.IGNORECASE)
        if match:
            pairs.setdefault(int(match[1]), {})[match[2].upper()] = path
    keys = sorted(k for k, v in pairs.items() if len(v) == 2)
    sample = [keys[i] for i in np.linspace(0, len(keys) - 1, args.samples).round().astype(int)]

    frames, data = [], {}
    for key in sample:
        thermal, rgb = load(pairs[key]['T'], pairs[key]['V'])
        te, re_ = edges(thermal.astype(np.float32)), edges(cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY).astype(np.float32))
        warp, method = estimate(te, re_)
        data[key] = (te, re_, thermal, rgb)
        frames.append({'capture': key, 'thermal': pairs[key]['T'].name, 'warp': warp.tolist(), 'method': method, 'own_score': score(te, re_, warp)})
        print(f"{key:4d} scale={np.hypot(*warp[:, 0]):.4f} tx={warp[0, 2]:.1f} ty={warp[1, 2]:.1f} score={frames[-1]['own_score']:.3f} {method}", flush=True)

    # Frames whose own fit is weak (bare ground, buildings) do not vote for the fixed transform.
    good = [f for f in frames if f['own_score'] >= .3]
    # The rig is rigid, so the true offset is shared; fits shifted by a panel-row period are aliases.
    centre = np.median(np.array([f['warp'] for f in good])[:, :, 2], axis=0)
    good = [f for f in good if np.hypot(*(np.array(f['warp'])[:, 2] - centre)) <= 15]
    for f in frames:
        f['votes'] = f in good
    fixed = np.median(np.array([f['warp'] for f in good]), axis=0).astype(np.float32)
    for frame in frames:
        te, re_, _, _ = data[frame['capture']]
        frame['fixed_score'] = score(te, re_, fixed)
        offset = np.array(frame['warp'])[:, 2] - fixed[:, 2]
        frame['offset_from_fixed_px'] = round(float(np.hypot(*offset)) / RGB_SCALE, 1)
    full = fixed.copy()
    full[:, :] /= RGB_SCALE  # express in full-resolution visible pixels
    result = {
        'thermal_size': [1280, 1024], 'rgb_size': [4032, 3024],
        'fixed_thermal_to_rgb': full.tolist(),
        'scale_rgb_px_per_thermal_px': round(float(np.hypot(*full[:, 0])), 4),
        'frames_sampled': len(frames), 'frames_voting': len(good),
        'fixed_score_median': round(float(np.median([f['fixed_score'] for f in frames])), 3),
        'offset_from_fixed_px_median': float(np.median([f['offset_from_fixed_px'] for f in good])),
        'offset_from_fixed_px_p90': float(np.percentile([f['offset_from_fixed_px'] for f in good], 90)),
        'frames_aliased_to_neighbour_row': sum(f['own_score'] >= .3 and not f['votes'] for f in frames),
        'frames': frames,
        'note': 'Edge-map correlation of the warped thermal footprint; offsets are in full-resolution visible pixels.',
    }
    (output / 'alignment.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for frame in sorted(frames, key=lambda f: f['fixed_score'])[::max(1, len(frames) // 4)][:5]:
        te, re_, thermal, rgb = data[frame['capture']]
        h, w = rgb.shape[:2]
        colour = cv2.applyColorMap(thermal, cv2.COLORMAP_INFERNO)
        moved = cv2.warpAffine(colour, fixed, (w, h))
        mask = cv2.warpAffine(np.full(thermal.shape, 255, np.uint8), fixed, (w, h)) > 0
        blend = rgb.copy()
        blend[mask] = (.5 * rgb[mask] + .5 * moved[mask]).astype(np.uint8)
        # Checkerboard view makes edge continuity across the two images easy to judge.
        tiles = ((np.indices((h, w)) // 48).sum(0) % 2).astype(bool) & mask
        checker = rgb.copy()
        checker[tiles] = moved[tiles]
        cv2.imwrite(str(output / f"check_{frame['capture']:04d}.jpg"), np.hstack([blend, checker]))
    print(json.dumps({k: v for k, v in result.items() if k != 'frames'}, indent=2))


if __name__ == '__main__':
    main()

"""Measure how far consecutive frames moved, from the images themselves.

GPS puts each frame within a few tenths of a metre, but along a row the module
pattern repeats every 1.008 m, so a frame on its own cannot tell which module it
sees. Consecutive frames overlap: phase correlation of the overlap gives their
relative motion independently of GPS, which ties each frame to its neighbour.

The correlation follows the ground texture (panel rows run along the track and
carry little along-track signal), so pixels are scaled at the ground range, not the
panel range used for module positions. A tie is the difference of two frames'
position corrections: (image motion - GPS motion) in north/east metres.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .camera_calibration import EARTH_R, POSE, camera_positions
from .geolocation import camera_rotation

MAX_YAW_CHANGE_DEG = 15
MAX_GAP_S = 3
MIN_OVERLAP = 0.25


def track(master):
    """One row per frame: camera north/east metres about the flight centre, attitude, time."""
    rows = master[master.mod_lat.notna()].copy()
    cam = camera_positions(rows)
    rows['cam_lat'], rows['cam_lon'] = cam[:, 0], cam[:, 1]
    frames = rows.groupby('image_id').agg(
        cam_lat=('cam_lat', 'mean'), cam_lon=('cam_lon', 'mean'), img_w=('img_w', 'first'), img_h=('img_h', 'first'),
        camera_to_surface_m=('camera_to_surface_m', 'first'), **{p: (p, 'first') for p in POSE})
    lat0, lon0 = frames.cam_lat.mean(), frames.cam_lon.mean()
    frames['north'] = np.radians(frames.cam_lat - lat0) * EARTH_R
    frames['east'] = np.radians(frames.cam_lon - lon0) * EARTH_R * math.cos(math.radians(lat0))
    stem = frames.index.to_series()
    frames['time'] = pd.to_datetime(stem.str.extract(r'DJI_(\d{14})_')[0], format='%Y%m%d%H%M%S', errors='coerce')
    frames['seq'] = pd.to_numeric(stem.str.extract(r'DJI_\d{14}_(\d+)_')[0], errors='coerce')
    return frames.sort_values(['time', 'seq'])


def pixel_to_ground(frame, ground_m, focal_35mm=52.0):
    """2x2 (north, east) metres per (u, v) pixel at the image centre, on the ground plane."""
    focal = math.hypot(frame.img_w, frame.img_h) * focal_35mm / math.hypot(36, 24)
    rotation = camera_rotation(*(frame[p] for p in POSE))

    def ground(du, dv):
        ray = rotation @ np.array([1.0, du / focal, dv / focal])
        return ray[:2] * ground_m / ray[2]
    centre = ground(0, 0)
    return np.column_stack((ground(1, 0) - centre, ground(0, 1) - centre))


def _texture(path):
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    image = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    return image - cv2.GaussianBlur(image, (0, 0), 25)  # drop the slow temperature gradient


def measure(image_a, image_b, jacobian, gps_motion):
    """Tie for one pair, or None when the predicted overlap is too small."""
    predicted = -np.linalg.solve(jacobian, gps_motion)  # pixels the content moves from a to b
    du, dv = (int(round(v)) for v in predicted)
    height, width = image_a.shape
    x0, x1, y0, y1 = max(0, -du), min(width, width - du), max(0, -dv), min(height, height - dv)
    if (x1 - x0) * (y1 - y0) < MIN_OVERLAP * width * height:
        return None
    a = image_a[y0:y1, x0:x1]
    b = image_b[y0 + dv:y1 + dv, x0 + du:x1 + du]
    (rx, ry), response = cv2.phaseCorrelate(a, b, cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F))
    tie = -jacobian @ np.array([rx, ry])
    return dict(tie_north_m=float(tie[0]), tie_east_m=float(tie[1]), response=float(response),
                overlap=round((x1 - x0) * (y1 - y0) / (width * height), 3), residual_px=round(math.hypot(rx, ry), 1))


def compute(master, image_paths, surface_above_ground_m=0.0, progress=None):
    """Ties between consecutive frames of each flight line.

    `image_paths` maps image_id to the thermal JPG. `surface_above_ground_m` is the panel
    surface height the master was projected with, so the ground lies that much further.
    """
    frames = track(master)
    rows = []
    names = frames.index.to_list()
    cache = {}
    for k, (a, b) in enumerate(zip(names[:-1], names[1:])):
        fa, fb = frames.loc[a], frames.loc[b]
        turn = abs((fa.gimbal_yaw - fb.gimbal_yaw + 180) % 360 - 180)
        gap = (fb.time - fa.time).total_seconds() if pd.notna(fa.time) and pd.notna(fb.time) else math.inf
        if turn > MAX_YAW_CHANGE_DEG or gap > MAX_GAP_S or a not in image_paths or b not in image_paths:
            continue
        for name in (a, b):
            if name not in cache:
                cache[name] = _texture(image_paths[name])
        for name in list(cache):
            if name not in (a, b):
                del cache[name]
        if cache[a] is None or cache[b] is None or cache[a].shape != cache[b].shape:
            continue
        jacobian = pixel_to_ground(fa, fa.camera_to_surface_m + surface_above_ground_m)
        gps_motion = np.array([fb.north - fa.north, fb.east - fa.east])
        tie = measure(cache[a], cache[b], jacobian, gps_motion)
        if tie:
            rows.append(dict(source=a, target=b, gps_step_m=round(float(np.hypot(*gps_motion)), 3), **tie))
        if progress and k % 100 == 0:
            progress(k, len(names))
    return pd.DataFrame(rows, columns=['source', 'target', 'gps_step_m', 'tie_north_m', 'tie_east_m',
                                       'response', 'overlap', 'residual_px'])


def find_images(roots, pattern='*_T.JPG'):
    paths = {}
    for root in roots:
        for path in Path(root).rglob(pattern):
            paths.setdefault(path.stem, path)
    return paths

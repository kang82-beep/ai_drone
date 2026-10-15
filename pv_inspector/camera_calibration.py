"""Fit the systematic camera corrections from frames already linked to the drawing.

Every registered frame gets its own scale, rotation and shift in site_registration.
When the same scale or rotation shows up in almost every frame it is a camera-model
error (height of the panel surface, gimbal yaw bias, camera offset from the GPS
position), not a frame-by-frame one. This fits those once so per-frame registration
only has to absorb what really varies between frames (GPS and exposure-timing noise).

The fit is self-consistency against the drawing, not a survey: a whole-site shift is
left to the map alignment. A scale error is fitted as panel height above the take-off
level: frame-to-frame image motion, which follows the ground, agrees with GPS at the
nominal focal length, so the modules look larger because they are nearer the camera.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .geolocation import NEUTRAL_CAMERA, camera_model_text, camera_rotation, parse_camera_model

EARTH_R = 6378137.0
POSE = ['gimbal_yaw', 'gimbal_pitch', 'gimbal_roll']


def ground_offsets(df, camera, focal_35mm=52.0, lower_m=0.0):
    """Vectorised geolocation.ground_offset for every row: (north, east) metres, NaN off-plane.

    `lower_m` shortens the stored camera_to_surface_m (a surface higher than assumed).
    """
    c = {**NEUTRAL_CAMERA, **camera}
    width, height = df.img_w.to_numpy(float), df.img_h.to_numpy(float)
    focal = np.hypot(width, height) * focal_35mm / math.hypot(36, 24)
    x = (df.centroid_u.to_numpy(float) - width / 2) / focal
    y = (df.centroid_v.to_numpy(float) - height / 2) / focal
    rng = df.camera_to_surface_m.to_numpy(float) - lower_m
    out = np.full((len(df), 2), np.nan)
    for pose, idx in df.groupby(POSE, sort=False).indices.items():
        yaw = pose[0] + c['yaw_offset_deg']
        ray = np.column_stack((np.ones(len(idx)), x[idx], y[idx])) @ camera_rotation(yaw, pose[1], pose[2]).T
        ok = ray[:, 2] > 0.1
        t = math.radians(yaw)
        out[idx[ok], 0] = ray[ok, 0] * rng[idx[ok]] / ray[ok, 2] + c['forward_m'] * math.cos(t) - c['right_m'] * math.sin(t)
        out[idx[ok], 1] = ray[ok, 1] * rng[idx[ok]] / ray[ok, 2] + c['forward_m'] * math.sin(t) + c['right_m'] * math.cos(t)
    return out


def _models(df):
    if 'geo_camera_model' not in df:
        return pd.Series([camera_model_text(None)] * len(df), index=df.index)
    return df['geo_camera_model'].fillna(camera_model_text(None))


def camera_positions(df):
    """Camera lat/lon per row, recovered from the stored projection and the model that made it."""
    cam = np.full((len(df), 2), np.nan)
    models = _models(df).to_numpy()
    for text in pd.unique(models):
        idx = np.flatnonzero(models == text)
        part = df.iloc[idx]
        off = ground_offsets(part, parse_camera_model(text))
        lat = part.mod_lat.to_numpy(float) - np.degrees(off[:, 0] / EARTH_R)
        cam[idx, 0] = lat
        cam[idx, 1] = part.mod_lon.to_numpy(float) - np.degrees(off[:, 1] / (EARTH_R * np.cos(np.radians(lat))))
    return cam


def project(df, camera, cam=None, lower_m=0.0):
    """Module lat/lon of every row under `camera` (rows without a position stay NaN)."""
    cam = camera_positions(df) if cam is None else cam
    off = ground_offsets(df, camera, lower_m=lower_m)
    lat = cam[:, 0] + np.degrees(off[:, 0] / EARTH_R)
    lon = cam[:, 1] + np.degrees(off[:, 1] / (EARTH_R * np.cos(np.radians(cam[:, 0]))))
    return np.column_stack((lat, lon))


def reproject(master, camera, lower_m=0.0):
    """Copy of a master table re-projected with `camera` and a surface `lower_m` higher,
    without re-running detection."""
    out = master.copy()
    rows = out.mod_lat.notna() & out.mod_lon.notna() & out[['centroid_u', 'centroid_v', 'img_w', 'img_h', 'camera_to_surface_m', *POSE]].notna().all(axis=1)
    if 'geo_camera_model' not in out:
        out['geo_camera_model'] = None
    part = out[rows]
    new = project(part, camera, lower_m=lower_m)
    out.loc[rows, 'mod_lat'], out.loc[rows, 'mod_lon'] = new[:, 0], new[:, 1]
    out.loc[rows, 'camera_to_surface_m'] = part.camera_to_surface_m - lower_m
    out.loc[rows, 'geo_camera_model'] = camera_model_text(camera)
    return out


def _jacobian(transform, latlon):
    """Drawing metres per (north, east) metre at the site centre."""
    lat, lon = latlon
    base = transform(np.array([[lat, lon]]))[0]
    north = transform(np.array([[lat + math.degrees(1 / EARTH_R), lon]]))[0] - base
    east = transform(np.array([[lat, lon + math.degrees(1 / (EARTH_R * math.cos(math.radians(lat))))]]))[0] - base
    return np.column_stack((north, east))


def fit(linked, site, transform):
    """Return (camera, surface_lower_m, report) from observations linked to drawing modules.

    `linked` needs the projection columns plus drawing_module_id; `transform` maps
    lat/lon to drawing metres (site_registration.GeoTransform after refinement).
    """
    target = site.set_index('drawing_module_id').loc[linked.drawing_module_id, ['x', 'n']].to_numpy(float)
    codes, frames = pd.factorize(linked.image_id)
    counts = np.bincount(codes)[:, None]
    cam = camera_positions(linked)

    def per_frame(camera, lower=0.0):
        residual = transform(project(linked, camera, cam, lower)) - target
        mean = np.zeros((len(frames), 2))
        np.add.at(mean, codes, residual)
        return residual, mean / counts

    def shape_residual(q):
        residual, mean = per_frame(dict(yaw_offset_deg=q[1]), q[0])
        return (residual - mean[codes]).ravel()

    def stats(camera, lower=0.0):
        residual, mean = per_frame(camera, lower)
        d = np.hypot(*(residual - mean[codes]).T)
        return dict(median_m=round(float(np.median(d)), 4), rms_m=round(float(np.sqrt((d ** 2).mean())), 4),
                    p95_m=round(float(np.percentile(d, 95)), 4)), mean

    before, _ = stats(NEUTRAL_CAMERA)
    # Stage 1, shape inside a frame: per-frame shifts are free, so only scale and rotation count.
    solution = least_squares(shape_residual, [0.0, 0.0], x_scale=[0.3, 0.5], loss='soft_l1', f_scale=0.15)
    lower = float(solution.x[0])
    camera = dict(NEUTRAL_CAMERA, yaw_offset_deg=float(solution.x[1]))
    after_shape, mean = stats(camera, lower)
    # Stage 2, offset that turns with the camera: flight lines in opposite directions see it
    # with opposite sign, while GPS noise and the site alignment do not. Along-track shifts
    # wrap at the module pitch, so forward_m is weakly determined on rows along the track.
    jac_inv = np.linalg.inv(_jacobian(transform, np.nanmean(cam, axis=0)))
    shift_ne = -mean @ jac_inv.T
    yaw = np.radians(linked.groupby(codes).gimbal_yaw.first().to_numpy(float) + camera['yaw_offset_deg'])
    n = len(frames)
    design = np.zeros((2 * n, 4))
    design[:n, 0], design[n:, 1] = 1, 1
    design[:n, 2], design[:n, 3] = np.cos(yaw), -np.sin(yaw)
    design[n:, 2], design[n:, 3] = np.sin(yaw), np.cos(yaw)
    observed = np.r_[shift_ne[:, 0], shift_ne[:, 1]]
    keep = np.ones(2 * n, bool)
    for _ in range(2):  # GPS outliers should not steer the offset
        coef = np.linalg.lstsq(design[keep], observed[keep], rcond=None)[0]
        error = observed - design @ coef
        keep = np.abs(error) <= 3 * 1.4826 * np.median(np.abs(error[keep]))
    camera.update(forward_m=float(coef[2]), right_m=float(coef[3]))
    spread_before = shift_ne.std(axis=0)
    spread_after = np.column_stack((error[:n], error[n:])).std(axis=0)
    camera = {k: round(v, 4) for k, v in camera.items()}
    report = dict(
        camera=camera, surface_higher_than_assumed_m=round(lower, 3),
        camera_to_surface_median_m=round(float(np.median(linked.camera_to_surface_m - lower)), 3),
        frames=int(n), observations=int(len(linked)),
        residual_in_frame_before=before, residual_in_frame_after=after_shape,
        frame_shift_std_north_east_m=dict(before=spread_before.round(3).tolist(), after=spread_after.round(3).tolist()),
        note='도면 배열과의 자체 일관성으로 맞춘 값이며 측량 검증이 아닙니다. 크기 오차는 패널 면 높이로 해석했습니다(초점거리는 제원값 유지).')
    return camera, lower, report

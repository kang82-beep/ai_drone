"""Approximate camera-ray/flat-plane intersection, never a surveyed position.

NED attitude: Rz(yaw) Ry(pitch) Rx(roll); camera axes forward/right/down.
XMP Euler convention and camera calibration must be checked against ground control.
"""
import math
import re
from pathlib import Path
import numpy as np
from .geometry import _enu_offset_to_latlon


def read_dji_pose(path):
    with open(path, 'rb') as stream:
        data = stream.read(2 * 1024 * 1024)
    pairs = re.findall(rb'drone-dji:(\w+)="([^"]*)"', data)
    pose = {}
    for key, value in pairs:
        try:
            number = float(value)
            if math.isfinite(number):
                pose[key.decode('ascii')] = number
        except ValueError:
            pass
    return pose


def read_mrk(path):
    """Read labelled DJI exposure records. No antenna offsets applied twice.

    Sequence keys are scoped to the MRK date and containing directory.
    Duplicate sequence IDs are rejected rather than matched arbitrarily.
    """
    if not path or not Path(path).is_file():
        return {}
    match = re.match(r'DJI_(\d{8})', Path(path).name)
    if not match:
        return {}
    records = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        def tagged(tag):
            found = re.search(r'([-+\d.]+),' + tag + r'\b', line)
            return float(found[1]) if found else None
        try:
            seq = int(fields[0])
            lat, lon = tagged('Lat'), tagged('Lon')
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            key = (match[1], seq)
            if key in records:
                raise ValueError(f'Duplicate MRK exposure: {key}')
            records[key] = dict(lat=lat, lon=lon, altitude=tagged('Ellh'), quality=tagged('Q'),
                                gps_seconds=float(fields[1]), directory=str(Path(path).resolve().parent))
        except (TypeError, IndexError):
            continue
    return records


def match_mrk(image_path, records):
    p = Path(image_path)
    match = re.fullmatch(r'DJI_(\d{8})\d{6}_(\d+)_[TV]', p.stem, re.IGNORECASE)
    if not match:
        return None
    record = records.get((match[1], int(match[2])))
    if record and record['directory'] == str(p.resolve().parent):
        return record
    return None


def camera_rotation(yaw, pitch, roll):
    y, p, r = map(math.radians, (yaw, pitch, roll))
    cy, sy, cp, sp, cr, sr = math.cos(y), math.sin(y), math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]]) @ np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]]) @ np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])


NEUTRAL_CAMERA = dict(yaw_offset_deg=0.0, forward_m=0.0, right_m=0.0)


def camera_model_text(camera):
    """Compact record of the camera correction, stored with every projected observation."""
    c = {**NEUTRAL_CAMERA, **(camera or {})}
    return ';'.join(f'{k}={c[k]:g}' for k in NEUTRAL_CAMERA)


def parse_camera_model(text):
    """Inverse of camera_model_text; empty or missing means the uncorrected model."""
    camera = dict(NEUTRAL_CAMERA)
    if isinstance(text, str) and text:
        for item in text.split(';'):
            key, _, value = item.partition('=')
            if key in camera:
                camera[key] = float(value)
    return camera


def ground_offset(u, v, width, height, yaw, pitch, roll, height_m, focal_35mm=52.0, camera=None):
    """North/east metres from the camera position to where pixel (u, v) meets the flat plane.

    `camera` holds the corrections fitted by register_flight.py --calibrate: a gimbal yaw bias and
    a camera offset from the GPS position in the camera's forward/right axes. Returns
    None when the ray does not reach the plane.
    """
    c = {**NEUTRAL_CAMERA, **(camera or {})}
    focal_px = math.hypot(width,height) * focal_35mm / math.hypot(36,24)
    yaw = yaw + c['yaw_offset_deg']
    ray = camera_rotation(yaw, pitch, roll) @ np.array([1,(u-width/2)/focal_px,(v-height/2)/focal_px])
    if ray[2] <= 0.1:
        return None
    north, east, _ = ray * (height_m/ray[2])
    y = math.radians(yaw)
    north += c['forward_m'] * math.cos(y) - c['right_m'] * math.sin(y)
    east += c['forward_m'] * math.sin(y) + c['right_m'] * math.cos(y)
    return float(north), float(east)


def project_pixel(u, v, width, height, lat, lon, pose, height_m, focal_35mm=52.0, camera=None):
    """Return lat/lon plus status; unknown attitude yields no invented coordinate.

    Assumes centered principal point, square pixels, diagonal 35mm equivalence,
    no lens distortion, and horizontal surface height_m below camera.
    """
    required = ('GimbalYawDegree', 'GimbalPitchDegree', 'GimbalRollDegree')
    if any(k not in pose for k in required):
        return None, None, 'missing_gimbal_attitude'
    values = (u,v,width,height,lat,lon,height_m,focal_35mm,*(pose[k] for k in required))
    if any(x is None or not math.isfinite(x) for x in values) or min(width,height,height_m,focal_35mm) <= 0:
        return None, None, 'invalid_geometry'
    if not (-90 < lat < 90 and -180 <= lon <= 180):
        return None, None, 'invalid_position'
    offset = ground_offset(u, v, width, height, *(pose[k] for k in required), height_m, focal_35mm, camera)
    if offset is None:
        return None, None, 'ray_near_or_above_horizon'
    out_lat,out_lon = _enu_offset_to_latlon(lat,lon,offset[1],offset[0])
    return out_lat,out_lon,'approximate_flat_plane'

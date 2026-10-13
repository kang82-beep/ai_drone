"""Module temperature relative to the other modules in the same frame.

The reference is a robust plane fitted to module mean temperatures over the
image, so a lens/sky gradient is not read as a defect and a warm string does not
pull its own reference up as long as it covers less than half the frame.
Thresholds are provisional until field-verified; irradiance scaling to
1000 W/m2 is a linear approximation and is applied only to a recorded value.
"""
from __future__ import annotations
import math
import numpy as np


def _number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _reference(u, v, t, min_plane):
    """Fitted reference per module and robust spread of the unaffected modules."""
    keep = np.ones(len(t), bool)
    scale = lambda x: (x - x.mean()) / max(float(np.ptp(x)), 1.0)
    design = np.column_stack((np.ones(len(t)), scale(u), scale(v))) if len(t) >= min_plane else np.ones((len(t), 1))
    for _ in range(6):
        coef = np.linalg.lstsq(design[keep], t[keep], rcond=None)[0]
        residual = t - design @ coef
        centre = np.median(residual[keep])
        sigma = max(1.4826 * float(np.median(np.abs(residual[keep] - centre))), 0.2)
        updated = np.abs(residual - centre) <= 2.5 * sigma
        if updated.sum() < max(4, len(t) // 2) or (updated == keep).all():
            break
        keep = updated
    return design @ coef, sigma


def capture_condition(irradiance, minimum):
    irradiance = _number(irradiance)
    if irradiance is None or irradiance <= 0:
        return 'irradiance_unrecorded'
    return 'ok' if irradiance >= minimum else 'low_irradiance'


def add_neighbor_delta(rows, threshold=3.0, min_modules=4, min_plane=8, irradiance=None, min_irradiance=600.0):
    """Annotate rows in place. Missing temperatures never become a zero difference."""
    irradiance = _number(irradiance)
    if irradiance is not None and irradiance <= 0:
        irradiance = None
    condition = capture_condition(irradiance, min_irradiance)
    by_image = {}
    for row in rows:
        row.update(neighbor_ref_temp=None, neighbor_count=0, neighbor_sigma=None,
                   neighbor_delta_mean=None, neighbor_delta_max=None, neighbor_delta_norm=None,
                   neighbor_delta_status='temperature_unavailable', neighbor_flag=False,
                   irradiance_w_m2=irradiance, capture_condition=condition,
                   reading_hold=condition == 'low_irradiance')
        values = [_number(row.get(k)) for k in ('mean_temp', 'max_temp', 'centroid_u', 'centroid_v')]
        if row.get('temperature_status', 'ok') == 'ok' and all(x is not None for x in values):
            by_image.setdefault(row.get('image_id'), []).append((row, values))
    for items in by_image.values():
        if len(items) < min_modules:
            for row, _ in items:
                row['neighbor_delta_status'] = 'insufficient_modules'
            continue
        mean, peak, u, v = (np.array([x[1][i] for x in items], float) for i in range(4))
        reference, sigma = _reference(u, v, mean, min_plane)
        for (row, _), ref, m, p in zip(items, reference, mean, peak):
            delta = float(m - ref)
            norm = delta * 1000.0 / irradiance if irradiance else None
            row.update(neighbor_ref_temp=float(ref), neighbor_count=len(items) - 1, neighbor_sigma=sigma,
                       neighbor_delta_mean=delta, neighbor_delta_max=float(p - ref), neighbor_delta_norm=norm,
                       neighbor_delta_status='ok',
                       neighbor_flag=bool((delta if norm is None else norm) >= threshold))
    return rows

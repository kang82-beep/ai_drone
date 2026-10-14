"""Module-level verdict from repeated views, and a neighbour comparison wider than one frame.

Per-observation decisions (classifier + temperature gates) stay as they are. This module
decides what to do with a drawing module that was photographed several times:

* Views near the frame edge read wrong (oblique reflection), and boxes that sit across a
  module gap mix in a neighbour (cell_fit); when a module has a trusted view, such views
  do not vote.
* 점검 대상 (inspect): flagged in at least two usable views and in at least half of them,
  or one strong signal. 재확인 (recheck): flagged, but only once or in a minority of views.
  Repetition removes reflections and glints; it does not remove shadows, which stay put
  between frames seconds apart, so shading is judged separately (anomaly_patterns).
* Wide comparison: each module's temperature, taken from central views and expressed
  relative to its own frame, is compared with the modules around it on the drawing,
  whichever frames they were photographed in. Strings are compared with the other
  strings of their junction box the same way.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from .cell_fit import TRUSTED_FITS

EDGE_RADIUS = .7          # normalised distance from the frame centre; same as anomaly_patterns
MIN_VOTES = 2
STRONG_PROB_ABNORMAL = .8
STRONG_DELTA_TEMP_C = 10.0
WIDE_RADIUS_M = 6.0       # about two tables either side
WIDE_MIN_NEIGHBOURS = 8
WIDE_FLAG_C = 3.0         # same threshold as the in-frame neighbour rule
STRONG_WIDE_C = 5.0
STRING_FLAG_C = 2.0


def view_radius(frame):
    return np.hypot((frame.centroid_u - frame.img_w / 2) / (frame.img_w / 2),
                    (frame.centroid_v - frame.img_h / 2) / (frame.img_h / 2)) / np.sqrt(2)


def frame_relative_temperature(frame):
    """Module mean temperature minus the median of the central modules of the same frame.

    Removes what changes from frame to frame (time, irradiance drift, palette) while the
    central-only reference avoids the cooler-looking edge of the frame.
    """
    central = frame[frame.radius <= EDGE_RADIUS]
    reference = central.groupby('image_id').mean_temp.median()
    fallback = frame.groupby('image_id').mean_temp.median()
    return frame.mean_temp - frame.image_id.map(reference).fillna(frame.image_id.map(fallback))


def judge(linked, catalog):
    """Return (modules, strings) verdict tables.

    linked: observations with drawing_module_id/string_id/jb_id/inverter_id, final,
            prob_abnormal, delta_temp, mean_temp, centroid_u/v, img_w/h, image_id.
    catalog: module_id, east_m, north_m for every drawing module.
    """
    obs = linked[linked.drawing_module_id.notna()].copy()
    obs['radius'] = view_radius(obs)
    obs['edge'] = obs.radius > EDGE_RADIUS
    obs['flagged'] = obs.final != 'normal'
    obs['relative_temp'] = frame_relative_temperature(obs)
    # A view is trusted when it is not on the frame edge and its box sits on its grid cell
    # (cell_fit); untrusted views vote only when the module has no trusted view at all.
    trusted = ~obs.edge
    if 'cell_fit' in obs:
        trusted &= obs.cell_fit.isin(TRUSTED_FITS) | obs.cell_fit.isna()
    obs['trusted'] = trusted
    has_trusted = obs.groupby('drawing_module_id').trusted.transform('any')
    obs['votes'] = obs.trusted | ~has_trusted

    usable = obs[obs.votes]
    modules = obs.groupby('drawing_module_id').agg(
        string_id=('string_id', 'first'), jb_id=('jb_id', 'first'), inverter_id=('inverter_id', 'first'),
        observations=('image_id', 'size'), flagged_all=('flagged', 'sum')).reset_index()
    votes = usable.groupby('drawing_module_id').agg(
        usable_views=('image_id', 'size'), flagged_votes=('flagged', 'sum'),
        relative_temp=('relative_temp', 'median'), max_prob_abnormal=('prob_abnormal', 'max'),
        max_delta_temp=('delta_temp', 'max'), only_untrusted=('trusted', lambda s: not s.any())).reset_index()
    modules = modules.merge(votes, on='drawing_module_id', how='left')

    # Wide neighbour comparison on the drawing, across frames.
    xy = catalog.set_index('module_id')[['east_m', 'north_m']]
    modules = modules.join(xy, on='drawing_module_id')
    located = modules.dropna(subset=['east_m', 'relative_temp'])
    tree = cKDTree(located[['east_m', 'north_m']].to_numpy())
    temps = located.relative_temp.to_numpy()
    wide, counts = [], []
    for i, point in enumerate(located[['east_m', 'north_m']].to_numpy()):
        near = [j for j in tree.query_ball_point(point, WIDE_RADIUS_M) if j != i]
        counts.append(len(near))
        wide.append(temps[i] - np.median(temps[near]) if len(near) >= WIDE_MIN_NEIGHBOURS else np.nan)
    modules.loc[located.index, 'wide_delta'] = wide
    modules.loc[located.index, 'wide_neighbours'] = counts
    modules['wide_flag'] = modules.wide_delta >= WIDE_FLAG_C

    strong = ((modules.max_prob_abnormal >= STRONG_PROB_ABNORMAL) & (modules.flagged_votes > 0)) \
        | (modules.max_delta_temp >= STRONG_DELTA_TEMP_C) | (modules.wide_delta >= STRONG_WIDE_C)
    consistent = (modules.flagged_votes >= MIN_VOTES) & (modules.flagged_votes * 2 >= modules.usable_views)
    flagged = (modules.flagged_votes > 0) | modules.wide_flag
    modules['verdict'] = np.select([flagged & (consistent | strong), flagged], ['inspect', 'recheck'], 'normal')
    reasons = []
    for row in modules.itertuples():
        why = []
        if row.flagged_votes:
            why.append(f'{int(row.flagged_votes)}/{int(row.usable_views)}회 후보' + (' (가장자리·어긋난 관측만)' if row.only_untrusted else ''))
        if row.flagged_all > row.flagged_votes:
            why.append(f'가장자리·어긋난 관측 {int(row.flagged_all - row.flagged_votes)}회는 판정에서 제외')
        if row.wide_flag:
            why.append(f'주변 {int(row.wide_neighbours)}장 대비 +{row.wide_delta:.1f}℃')
        if row.verdict == 'inspect' and not (row.flagged_votes >= MIN_VOTES and row.flagged_votes * 2 >= row.usable_views):
            why.append('강한 신호')
        reasons.append('; '.join(why))
    modules['verdict_reason'] = reasons

    # Strings against the other strings of the same junction box.
    strings = modules.groupby(['inverter_id', 'jb_id', 'string_id']).agg(
        modules_observed=('drawing_module_id', 'size'), relative_temp=('relative_temp', 'median'),
        inspect=('verdict', lambda s: int((s == 'inspect').sum())), recheck=('verdict', lambda s: int((s == 'recheck').sum()))).reset_index()
    strings['string_delta'] = np.nan
    for _, group in strings.groupby('jb_id'):
        for index in group.index:
            others = group.drop(index)
            others = others[others.modules_observed >= 5]
            if len(others) >= 2 and strings.at[index, 'modules_observed'] >= 5:
                strings.at[index, 'string_delta'] = strings.at[index, 'relative_temp'] - others.relative_temp.median()
    strings['string_flag'] = strings.string_delta >= STRING_FLAG_C
    return modules, strings

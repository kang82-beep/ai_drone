"""Link one analysed flight to the drawing: frame ties, registration and a drawing check.

Run after run_full_site.py. Every step is automatic; nothing is adjusted per image by hand.

  python register_flight.py --analysis results/<flight>             # usual run
  python register_flight.py --analysis results/<flight> --calibrate # new camera, site or speed

--calibrate first fits the camera corrections on this flight, re-projects the
observations with them (master_calibrated.csv) and prints the settings to keep in the
config, so later flights start from them.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
from scipy.spatial import cKDTree

from audit_drawing_fit import group_offsets, never_detected, undrawn_detections
from pv_inspector import config
from pv_inspector.camera_calibration import fit, reproject
from pv_inspector.frame_ties import compute, find_images
from pv_inspector.geolocation import parse_camera_model
from pv_inspector.site_registration import GeoTransform, load_site, refine_correction, register, summarise, visual_link_agreement


def calibrate(master, site, reference, base_surface):
    work, _, _ = register(master, site, reference)
    linked = work[work.link_status.astype(str).str.startswith('module_candidate')]
    transform = GeoTransform(reference)
    xy = site[['x', 'n']].to_numpy(float)
    refine_correction(transform, [g[['mod_lat', 'mod_lon']].to_numpy(float) for _, g in linked.groupby('image_id')], cKDTree(xy), xy)
    camera, lower, report = fit(linked, site, transform)
    report['base_surface_m'] = base_surface
    return reproject(master, camera, lower), camera, lower, report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--analysis', required=True, help='run_full_site.py 출력 폴더')
    parser.add_argument('--calibrate', action='store_true', help='이 비행으로 카메라 보정값을 다시 맞춘다')
    parser.add_argument('--layout', default='shinan3_viewer/assets/layout.json')
    parser.add_argument('--cable-model', default='results/shinan3_cables/cable_model.json')
    parser.add_argument('--reference', default='results/shinan3_map_alignment/module_geolocation_candidates.json')
    args = parser.parse_args()
    analysis = Path(args.analysis)
    output = analysis / 'reg'
    output.mkdir(parents=True, exist_ok=True)
    site = load_site(args.layout, args.cable_model)
    reference = json.loads(Path(args.reference).read_text(encoding='utf-8-sig'))[::50]
    master = pd.read_csv(analysis / 'master_results.csv', encoding='utf-8-sig', low_memory=False)
    base = json.loads((analysis / 'base_config.json').read_text(encoding='utf-8-sig')) if (analysis / 'base_config.json').is_file() else {}
    surface = float(base.get('GEO_SURFACE_ABOVE_TAKEOFF_M', config.GEO_SURFACE_ABOVE_TAKEOFF_M))

    calibration = None
    if args.calibrate:
        print('카메라 보정 중...', flush=True)
        master, camera, lower, calibration = calibrate(master, site, reference, surface)
        surface += lower
        master.to_csv(analysis / 'master_calibrated.csv', index=False, encoding='utf-8-sig')

    ties_path = analysis / 'frame_ties.csv'
    print('연속 영상 사이 이동 측정 중...', flush=True)
    ties = compute(master, find_images([analysis / 'chunks']), surface)
    ties.to_csv(ties_path, index=False, encoding='utf-8-sig')

    print('도면 연결 중...', flush=True)
    work, frames, report = register(master, site, reference, ties=ties)
    links = analysis / 'association_links.csv'
    if links.is_file():
        report['visual_link_agreement'] = visual_link_agreement(work, pd.read_csv(links, encoding='utf-8-sig'))
    if calibration:
        camera = parse_camera_model(master.geo_camera_model.dropna().iloc[0])
        trend = (report.get('flight_lines') or {}).get('trend') or {}
        # The along-track offset is only measurable once lines are unwrapped, so it comes from the trend.
        calibration['config'] = dict(GEO_SURFACE_ABOVE_TAKEOFF_M=round(surface, 3),
                                     GEO_YAW_OFFSET_DEG=camera['yaw_offset_deg'],
                                     GEO_CAMERA_FORWARD_M=round(camera['forward_m'] + trend.get('along_track_m', 0.0), 3),
                                     GEO_CAMERA_RIGHT_M=camera['right_m'])
        report['camera_calibration'] = calibration
    modules, strings = summarise(work)
    work.to_csv(output / 'master_linked.csv', index=False, encoding='utf-8-sig')
    frames.to_csv(output / 'frame_registration.csv', index=False, encoding='utf-8-sig')
    modules.to_csv(output / 'module_summary.csv', index=False, encoding='utf-8-sig')
    strings.to_csv(output / 'string_summary.csv', index=False, encoding='utf-8-sig')
    (output / 'registration_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    print('도면 점검 중...', flush=True)
    registered = set(frames.loc[frames.status == 'registered', 'image_id'])
    linked = work[work.link_status.astype(str).str.startswith('module_candidate') & work.drawing_x.notna()]
    audit = output / 'drawing_audit'
    audit.mkdir(exist_ok=True)
    groups, shifted = group_offsets(linked, site)
    shifted.to_csv(audit / 'groups_off_drawing.csv', encoding='utf-8-sig')
    undrawn_detections(work, registered, site).to_csv(audit / 'detections_without_drawing_module.csv', index=False, encoding='utf-8-sig')
    never_detected(work, registered, site).to_csv(audit / 'drawing_modules_never_detected.csv', index=False, encoding='utf-8-sig')

    lines = report.get('flight_lines') or {}
    summary = dict(frames=report['frames'], frames_registered=report['frames_registered'],
                   module_candidates=report['module_candidates'],
                   module_candidates_line_unresolved=report['module_candidates_line_unresolved'],
                   drawing_modules_observed=report['drawing_modules_observed'],
                   lines=lines.get('lines'), lines_resolved=lines.get('resolved'),
                   multi_view_agreement=(report.get('visual_link_agreement') or {}).get('agreement'),
                   groups_off_drawing=int(len(shifted)), group_offset_median_m=round(float(groups.offset_m.median()), 3),
                   keep_in_config=(calibration or {}).get('config'))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

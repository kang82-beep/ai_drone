"""Read-only image audit; writes CSV without neural inference or SDK calls."""
import csv
from pathlib import Path
from pv_inspector import config
from pv_inspector.geolocation import read_dji_pose, read_mrk, match_mrk, project_pixel
from PIL import Image


def main():
    config.configure('config.local.json')
    records=read_mrk(config.MRK_CSV_PATH)
    rows=[]
    for p in sorted(Path(config.INPUT_IMG_DIR).glob('*_T.JPG')):
        pose=read_dji_pose(p)
        record=match_mrk(p,records)
        with Image.open(p) as im:
            w,h=im.size
        lat,lon,status=project_pixel(w/2,h/2,w,h,pose.get('GpsLatitude'),pose.get('GpsLongitude'),pose,config.ALT_AGL_M,config.FOCAL_35MM_EQ)
        rows.append(dict(image=p.name,mrk_matched=bool(record),status=status,center_lat=lat,center_lon=lon,
                         yaw=pose.get('GimbalYawDegree'),pitch=pose.get('GimbalPitchDegree'),roll=pose.get('GimbalRollDegree'),
                         relative_altitude=pose.get('RelativeAltitude'),rtk_flag=pose.get('RtkFlag')))
    out=Path('results/geolocation_check');out.mkdir(parents=True,exist_ok=True)
    with (out/'metadata_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['image'])
        writer.writeheader();writer.writerows(rows)
    print('Images:',len(rows),'MRK matches:',sum(r['mrk_matched'] for r in rows),'projectable:',sum(r['status']=='approximate_flat_plane' for r in rows))
    print('Audit:',out/'metadata_audit.csv')


if __name__=='__main__':
    main()

"""Replay visual association on the existing five-image detector observations."""
from pathlib import Path
import pandas as pd
from pv_inspector.association import associate_modules


def main():
    df=pd.read_csv('results/five_image_check/observations.csv').rename(columns={
        'image':'image_id','module':'module_id','u':'centroid_u','v':'centroid_v',
        'x1':'bbox_x1','x2':'bbox_x2','y1':'bbox_y1','y2':'bbox_y2','lat':'mod_lat','lon':'mod_lon'})
    paths={name:str(Path('image')/name) for name in df.image_id.unique()}
    out=Path('results/association_check')
    full,reps=associate_modules(df,paths,out)
    reps.to_csv(out/'provisional_modules.csv',index=False,encoding='utf-8-sig')
    assert len(full)==len(df)
    assert not full.duplicated(['module_uid','image_id']).any()
    print('Observations:',len(full),'provisional IDs:',len(reps),'multi-image tracks:',int((reps.observation_count>1).sum()))
    print(full.association_status.value_counts().to_dict())


if __name__=='__main__':
    main()

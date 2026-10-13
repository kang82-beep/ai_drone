"""Conservative within-run panel IDs from GPS candidates and thermal registration.

IDs are provisional, not surveyed catalog IDs. No RGB-to-thermal transform is
assumed. Every input observation survives; uncertain pairs remain separate.
"""
from collections import OrderedDict
from pathlib import Path
import math
import cv2
import numpy as np
import pandas as pd
from .dedup import _pick_representative


class Tracks:
    def __init__(self, frames):
        self.parent=list(range(len(frames)))
        self.frames=[{f} for f in frames]

    def root(self, i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]]
            i=self.parent[i]
        return i

    def join(self, i, j):
        a,b=self.root(i),self.root(j)
        if a==b:
            return True
        if self.frames[a]&self.frames[b]:
            return False
        a,b=sorted((a,b))
        self.parent[b]=a;self.frames[a]|=self.frames[b]
        return True


def separation(a,b):
    vals=[a.get('mod_lat'),a.get('mod_lon'),b.get('mod_lat'),b.get('mod_lon')]
    if any(pd.isna(v) for v in vals):
        return float('inf')
    lat,lon,la,lo=map(float,vals)
    return math.hypot(math.radians(la-lat)*6378137,
                      math.radians(lo-lon)*6378137*math.cos(math.radians((lat+la)/2)))


def associate_modules(df, image_paths, output_dir, gps_radius_m=2.0, frame_window=3):
    if gps_radius_m<=0 or frame_window<1:
        raise ValueError('Association radius/window must be positive')
    work=df.reset_index(drop=True).copy()
    if work.empty:
        return work,work.copy()
    tracks=Tracks(work.image_id.tolist())
    groups={str(k):g.index.tolist() for k,g in work.groupby('image_id',sort=True)}
    records=work.to_dict('records')
    cache=OrderedDict();sift=cv2.SIFT_create(nfeatures=6000)
    def features(name):
        if name in cache:
            cache.move_to_end(name);return cache[name]
        data=np.fromfile(str(image_paths[name]),dtype=np.uint8)
        im=cv2.imdecode(data,cv2.IMREAD_GRAYSCALE)
        if im is None:
            raise ValueError(f'Cannot decode {image_paths[name]}')
        h,w=im.shape;scale=1280/w
        im=cv2.resize(im,(1280,round(h*scale)))
        kp,desc=sift.detectAndCompute(im,None)
        cache[name]=(kp,desc,scale)
        while len(cache)>frame_window+2: cache.popitem(last=False)
        return cache[name]
    pairs=[];edges=[];names=sorted(image_paths)
    for pos,name in enumerate(names):
        if name not in groups: continue
        for other in names[pos+1:pos+1+frame_window]:
            if other not in groups: continue
            ai,bi=groups[name],groups[other]
            gps=np.array([[separation(records[i],records[j]) for j in bi] for i in ai])
            audit=dict(source=name,target=other,status='gps_no_candidate',inliers=0,links=0)
            if not np.any(gps<=gps_radius_m):
                pairs.append(audit);continue
            try:
                ka,da,sa=features(name);kb,db,sb=features(other)
                if da is None or db is None: raise ValueError('No descriptors')
                knn=cv2.BFMatcher().knnMatch(da,db,k=2)
                good=[m[0] for m in knn if len(m)==2 and m[0].distance<.7*m[1].distance]
                if len(good)<12: raise ValueError('Too few feature matches')
                src=np.float32([ka[m.queryIdx].pt for m in good]);dst=np.float32([kb[m.trainIdx].pt for m in good])
                cv2.setRNGSeed(42)
                H,mask=cv2.findHomography(src,dst,cv2.RANSAC,3)
                audit['inliers']=int(mask.sum()) if mask is not None else 0
                if H is None or audit['inliers']<20 or audit['inliers']/len(good)<.3:
                    raise ValueError('Insufficient registration consensus')
                valid=mask.ravel().astype(bool)
                hull=cv2.convexHull(dst[valid])
                source_hull=cv2.convexHull(src[valid])
                xy=np.float32([[[records[i]['centroid_u']*sa,records[i]['centroid_v']*sa]] for i in ai])
                moved=cv2.perspectiveTransform(xy,H)[:,0]
                target=np.float32([[records[j]['centroid_u']*sb,records[j]['centroid_v']*sb] for j in bi])
                distances=np.linalg.norm(moved[:,None,:]-target[None,:,:],axis=2)
                audit['status']='registered_no_links'
                for a,i in enumerate(ai):
                    b=int(distances[a].argmin());j=bi[b];r=records[j]
                    threshold=.25*min(r['bbox_x2']-r['bbox_x1'],r['bbox_y2']-r['bbox_y1'])*sb
                    if distances[a,b]>threshold or int(distances[:,b].argmin())!=a or gps[a,b]>gps_radius_m: continue
                    # Do not extrapolate a transform outside its feature support.
                    if cv2.pointPolygonTest(hull,tuple(map(float,target[b])),False)<0: continue
                    if cv2.pointPolygonTest(source_hull,tuple(map(float,xy[a,0])),False)<0: continue
                    # Reject almost-equally good neighboring panel candidates.
                    if len(bi)>1 and np.sort(distances[a])[1]<max(2*distances[a,b],threshold): continue
                    edges.append(dict(source_index=i,target_index=j,source=name,target=other,
                                      visual_error_px=float(distances[a,b]),gps_distance_m=float(gps[a,b])))
                    audit['links']+=1
                if audit['links']: audit['status']='thermal_candidates'
            except (ValueError,cv2.error,OSError) as exc:
                audit['status']='rgb_review_needed';audit['reason']=str(exc)
            pairs.append(audit)
        print(f'[Association] {pos+1}/{len(names)} {name}',flush=True)
    for edge in sorted(edges,key=lambda e:(e['visual_error_px'],e['gps_distance_m'])):
        edge['accepted']=tracks.join(edge['source_index'],edge['target_index'])
        edge['status']='provisional_visual_link' if edge['accepted'] else 'same_image_conflict'
    roots=[tracks.root(i) for i in range(len(work))]
    ids={r:i for i,r in enumerate(sorted(set(roots)))}
    work['cluster_id']=[ids[r] for r in roots]
    work['module_uid']=[f'M{ids[r]+1:07d}' for r in roots]
    count=work.groupby('module_uid').size()
    work['observation_count']=work.module_uid.map(count)
    work['association_status']=np.where(work.observation_count>1,'provisional_visual_track','unlinked')
    review=set()
    for p in pairs:
        if p['status']=='rgb_review_needed':review.update((p['source'],p['target']))
    work['rgb_review_needed']=work.image_id.isin(review)
    representatives=[]
    for _,g in work.groupby('module_uid',sort=True):
        representative=_pick_representative(g.to_dict('records'))
        representative['label_disagreement']=bool(g['final'].nunique()>1) if 'final' in g else False
        representatives.append(representative)
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    work.to_csv(out/'module_observations.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(pairs).reindex(columns=['source','target','status','inliers','links','reason']).to_csv(out/'association_pairs.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(edges).reindex(columns=['source_index','target_index','source','target','visual_error_px','gps_distance_m','accepted','status']).to_csv(out/'association_links.csv',index=False,encoding='utf-8-sig')
    return work,pd.DataFrame(representatives)

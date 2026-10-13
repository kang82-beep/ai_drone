"""Five-frame diagnostic: detector + geolocation + independent visual matching.

Not a full classification/temperature run. Outputs tentative correspondences,
not verified physical panel IDs. Run from the workspace root.
"""
import csv
import json
import math
import time
from pathlib import Path
import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from torchvision.transforms.functional import to_tensor
from torchvision.ops import nms
from pv_inspector import config
from pv_inspector.models import get_maskrcnn_model
from pv_inspector.geometry import filter_by_grid_adjacency
from pv_inspector.geolocation import read_dji_pose, project_pixel


def write_csv(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['empty'])
        w.writeheader();w.writerows(rows)


def main():
    config.configure('config.local.json')
    torch.set_num_threads(4)
    out=Path('results/five_image_check');out.mkdir(parents=True,exist_ok=True)
    paths=sorted(Path(config.INPUT_IMG_DIR).glob('*_T.JPG'))[100:105]
    model=get_maskrcnn_model(2)
    model.load_state_dict(torch.load(config.MASKRCNN_WEIGHTS,map_location='cpu',weights_only=True))
    model.eval()
    frames=[]; observations=[]; summaries=[]
    sift=cv2.SIFT_create(nfeatures=6000)
    for p in paths:
        started=time.time()
        with Image.open(p) as im: im=im.convert('RGB')
        w,h=im.size
        with torch.inference_mode(): pred=model([to_tensor(im)])[0]
        boxes=pred['boxes'].numpy().astype(int);scores=pred['scores'].numpy();labels=pred['labels'].numpy()
        masks=pred['masks'][:,0].numpy()>.5
        candidates=[]
        for box,score,label,mask in zip(boxes,scores,labels,masks):
            x1,y1,x2,y2=box.tolist();x1=max(0,x1);y1=max(0,y1);x2=min(w-1,x2);y2=min(h-1,y2)
            bw,bh=x2-x1,y2-y1;area=bw*bh;ma=int(mask[y1:y2,x1:x2].sum())
            if score<config.SCORE_TH or label!=1 or x1<=1 or y1<=1 or x2>=w-2 or y2>=h-2: continue
            if bw<config.MIN_MODULE_W or bh<config.MIN_MODULE_H: continue
            if max(area,ma)<max(config.MIN_AREA_PX,config.MIN_MODULE_AREA): continue
            candidates.append((float(score),x1,y1,x2,y2,int(label),mask))
        if candidates:
            keep=nms(torch.tensor([c[1:5] for c in candidates],dtype=torch.float32),torch.tensor([c[0] for c in candidates]),.5).tolist()
            candidates=[candidates[i] for i in keep]
            grid=filter_by_grid_adjacency(candidates,w,h,pair_required=True,size_outlier_tol=2.0,col_tol_mult=.7,row_near_min_mult=.3,row_near_max_mult=2.2)
            candidates=[candidates[i] for i in grid]
        pose=read_dji_pose(p);rows=[];draw=ImageDraw.Draw(im)
        for i,c in enumerate(candidates):
            score,x1,y1,x2,y2,_,_=c;u=(x1+x2)/2;v=(y1+y2)/2
            lat,lon,status=project_pixel(u,v,w,h,pose.get('GpsLatitude'),pose.get('GpsLongitude'),pose,config.ALT_AGL_M,config.FOCAL_35MM_EQ)
            row=dict(image=p.name,module=i+1,u=u,v=v,x1=x1,y1=y1,x2=x2,y2=y2,score=score,lat=lat,lon=lon,status=status)
            rows.append(row);draw.rectangle((x1,y1,x2,y2),outline='red',width=3);draw.text((x1+3,y1+3),str(i+1),fill='white')
        im.save(out/(p.stem+'_detections.jpg'))
        original=cv2.imread(str(p));gray=cv2.cvtColor(original,cv2.COLOR_BGR2GRAY)
        kp,desc=sift.detectAndCompute(gray,None)
        frames.append(dict(path=p,rows=rows,kp=kp,desc=desc,im=original))
        observations.extend(rows)
        summary=dict(image=p.name,modules=len(rows),seconds=round(time.time()-started,2))
        summaries.append(summary);print(summary,flush=True)
        del pred,masks,candidates
    pair_stats=[];matches=[]
    for a,b in zip(frames,frames[1:]):
        stat=dict(source=a['path'].name,target=b['path'].name,feature_matches=0,inliers=0,accepted=False,matched_modules=0)
        if a['desc'] is None or b['desc'] is None:
            pair_stats.append(stat);continue
        neighbors=cv2.BFMatcher().knnMatch(a['desc'],b['desc'],k=2)
        good=[x[0] for x in neighbors if len(x)==2 and x[0].distance<.7*x[1].distance]
        stat['feature_matches']=len(good)
        if len(good)<12:
            pair_stats.append(stat);continue
        src=np.float32([a['kp'][m.queryIdx].pt for m in good]);dst=np.float32([b['kp'][m.trainIdx].pt for m in good])
        H,inliers=cv2.findHomography(src,dst,cv2.RANSAC,3.0)
        stat['inliers']=int(inliers.sum()) if inliers is not None else 0
        if H is None or stat['inliers']<20 or stat['inliers']/len(good)<.3:
            pair_stats.append(stat);continue
        stat['accepted']=True
        err=np.linalg.norm(cv2.perspectiveTransform(src[:,None,:],H)[:,0]-dst,axis=1)
        stat['feature_error_median_px']=float(np.median(err[inliers.ravel().astype(bool)]))
        np.save(out/(a['path'].stem+'_to_'+b['path'].stem+'.npy'),H)
        ra,rb=a['rows'],b['rows']
        if ra and rb:
            xy=cv2.perspectiveTransform(np.float32([[[r['u'],r['v']]] for r in ra]),H)[:,0]
            target=np.float32([[r['u'],r['v']] for r in rb])
            distance=np.linalg.norm(xy[:,None]-target[None,:],axis=2)
            links=[]
            for i,r in enumerate(ra):
                j=int(distance[i].argmin());s=rb[j]
                threshold=.25*min(s['x2']-s['x1'],s['y2']-s['y1'])
                if distance[i,j]>threshold or int(distance[:,j].argmin())!=i: continue
                if r['lat'] is None or s['lat'] is None: continue
                north=math.radians(s['lat']-r['lat'])*6378137
                east=math.radians(s['lon']-r['lon'])*6378137*math.cos(math.radians(r['lat']))
                item=dict(source=r['image'],source_module=r['module'],target=s['image'],target_module=s['module'],visual_error_px=float(distance[i,j]),gps_difference_m=math.hypot(north,east),north_difference_m=north,east_difference_m=east)
                matches.append(item);links.append((r,s,item))
            stat['matched_modules']=len(links)
            if links:
                errors=[item['gps_difference_m'] for _,_,item in links]
                stat['gps_median_m']=float(np.median(errors));stat['gps_p95_m']=float(np.percentile(errors,95))
                canvas=np.concatenate([a['im'],b['im']],axis=1)
                for r,s,item in links[::max(1,len(links)//15)]:
                    x,y=int(r['u']),int(r['v']);xx,yy=int(s['u'])+a['im'].shape[1],int(s['v'])
                    cv2.line(canvas,(x,y),(xx,yy),(0,0,255),2)
                    cv2.putText(canvas,f"{r['module']}->{s['module']}",(x,y),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
                cv2.imwrite(str(out/(a['path'].stem+'_matches.jpg')),canvas)
        pair_stats.append(stat);print(stat,flush=True)
    write_csv(out/'observations.csv',observations);write_csv(out/'visual_matches.csv',matches)
    report=dict(scope='5 consecutive frames; location/duplicate diagnostic only; visual matches are tentative',height_m=config.ALT_AGL_M,images=summaries,pairs=pair_stats)
    (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Done:',out,flush=True)


if __name__=='__main__':
    main()

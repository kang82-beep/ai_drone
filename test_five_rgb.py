"""Compare RGB registration on the same five captures; no T/V calibration."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from pv_inspector.files import parse_tv_and_key5


def main():
    cv2.setNumThreads(4)
    cv2.setRNGSeed(42)
    root=Path('image')
    previous=json.loads(Path('results/five_image_check/summary.json').read_text())
    lookup={parse_tv_and_key5(str(p))[2]:p for p in root.glob('*_V.JPG')}
    paths=[lookup[parse_tv_and_key5(str(root/r['image']))[2]] for r in previous['images']]
    out=Path('results/five_rgb_check');out.mkdir(parents=True,exist_ok=True)
    sift=cv2.SIFT_create(nfeatures=6000)
    frames=[]
    sheet=Image.new('RGB',(1600,270))
    for i,p in enumerate(paths):
        im=cv2.imread(str(p));h,w=im.shape[:2]
        # Match the thermal test working width, avoiding a raw pixel-count advantage.
        small=cv2.resize(im,(1280,round(h*1280/w)),interpolation=cv2.INTER_AREA)
        gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        kp,desc=sift.detectAndCompute(gray,None)
        frames.append((p,small,kp,desc))
        thumb=Image.fromarray(cv2.cvtColor(small,cv2.COLOR_BGR2RGB));thumb.thumbnail((320,240))
        sheet.paste(thumb,(320*i,25));ImageDraw.Draw(sheet).text((320*i+3,5),p.stem,fill='white')
        print(p.name,'features',len(kp),flush=True)
    sheet.save(out/'selection.jpg')
    stats=[]
    for index,(a,b) in enumerate(zip(frames,frames[1:])):
        p,im,kp,desc=a;q,jm,kq,deq=b
        stat=dict(source=p.name,target=q.name,working_size=[im.shape[1],im.shape[0]],feature_matches=0,inliers=0,accepted=False)
        if desc is None or deq is None:
            stats.append(stat);continue
        candidates=cv2.BFMatcher().knnMatch(desc,deq,k=2)
        good=[m for m,n in candidates if m.distance<.7*n.distance]
        stat['feature_matches']=len(good)
        if len(good)<12:
            stats.append(stat);continue
        src=np.float32([kp[m.queryIdx].pt for m in good]);dst=np.float32([kq[m.trainIdx].pt for m in good])
        H,mask=cv2.findHomography(src,dst,cv2.RANSAC,3.0)
        if H is None:
            stats.append(stat);continue
        valid=mask.ravel().astype(bool)
        stat['inliers']=int(valid.sum());stat['inlier_ratio']=float(valid.mean())
        stat['accepted']=bool(valid.sum()>=20 and valid.mean()>=.3)
        errors=np.linalg.norm(cv2.perspectiveTransform(src[:,None,:],H)[:,0]-dst,axis=1)
        stat['inlier_error_median_px']=float(np.median(errors[valid]))
        stat['inlier_error_p95_px']=float(np.percentile(errors[valid],95))
        stat['source_inlier_hull_fraction']=float(cv2.contourArea(cv2.convexHull(src[valid]))/(im.shape[0]*im.shape[1]))
        stat['target_inlier_hull_fraction']=float(cv2.contourArea(cv2.convexHull(dst[valid]))/(jm.shape[0]*jm.shape[1]))
        # Held-out correspondences: fit on 70%, evaluate the untouched 30%.
        order=np.random.default_rng(42).permutation(len(good));cut=int(.7*len(good))
        train,test=order[:cut],order[cut:]
        ht,_=cv2.findHomography(src[train],dst[train],cv2.RANSAC,3.0)
        if ht is not None:
            e=np.linalg.norm(cv2.perspectiveTransform(src[test,None,:],ht)[:,0]-dst[test],axis=1)
            stat['heldout_count']=len(test);stat['heldout_within_3px_fraction']=float((e<=3).mean())
        np.save(out/f'pair_{index+1}_homography.npy',H)
        vis=cv2.drawMatches(im,kp,jm,kq,[m for m,v in zip(good,valid) if v][::max(1,int(valid.sum())//35)],None,flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        cv2.imwrite(str(out/f'pair_{index+1}_matches.jpg'),vis)
        warped=cv2.warpPerspective(im,H,(jm.shape[1],jm.shape[0]))
        occupancy=cv2.warpPerspective(np.ones(im.shape[:2],np.uint8),H,(jm.shape[1],jm.shape[0]),flags=cv2.INTER_NEAREST)>0
        checker=jm.copy();yy,xx=np.indices(jm.shape[:2]);choose=occupancy&(((xx//80+yy//80)%2)==0)
        checker[choose]=warped[choose]
        cv2.imwrite(str(out/f'pair_{index+1}_checkerboard.jpg'),checker)
        stat['overlap_target_fraction']=float(occupancy.mean())
        stats.append(stat);print(stat,flush=True)
    (out/'summary.json').write_text(json.dumps(dict(scope='RGB-RGB only; same detector settings and 1280-pixel working width; no physical panel identity validation',pairs=stats),indent=2),encoding='utf-8')


if __name__=='__main__':
    main()

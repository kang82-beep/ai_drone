"""Conservative two-row array evidence, independent of GPS and the drawing layout.

supported/review/low are rule outcomes, not calibrated probabilities or fault labels.
Assessment retains every detection; filtering separately records exclusions.
A missing mate alone never proves a false detection.
"""
from collections import Counter, defaultdict
import math
import cv2
import numpy as np
from scipy.spatial import cKDTree

VERSION = 'two_row_v1'
LABELS = {'supported': '2열 구조 지지', 'review': '구조 확인 필요', 'low': '모듈 가능성 낮음'}
COLORS = {'supported': '#35d59b', 'review': '#ffb347', 'low': '#d85cff'}
REASONS = {'two_rows_repeated': '2열 짝과 반복 간격 확인', 'missing_mate': '짝 모듈 검출 부족',
           'short_track': '연속 모듈 근거 부족', 'isolated': '배열에서 고립된 후보',
           'size_outlier': '주변 모듈과 크기 불일치', 'orientation_outlier': '배열 방향 불일치',
           'more_than_two_rows': '2열보다 많은 평행 열로 모호함', 'edge_partial': '영상 가장자리 또는 부분 검출',
           'insufficient_context': '구조를 추정할 후보 부족', 'invalid_geometry': '유효하지 않은 모듈 형상'}


class Groups:
    def __init__(self,n):self.parent=list(range(n))
    def root(self,i):
        while self.parent[i]!=i:
            self.parent[i]=self.parent[self.parent[i]];i=self.parent[i]
        return i
    def join(self,i,j):self.parent[self.root(j)]=self.root(i)


def assess_two_rows(candidates, image_size=None):
    """Use short-edge direction along an array, long-edge direction across its 2 rows.

    Polygon geometry supports camera rotation. Pair tests use local module dimensions;
    global PCA of the whole site is deliberately not used to infer array orientation.
    """
    n=len(candidates)
    results=[{'version':VERSION,'status':'review','reasons':['insufficient_context'],
              'mate_ids':[],'track_size':0,'same_row_neighbors':0,'two_row_eligible':False} for _ in candidates]
    if not n:return results
    centers=[];short=[];long=[];axes=[];valid=[]
    for i,item in enumerate(candidates):
        try:
            poly=np.asarray(item['polygon'],dtype=np.float32)
            if poly.ndim!=2 or poly.shape[1]!=2 or len(poly)<3 or not np.isfinite(poly).all():raise ValueError()
            box=cv2.boxPoints(cv2.minAreaRect(poly));vectors=np.roll(box,-1,axis=0)-box
            lengths=np.linalg.norm(vectors,axis=1);k=int(np.argmin(lengths))
            s=float(lengths[k]);l=float(lengths.max())
            if s<=0 or l<=0:raise ValueError()
            centers.append(np.mean(poly,axis=0));short.append(s);long.append(l);axes.append(vectors[k]/s);valid.append(i)
        except (KeyError,ValueError,cv2.error):
            results[i].update(status='low',reasons=['invalid_geometry'])
    if len(valid)<6:return results
    centers=np.asarray(centers);short=np.asarray(short);long=np.asarray(long);axes=np.asarray(axes)
    # Robust orientation consensus modulo pi, avoiding cancellation of reversed edges.
    angles=np.arctan2(axes[:,1],axes[:,0]);usable=long/short>1.15
    if usable.sum()<4:return results
    bins=np.floor((angles[usable]%np.pi)/np.pi*36).astype(int)
    peak=Counter(bins).most_common(1)[0][0]
    near=usable & (np.abs(np.angle(np.exp(2j*(angles-(peak+.5)*np.pi/36))))<math.radians(35))
    theta=.5*np.angle(np.mean(np.exp(2j*angles[near])))
    axis=np.array([math.cos(theta),math.sin(theta)]);cross=np.array([-axis[1],axis[0]])
    aligned=np.abs(axes@axis)>=math.cos(math.radians(25))
    u=centers@axis;v=centers@cross
    tree=cKDTree(centers);s0=float(np.median(short[aligned]));l0=float(np.median(long[aligned]))
    neighbors=tree.query_ball_point(centers,3.4*l0)
    good=(short>.6*s0)&(short<1.6*s0)&(long>.65*l0)&(long<1.55*l0)&aligned
    local_s=np.full(len(valid),s0);local_l=np.full(len(valid),l0)
    for i,nb in enumerate(neighbors):
        peers=[j for j in nb if good[j]]
        if len(peers)>=5:local_s[i]=np.median(short[peers]);local_l[i]=np.median(long[peers])
    good &= (short>.6*local_s)&(short<1.6*local_s)&(long>.65*local_l)&(long<1.55*local_l)
    groups=Groups(len(valid));along=[[] for _ in valid];across=[[] for _ in valid]
    for i,nb in enumerate(neighbors):
        if not good[i]:continue
        for j in nb:
            if j<=i or not good[j]:continue
            du=abs(u[j]-u[i]);dv=abs(v[j]-v[i]);s=(local_s[i]+local_s[j])/2;l=(local_l[i]+local_l[j])/2
            if .6*s<=du<=2.4*s and dv<=.24*l:
                groups.join(i,j);along[i].append(j);along[j].append(i)
            if .65*l<=dv<=1.45*l and du<=.35*s:
                across[i].append(j);across[j].append(i)
    tracks=defaultdict(list)
    for i in range(len(valid)):
        if good[i]:tracks[groups.root(i)].append(i)
    links=defaultdict(set)
    for i,mates in enumerate(across):
        for j in mates:
            a,b=groups.root(i),groups.root(j)
            if a!=b:links[tuple(sorted([a,b]))].add((min(i,j),max(i,j)))
    partners=defaultdict(set)
    for (a,b),pairs in links.items():
        if len(pairs)>=3 and len(pairs)>=.25*max(len(tracks[a]),len(tracks[b])):
            partners[a].add(b);partners[b].add(a)
    for i,original in enumerate(valid):
        item=results[original];track=groups.root(i);size=len(tracks.get(track,[]))
        edge=False
        if image_size:
            p=np.asarray(candidates[original]['polygon']);w,h=image_size
            edge=bool(p[:,0].min()<s0*.6 or p[:,1].min()<s0*.6 or p[:,0].max()>w-s0*.6 or p[:,1].max()>h-s0*.6)
        mate_ids=[candidates[valid[j]].get('id',str(valid[j])) for j in across[i]]
        item.update(mate_ids=mate_ids,track_size=size,same_row_neighbors=len(along[i]),
                    orientation_deg=round(math.degrees(theta),2),track_id=int(track))
        if not good[i]:
            reason='orientation_outlier' if not aligned[i] else 'size_outlier'
            item.update(status='review' if edge else 'low',reasons=[reason]+(['edge_partial'] if edge else []))
        elif len(partners[track])>1 or any(len(partners[p])>1 for p in partners[track]):
            item.update(status='review',reasons=['more_than_two_rows'])
        elif len(partners[track])==1 and size>=3:
            partner=next(iter(partners[track]))
            if any(groups.root(j)==partner for j in across[i]):
                item.update(status='supported',reasons=['two_rows_repeated'],two_row_eligible=True)
            else:item.update(status='review',reasons=['missing_mate']+(['edge_partial'] if edge else []))
        elif edge:item.update(status='review',reasons=['edge_partial'])
        elif size>=3:item.update(status='review',reasons=['missing_mate'])
        else:item.update(status='low',reasons=['isolated' if not along[i] and not across[i] else 'short_track'])
    return results


def describe(result):
    return LABELS[result['status']]+' · '+', '.join(REASONS[r] for r in result['reasons'])


def filter_two_row_candidates(candidates, image_size=None):
    """Return kept indices and auditable decisions; never infer missing modules.

    Reject only isolated/size outliers outside supported row envelopes. A different
    orientation, short track, edge, missing mate, or weak scene evidence is retained.
    Envelopes are per track, not a bounding box spanning the entire installation.
    """
    assessments = assess_two_rows(candidates, image_size)
    supported = [i for i, r in enumerate(assessments) if r['status'] == 'supported']
    envelopes = []
    if len(supported) >= max(6, math.ceil(len(candidates) * .25)):
        tracks = defaultdict(list)
        for i in supported:
            tracks[assessments[i]['track_id']].append(i)
        for indices in tracks.values():
            theta = math.radians(assessments[indices[0]]['orientation_deg'])
            basis = np.array([[math.cos(theta), math.sin(theta)],
                              [-math.sin(theta), math.cos(theta)]])
            polys = [np.asarray(candidates[i]['polygon']) @ basis.T for i in indices]
            points = np.concatenate(polys)
            dims = np.median([np.ptp(p, axis=0) for p in polys], axis=0)
            margin = dims * [1.5, .75]
            envelopes.append((basis, points.min(axis=0)-margin, points.max(axis=0)+margin))
    kept = []
    valid_polys = [np.asarray(c['polygon'], dtype=float) for c in candidates]
    centers = np.asarray([p.mean(axis=0) for p in valid_polys]) if candidates else np.empty((0, 2))
    for i, result in enumerate(assessments):
        result.update(filter_action='keep', filter_reason='structure_supported'
                      if result['status'] == 'supported' else 'uncertain_preserved')
        eligible = result['status'] == 'low' and set(result['reasons']) <= {'isolated', 'size_outlier'}
        if envelopes and eligible:
            poly = np.asarray(candidates[i]['polygon'])
            # Polygon bounding intervals overlap => preserve even if center is outside.
            overlaps = any(np.all((poly @ basis.T).max(axis=0) >= lo) and
                           np.all((poly @ basis.T).min(axis=0) <= hi)
                           for basis, lo, hi in envelopes)
            # A real array may consist of merged/missed detections and lack paired
            # support. Preserve its repeated centers even when sizes are atypical.
            repeated = False
            for basis, _, _ in envelopes:
                projected = centers @ basis.T
                dims = np.median([np.ptp(valid_polys[j] @ basis.T, axis=0)
                                  for j in supported], axis=0)
                delta = np.abs(projected - projected[i])
                neighbors = (delta[:, 0] > .3*dims[0]) & (delta[:, 0] < 4*dims[0]) & (delta[:, 1] < .8*dims[1])
                if np.count_nonzero(neighbors) >= 2:
                    repeated = True
                    break
            if repeated:
                result['filter_reason'] = 'unpaired_track_preserved'
            elif not overlaps:
                result.update(filter_action='reject', filter_reason='outside_two_row_array')
        if result['filter_action'] == 'keep':
            kept.append(i)
    return kept, assessments


def detector_candidates(cands):
    """Prefer oriented detector masks, falling back to axis-aligned bounding boxes."""
    items=[]
    for i,(_,x1,y1,x2,y2,_,mask) in enumerate(cands):
        crop=np.asarray(mask[y1:y2,x1:x2],dtype=np.uint8)
        contours,_=cv2.findContours(crop,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contour=max(contours,key=cv2.contourArea)
            polygon=cv2.boxPoints(cv2.minAreaRect(contour))+[x1,y1]
        else:polygon=np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]])
        items.append({'id':str(i),'polygon':polygon.tolist()})
    return items

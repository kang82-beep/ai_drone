"""Re-infer sample frames and compare legacy/new filters in a separate folder."""
import json
from pathlib import Path
import torch
from PIL import Image, ImageDraw
from torchvision.transforms.functional import to_tensor
from torchvision.ops import nms
from pv_inspector import config
from pv_inspector.models import get_maskrcnn_model
from pv_inspector.geometry import filter_by_grid_adjacency
from pv_inspector.two_row_structure import detector_candidates, filter_two_row_candidates


def main():
    config.configure('config.local.json')
    torch.set_num_threads(4)
    out=Path('results/two_row_filter_check');out.mkdir(parents=True,exist_ok=True)
    model=get_maskrcnn_model(2)
    model.load_state_dict(torch.load(config.MASKRCNN_WEIGHTS,map_location='cpu',weights_only=True))
    model.eval()
    summaries=[]; records=[]
    all_paths=sorted(Path(config.INPUT_IMG_DIR).glob('*_T.JPG'))
    paths=all_paths[100:105]
    paths += [p for p in all_paths if any(f'_{number}_T' in p.stem for number in ('0230','0275','0312','0351')) and p not in paths]
    for path in paths:
        with Image.open(path) as source: image=source.convert('RGB')
        w,h=image.size
        with torch.inference_mode(): pred=model([to_tensor(image)])[0]
        cands=[]
        for box,score,label,mask in zip(pred['boxes'],pred['scores'],pred['labels'],pred['masks'][:,0]):
            x1,y1,x2,y2=map(int,box.tolist())
            x1=max(0,x1);y1=max(0,y1);x2=min(w-1,x2);y2=min(h-1,y2)
            mask=mask.numpy()>.5
            area=(x2-x1)*(y2-y1);ma=int(mask[y1:y2,x1:x2].sum())
            if float(score)<config.SCORE_TH or int(label)!=1:continue
            if x2-x1<config.MIN_MODULE_W or y2-y1<config.MIN_MODULE_H:continue
            if max(area,ma)<max(config.MIN_AREA_PX,config.MIN_MODULE_AREA):continue
            cands.append((float(score),x1,y1,x2,y2,int(label),mask))
        legacy=[c for c in cands if c[1]>1 and c[2]>1 and c[3]<w-2 and c[4]<h-2]
        def suppress(items):
            if not items:return []
            indices=nms(torch.tensor([c[1:5] for c in items],dtype=torch.float32),torch.tensor([c[0] for c in items]),.5).tolist()
            return [items[i] for i in indices]
        legacy=suppress(legacy)
        old=filter_by_grid_adjacency(legacy,w,h)
        cands=suppress(cands)
        kept, decisions=filter_two_row_candidates(detector_candidates(cands),(w,h))
        old_boxes={tuple(legacy[i][1:5]) for i in old}
        new_boxes={tuple(cands[i][1:5]) for i in kept}
        before=image.copy();after=image.copy();bd=ImageDraw.Draw(before);ad=ImageDraw.Draw(after)
        for box in old_boxes:bd.rectangle(box,outline='#35d59b',width=2)
        for i,(c,r) in enumerate(zip(cands,decisions)):
            color='#ff4050' if r['filter_action']=='reject' else '#35d59b' if r['status']=='supported' else '#ffb347'
            ad.rectangle(c[1:5],outline=color,width=2)
            if r['filter_action']=='reject':ad.text((c[1],c[2]),str(i),fill='white')
            records.append(dict(image=path.name,candidate=i,bbox=list(c[1:5]),**r))
        canvas=Image.new('RGB',(w*2,h+30),'black')
        canvas.paste(before,(0,30));canvas.paste(after,(w,30))
        draw=ImageDraw.Draw(canvas);draw.text((10,8),'LEGACY',fill='white')
        draw.text((w+10,8),'NEW: green=supported orange=review red=excluded',fill='white')
        canvas.save(out/(path.stem+'_comparison.jpg'),quality=92)
        summary=dict(image=path.name,candidates=len(cands),legacy_kept=len(old),new_kept=len(kept),
                     excluded=len(cands)-len(kept),added_vs_legacy=len(new_boxes-old_boxes),removed_vs_legacy=len(old_boxes-new_boxes))
        summaries.append(summary);print(summary,flush=True)
    if not summaries:raise RuntimeError('No sample images found')
    (out/'decisions.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')


if __name__=='__main__':main()

from pathlib import Path
import json
import rasterio
from rasterio.enums import Resampling
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/shinan2_review';OUT.mkdir(parents=True,exist_ok=True)
source=Path('C:/3d/result (1).tif')
with rasterio.open(source) as src:
    report={'source':str(source),'width':src.width,'height':src.height,'count':src.count,'dtypes':src.dtypes,'crs':str(src.crs),'bounds':list(src.bounds),'transform':list(src.transform),'overviews':src.overviews(1),'tags':src.tags()}
    scale=2400/max(src.width,src.height);w=int(src.width*scale);h=int(src.height*scale)
    arr=src.read(list(range(1,min(3,src.count)+1)),out_shape=(min(3,src.count),h,w),resampling=Resampling.average)
    if arr.dtype!=np.uint8:
        lo,hi=np.percentile(arr,[1,99]);arr=np.clip((arr-lo)/max(hi-lo,1)*255,0,255).astype(np.uint8)
    Image.fromarray(np.moveaxis(arr,0,-1)).save(OUT/'orthomosaic_preview.jpg',quality=93)
(OUT/'raster_metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='tags'},indent=2))

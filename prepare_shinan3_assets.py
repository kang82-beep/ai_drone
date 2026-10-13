"""Portable viewer data and deterministic, seamless illustrative PBR textures.

Textures are authored approximations, never represented as photographs of the site.
"""
from pathlib import Path
import json, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'shinan3_viewer/assets'
OUT.mkdir(parents=True, exist_ok=True)
data = json.loads((ROOT/'results/shinan3_blender/layout.json').read_text(encoding='utf-8'))
compact = {k: v for k, v in data.items() if k not in ('modules', 'groups', 'buildings')}
compact['groups'] = [{k: g[k] for k in ('id','bounds','cad_handle')} for g in data['groups']]
compact['buildings'] = [{k:v for k,v in b.items() if k != 'plan_lines'} for b in data['buildings']]
(OUT/'layout.json').write_text(json.dumps(compact, ensure_ascii=False, separators=(',',':')), encoding='utf-8')

rng = np.random.default_rng(31007)
N = 1024
def fractal():
    """Periodic FFT-filtered multiscale noise, no seams at repeated edges."""
    out = np.zeros((N,N))
    fy = np.fft.fftfreq(N)[:,None]; fx = np.fft.fftfreq(N)[None,:]
    rr = fx*fx + fy*fy
    for sigma, strength in ((90,.36),(24,.28),(5,.22),(.65,.14)):
        raw = rng.normal(size=(N,N))
        field = np.fft.ifft2(np.fft.fft2(raw)*np.exp(-2*np.pi*np.pi*sigma*sigma*rr)).real
        out += strength * field / (field.std()+1e-9)
    return out

def save_rgb(name, array):
    Image.fromarray(np.uint8(np.clip(array,0,255))).save(OUT/name, quality=94)

def normal(name, height, strength):
    dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*strength
    dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*strength
    normal=np.stack((-dx,-dy,np.ones_like(dx)),axis=2)
    normal/=np.linalg.norm(normal,axis=2,keepdims=True)
    save_rgb(name,(normal*.5+.5)*255)

ground = fractal()
fine = rng.normal(0,1,(N,N))
base = np.array([128,120,102])
color=base+ground[:,:,None]*np.array([13,12,10])+fine[:,:,None]*3
save_rgb('ground_color.jpg',color)
normal('ground_normal.jpg',ground+fine*.18,.65)
concrete=fractal(); pores=rng.random((N,N))>.993
save_rgb('concrete_color.jpg',np.array([168,166,157])+concrete[:,:,None]*8-pores[:,:,None]*29)
normal('concrete_normal.jpg',concrete*.15-pores*.2,.75)
save_rgb('metal_roughness.jpg',np.repeat(np.clip(130+fractal()*9,0,255)[:,:,None],3,axis=2))

# 6 x 10 generic polycrystalline cells; not a claim about the installed make/model.
W,H=768,1280
panel=Image.new('RGB',(W,H),(93,106,118)); draw=ImageDraw.Draw(panel)
cw,ch=W/6,H/10
for row in range(10):
    for col in range(6):
        x0,y0=int(col*cw)+3,int(row*ch)+5
        x1,y1=int((col+1)*cw)-3,int((row+1)*ch)-5
        shift=int(rng.integers(-6,7))
        draw.rounded_rectangle((x0,y0,x1,y1),radius=5,fill=(24+shift,43+shift,69+shift))
        for _ in range(20):
            xx=int(rng.integers(x0+1,x1)); yy=int(rng.integers(y0+1,y1))
            r=int(rng.integers(4,17)); s=int(rng.integers(-6,7))
            draw.polygon([(xx,yy),(min(x1,xx+r),yy),(xx,min(y1,yy+r))],fill=(25+shift+s,45+shift+s,73+shift+s))
        for y in range(y0+4,y1,6):draw.line((x0+1,y,x1-1,y),fill=(52+shift,67+shift,85+shift),width=1)
        for frac in (.25,.5,.75):
            x=int(x0+(x1-x0)*frac); draw.line((x,y0,x,y1),fill=(88,105,122),width=1)
panel.save(OUT/'panel_color.jpg',quality=97)

refs=OUT/'reference';refs.mkdir(exist_ok=True)
for name in ('electrical_021.png','electrical_022.png','electrical_023.png','civil_127.png'):
    src=ROOT/'results/shinan3_blender/source_pages'/name
    if src.exists():shutil.copy2(src,refs/name)
shutil.copy2(ROOT/'results/shinan3_blender/module_catalog.csv', OUT/'module_catalog.csv')
manifest={'texture_origin':'Deterministically authored procedural PBR approximations; not measured site scans.',
 'ground_reference':'Preconstruction site photographs: muted grey/brown soil, gravel and reeds. Current finished surface unknown.',
 'panel_reference':'Generic illustrative 6x10 cell grid; installed product cell construction is not photographically verified.',
 'source_dwg_sha256':data['source_sha256'], 'module_count':len(data['groups'])*20,
 'coordinate_conversion':'Three.js (east, elevation, -north); source (east,north,elevation)',
 'physics_scope':'Static scene and navigation collisions; no structural, aerodynamic or thermal simulation.'}
(OUT/'asset_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Viewer assets generated:',OUT)

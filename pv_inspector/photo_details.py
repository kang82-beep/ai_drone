"""Photo-observed appearance; dimensions and repetition remain illustrative."""
import math

PHOTO_SOURCE = 'IMG_5909–5943.JPG; appearance observed, detail dimensions/placement assumed'


def building_details(b, equipment):
    from .site_structures import box, beam
    L,D=b['length'],b['depth'];out=[];key=b['id']
    def add(name,x,y,z,w,d,h,kind):
        out.append(box(key+'-PHOTO-'+name,x,y,z,w,d,h,kind,PHOTO_SOURCE))
    add('FLOOR',.18,.18,.501,L-.36,D-.36,.012,'floor')
    for y in [3.95,4.15]:add(f'AISLE-{y}',.3,y,.516,L-.6,.06,.004,'marking')
    # Shallow strips represent horizontal sandwich-panel joints, not textures.
    for i in range(1,16):
        z=.5+i*.25
        add(f'JOINT-S-{i}',0,D,z,L,.012,.012,'wall')
        for a,c in [(0,.8),(2.2,L-4.6),(L-3.2,L)]:
            add(f'JOINT-N-{i}-{a}',a,-.012,z,c-a,.012,.012,'wall')
        for x in [-.012,L]:add(f'JOINT-END-{i}-{x}',x,0,z,.012,D,.012,'wall')
    for x in [L*.27,L*.46,L*.65]:
        for y in [-.045,D+.015]:
            add(f'WINDOW-FRAME-{x}-{y}',x,y,1.65,.85,.035,.6,'window_frame')
            add(f'WINDOW-GLASS-{x}-{y}',x+.05,y-.006 if y<0 else y+.036,1.7,.75,.006,.5,'glass')
    for x in [-.045,L+.015]:
        for y in [D*.25,D*.7]:
            add(f'END-WINDOW-{x}-{y}',x,y,1.65,.03,.85,.85,'window_frame')
            add(f'END-GLASS-{x}-{y}',x-.006 if x<0 else x+.031,y+.05,1.7,.006,.75,.75,'glass')
    for y in [0,D]:add(f'EAVE-{y}',-.15,y-.08,4.48,L+.3,.16,.2,'roof')
    for x in [0,L]:
        for j,(a,c) in enumerate([((x,0,4.55),(x,D/2,6.05)),((x,D/2,6.05),(x,D,4.55))]):
            p=beam(key+f'-PHOTO-ROOF-TRIM-{x}-{j}',a,c,.15,.2,'roof');p['source']=PHOTO_SOURCE;out.append(p)
    for i in range(4):
        x=L*(i+1)/5
        add(f'ROOF-VENT-STEM-{i}',x-.16,D/2-.16,6,.32,.32,.25,'roof_metal')
        # Faceted cylindrical ventilator envelope.
        verts=[(x+.3*math.cos(j*math.tau/12),D/2+.3*math.sin(j*math.tau/12),z) for z in [6.2,6.55] for j in range(12)]
        out.append({'id':key+f'-PHOTO-ROOF-VENT-{i}','kind':'roof_metal','source':PHOTO_SOURCE,'vertices':verts,'faces':[tuple(range(11,-1,-1)),tuple(range(12,24))]+[(j,(j+1)%12,(j+1)%12+12,j+12) for j in range(12)]})
    for i,x in enumerate([.8,L-4.6]):
        add(f'CANOPY-{i}',x-.15,-.65,2.85,1.7,.8,.12,'wall')
    for i in range(5):
        x=.5+i*(L-1)/4
        for j,(a,c) in enumerate([((x,0,4.4),(x,D/2,5.85)),((x,D/2,5.85),(x,D,4.4)),((x,0,4.4),(x,D,4.4))]):
            p=beam(key+f'-PHOTO-TRUSS-{i}-{j}',a,c,.1,.15,'steel');p['source']=PHOTO_SOURCE;out.append(p)
    for p in equipment:
        if p['kind'] not in ('equipment','inverter'):continue
        start=len(out)
        xs,ys,zs=zip(*p['vertices']);x,y,z=min(xs),max(ys)+.025,min(zs);w=max(xs)-x;h=max(zs)-z
        tag=p['id'].replace(key+'-','')
        if p['kind']=='inverter':add(tag+'-BAND',x,y,z+h*.7,w,.012,.25,'orange')
        add(tag+'-HANDLE',x+w*.82,y+.02,z+h*.43,.025,.035,.18,'dark_detail')
        add(tag+'-WARNING',x+w*.3,y+.018,z+h*.48,w*.4,.006,.14,'marking')
        add(tag+'-DISPLAY',x+w*.25,y+.018,z+h*.8,w*.35,.01,.12,'dark_detail')
        for i in range(7):add(tag+f'-LOUVER-{i}',x+w*.15,y+.018,z+.13+i*.035,w*.7,.008,.009,'dark_detail')
        if min(ys)>D/2:
            for detail in out[start:]:detail['vertices']=[(xx,min(ys)+max(ys)-yy,zz) for xx,yy,zz in detail['vertices']]
    return out

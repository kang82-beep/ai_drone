"""Drawing-derived buildings and explicitly assumed visualization structures (metres)."""
import math
from .drawing_model import SPEC

FACES = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
ASSUMPTIONS = {
    'panel_low_top_m': 0.9, 'post_section_m': 0.10,
    'footing_size_m': [0.65,0.65,0.8], 'footing_bottom_m': -0.6,
    'support_frames_per_10_modules': 5, 'rail_section_m': [0.06,0.08],
    'note': 'Visualization assumptions, not structural design; flat ground z=0. Building location traced from p.14; dimensions p.6/7, elevations p.61. Roof thickness, wall thickness, openings and support sections simplified.',
}

def box(key,x,y,z,w,d,h,kind='steel',source='assumed'):
    return {'id':key,'kind':kind,'source':source,'vertices':[(x,y,z),(x+w,y,z),(x+w,y+d,z),(x,y+d,z),(x,y,z+h),(x+w,y,z+h),(x+w,y+d,z+h),(x,y+d,z+h)],'faces':FACES}

def beam(key,a,b,width=.08,depth=.08,kind='steel'):
    axis=[b[i]-a[i] for i in range(3)]; length=math.sqrt(sum(t*t for t in axis)); axis=[t/length for t in axis]
    ref=(0,0,1) if abs(axis[2])<.9 else (0,1,0)
    u=[axis[1]*ref[2]-axis[2]*ref[1],axis[2]*ref[0]-axis[0]*ref[2],axis[0]*ref[1]-axis[1]*ref[0]]
    norm=math.sqrt(sum(t*t for t in u));u=[t/norm for t in u]
    v=[axis[1]*u[2]-axis[2]*u[1],axis[2]*u[0]-axis[0]*u[2],axis[0]*u[1]-axis[1]*u[0]]
    vertices=[tuple(p[i]+s*width/2*u[i]+t*depth/2*v[i] for i in range(3)) for p in (a,b) for s,t in [(-1,-1),(1,-1),(1,1),(-1,1)]]
    return {'id':key,'kind':kind,'source':'assumed','vertices':vertices,'faces':FACES}

def raised_modules(strip):
    from .site_model import strip_modules
    result=strip_modules(strip)
    for m in result:
        m.update(kind='module',source='PDF p.10–11; elevation assumed',faces=FACES)
        m['vertices']=[(x,y,z+ASSUMPTIONS['panel_low_top_m']) for x,y,z in m['vertices']]
    return result

def module_frames(modules):
    for m in modules:
        # Thin perimeter strips within the module envelope; section is illustrative.
        p=m['vertices']
        for i,j in [(0,1),(1,2),(2,3),(3,0)]:
            a=tuple(p[i][k]+(p[i+4][k]-p[i][k])*.3 for k in range(3))
            b=tuple(p[j][k]+(p[j+4][k]-p[j][k])*.3 for k in range(3))
            yield beam(m['id']+f'-FRAME-{i}',a,b,.018,.028,'frame')

def supports(strip):
    angle=math.radians(SPEC.tilt_deg); depth=2*SPEC.module_length*math.cos(angle)
    def pt(x,s,offset=0):return (x,strip['y']+depth-s*math.cos(angle),ASSUMPTIONS['panel_low_top_m']+s*math.sin(angle)+offset)
    result=[]
    for g in range(strip['groups']):
        x=strip['x']+g*(SPEC.group_width+SPEC.group_gap); prefix=f"{strip['id']}-G{g+1}"
        result.append(box(prefix+'-PHOTO-APRON',x,strip['y']+.2,-.08,SPEC.group_width,depth-.4,.10,'foundation','IMG_5910/5911: continuous concrete apron observed; extent/thickness assumed'))
        for i,s in enumerate([.35,1.3,2.05,3.0]):
            result.append(beam(prefix+f'-RAIL-{i}',pt(x,s,-.085),pt(x+SPEC.group_width,s,-.085),.06,.08))
        for n in range(5):
            xx=x+.3+n*(SPEC.group_width-.6)/4
            low,high=pt(xx,.45,-.21),pt(xx,2.9,-.21)
            for j,p in enumerate([low,high]):
                result.append(box(prefix+f'-F{n}-{j}',p[0]-.325,p[1]-.325,-.6,.65,.65,.8,'foundation'))
                result.append(box(prefix+f'-BASE{n}-{j}',p[0]-.12,p[1]-.12,.2,.24,.24,.025,'steel'))
                result.append(beam(prefix+f'-POST{n}-{j}',(p[0],p[1],.225),p,.1,.1))
                for k,(dx,dy) in enumerate([(-.085,-.085),(.085,-.085),(.085,.085),(-.085,.085)]):
                    result.append(box(prefix+f'-ANCHOR-{n}-{j}-{k}',p[0]+dx-.009,p[1]+dy-.009,.225,.018,.018,.12,'steel','IMG_5910: four anchor caps; dimensions assumed'))
            result.append(beam(prefix+f'-RAFTER{n}',pt(xx,.18,-.155),pt(xx,3.17,-.155),.08,.12))
            result.append(beam(prefix+f'-BRACE{n}',(low[0],low[1],.35),(high[0],high[1],high[2]-.12),.045,.045))
    return result

def buildings(data):
    result=[]
    for i,(px,py,pw,ph) in enumerate(data['footprints_review_px'],1):
        # Same local scan mapping as panel layout, using the relevant X dimension chain.
        lane=0 if i==1 else 2; origins=[503,758,1020,1275]; metres=[0,86.58,175.16,261.74]
        x=metres[lane]+(px-origins[lane])*82.58/245; y=(py-130)*292.077/876
        result.append({'id':f'ER-{i:02d}','label':f'전기실 {i}호','x':x,'y':y,'length':20.5 if i==1 else 18.,'depth':9.6,'rotated':i==1,'source':f'PDF p.{5+i}, p.61; p.14 scan position','position_status':'scan approximation'})
    return result

def building_parts(building):
    b=building; key=b['id']; L=b['length'];D=b['depth']; parts=[]
    def add(s,u,v,z,w,d,h,kind,source=None):
        parts.append(box(key+'-'+s,u,v,z,w,d,h,kind,source or b['source']))
    add('PLINTH',-.15,-.15,-.3,L+.3,D+.3,.8,'foundation','PDF p.61 floor +0.5; slab thickness assumed')
    # Longitudinal walls with two explicit doorway gaps on the north/east side.
    add('WALL-S',0,D-.18,.5,L,.18,4,'wall')
    for a,c in [(0,.8),(2.2,L-4.6),(L-3.2,L)]:add(f'WALL-N-{a}',a,0,.5,c-a,.18,4,'wall')
    for u in [.8,L-4.6]:
        add(f'DOOR-{u}',u,.05,.5,1.4,.06,2.2,'door','opening position from p.6/7; simplified height')
        add(f'HEADER-{u}',u,0,2.7,1.4,.18,1.8,'wall')
        add(f'STEP-{u}',u,-.65,0,1.4,.65,.25,'foundation','illustrative entrance step')
    add('END-1',0,0,.5,.18,D,4,'wall');add('END-2',L-.18,0,.5,.18,D,4,'wall')
    for side in [0,1]:
        v0,v1=(0,D/2) if side==0 else (D/2,D)
        z0,z1=(4.5,6.) if side==0 else (6.,4.5)
        vertices=[(0,v0,z0),(L,v0,z0),(L,v1,z1),(0,v1,z1)]
        parts.append({'id':key+f'-ROOF-{side}','kind':'roof','source':'PDF p.61; elevations relative to ground','vertices':vertices+[(x,y,z+.12) for x,y,z in vertices],'faces':FACES})
    for u in [0,L-.18]:
        vertices=[(u,0,4.5),(u,D,4.5),(u,D/2,6),(u+.18,0,4.5),(u+.18,D,4.5),(u+.18,D/2,6)]
        parts.append({'id':key+f'-GABLE-{u}','kind':'wall','source':'PDF p.61','vertices':vertices,'faces':[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)]})
    if key=='ER-01':
        add('CONTROL-PARTITION',2.7,.18,.5,.12,D-.36,3,'wall','PDF p.6; simplified partition')
        upper=[('REC-1',.8,1.5,2.35),('LV-B',.8,1.5,2.35),('LV-A',.8,1.5,2.35),('MCCB-1',.8,1.5,2.35)]+[(f'INV-{g}{j}',.8,1.3,2.1) for g in 'AB' for j in range(5)]
        lower=[('TR-B',2,2.5,2.55),('TR-A',2,2.5,2.55),('TR-1',2,2.5,2.55)]+[(s,1.3,2.5,2.55) for s in ['VCB-4','VCB-3','VCB-2','VCB-1','PT-1','MOF-1','LBS-1']]
        runs=[(upper,3.65,1.25),(lower,4.25,5.3)]
    else:
        upper=[(f'TR-{g}',2,2.5,2.55) for g in 'EDC']+[(f'VCB-{j}',1.3,2.5,2.55) for j in [8,7,6,5]]
        lower=[(s,.8,1.5,2.35) for s in ['REC-2','MCCB-2','LV-E','LV-D','LV-C']]+[(f'INV-{g}{j}',.8,1.3,2.1) for g in 'CDE' for j in [4,3,2,1,0]]
        runs=[(upper,1,1.85),(lower,1,6.9)]
    for equipment,u,v in runs:
        for name,w,d,h in equipment:
            kind='inverter' if name.startswith('INV') else 'equipment'
            add(name,u,v,.5,w,d,h,kind,f'PDF p.{6 if key=="ER-01" else 7} equipment schedule / simplified envelope')
            add(name+'-FRONT',u+.08,v-.012 if v>D/2 else v+d,.8,w-.16,.012,h-.5,'inverter_front' if kind=='inverter' else 'equipment_front','illustrative cabinet face, facing central aisle')
            u+=w
    from .photo_details import building_details
    parts.extend(building_details(b,parts))
    # Rotate No.1 plan (north points left in p.6) into site coordinates.
    for p in parts:
        p['vertices']=[(b['x']+D-v,b['y']+u,z) if b['rotated'] else (b['x']+u,b['y']+v,z) for u,v,z in p['vertices']]
    return parts

COLORS={'module':'#23779c','frame':'#d4dde0','steel':'#a3b8c2','foundation':'#96948c','wall':'#dfd7bf','roof':'#657e88','door':'#3b687c','equipment':'#a8b9b6','inverter':'#52a69b','equipment_front':'#385962'}
COLORS.update(wall='#aeb8b4',roof='#315d84',door='#9ca8a5',equipment='#999b86',inverter='#e7e5d9',equipment_front='#c4c3b3',floor='#367d69',marking='#eac447',orange='#df702f',dark_detail='#303b3d',window_frame='#e8ece8',glass='#344b50',junction='#9b9e8e')
ASSUMPTIONS['photo_reference']='35 photos IMG_5909–5943: materials, facade details, anchors, apron and cabinet appearance. Detail dimensions and application to both rooms are inferred; no surveyed reconstruction.'

COLORS.update(roof_metal='#b6bfc0',inverter_front='#e7e5d9')
SHELL_KINDS=('wall','roof','door','roof_metal','window_frame','glass')

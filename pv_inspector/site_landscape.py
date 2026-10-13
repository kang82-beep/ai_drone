"""Photo-informed concrete maintenance roads aligned to drawing clearances."""
from .site_structures import box

ROAD_SOURCE='PDF p.14 array clearances; IMG_5923–5929 concrete road appearance; pavement boundaries/thickness/drains inferred'


def road_rectangles():
    return [
        ('ROAD-W',82.83,-5,3.5,301),
        ('ROAD-MAIN',169.46,-5,5.4,301),
        ('ROAD-E',257.99,-5,3.5,301),
        ('ROAD-CROSS-N',-.5,102.05,258.3,2.85),
        ('ROAD-CROSS-M',-.5,168.2,345.3,4.6),
        ('ROAD-CROSS-S',-.5,215.0,258.3,2.8),
        ('ROAD-SOUTH',-.5,292,345.3,4),
    ]


def landscape_parts():
    parts=[box('GROUND',-15,-20,-.3,375,330,.3,'ground','Flat illustrative ground; no surveyed terrain')]
    occupied=[]
    for key,x,y,w,d in road_rectangles():
        # Subtract earlier road rectangles to prevent coincident pavement at junctions.
        pieces=[(x,y,x+w,y+d)]
        for ax,ay,bx,by in occupied:
            remainder=[]
            for x0,y0,x1,y1 in pieces:
                ix0,iy0,ix1,iy1=max(x0,ax),max(y0,ay),min(x1,bx),min(y1,by)
                if ix0>=ix1 or iy0>=iy1:remainder.append((x0,y0,x1,y1));continue
                for rect in [(x0,y0,ix0,y1),(ix1,y0,x1,y1),(ix0,y0,ix1,iy0),(ix0,iy1,ix1,y1)]:
                    if rect[2]>rect[0] and rect[3]>rect[1]:remainder.append(rect)
            pieces=remainder
        for i,(a,b,c,e) in enumerate(pieces):parts.append(box(key+f'-P{i}',a,b,.025,c-a,e-b,.055,'concrete_road',ROAD_SOURCE))
        occupied.append((x,y,x+w,y+d))
        # Thin control joints, flush with pavement; no traffic lane markings observed.
        if d>w:
            for i in range(1,int(d/5)):
                parts.append(box(key+f'-JOINT-{i}',x,y+i*5,.0801,w,.012,.001,'road_joint',ROAD_SOURCE))
        else:
            for i in range(1,int(w/5)):
                parts.append(box(key+f'-JOINT-{i}',x+i*5,y,.0801,.012,d,.001,'road_joint',ROAD_SOURCE))
    # Grated drains observed along road margins; approximate placement along main road only.
    for x in [169.2,174.91]:
        parts.append(box(f'DRAIN-{x}',x,0,.022,.20,291,.07,'drain',ROAD_SOURCE))
        for i in range(970):parts.append(box(f'GRATE-{x}-{i}',x,i*.3,.095,.20,.018,.012,'steel',ROAD_SOURCE))
    return parts

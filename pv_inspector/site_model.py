"""Full-site layout instantiated from the PDF standard module specification."""
import json
import math
from pathlib import Path
from .drawing_model import SPEC

LAYOUT=Path(__file__).resolve().parents[1]/'results'/'drawing_site'/'site_layout.json'


def load_site():
    return json.loads(LAYOUT.read_text(encoding='utf-8'))


def strip_modules(strip):
    angle=math.radians(SPEC.tilt_deg)
    modules=[]
    # Drawing page has north upwards. Model Y increases down-page (south).
    # Low edge is to the south; the panel rises towards north.
    depth=2*SPEC.module_length*math.cos(angle)
    def vertex(x,s,t):
        return (x,strip['y']+depth-s*math.cos(angle)+t*math.sin(angle),s*math.sin(angle)+t*math.cos(angle))
    for row in range(2):
        for col in range(strip['columns']):
            group,local=divmod(col,10)
            x=strip['x']+group*(SPEC.group_width+SPEC.group_gap)+local*(SPEC.module_width+SPEC.lateral_gap)
            s=row*SPEC.module_length
            corners=[(x,s),(x+SPEC.module_width,s),(x+SPEC.module_width,s+SPEC.module_length),(x,s+SPEC.module_length)]
            vertices=[vertex(px,ps,t) for t in (0,-SPEC.module_thickness) for px,ps in corners]
            modules.append({'id':f"{strip['id']}-R{row+1}-M{col+1:03d}",'vertices':vertices,'strip':strip['id']})
    return modules


def strip_outline(strip):
    d=2*SPEC.module_length*math.cos(math.radians(SPEC.tilt_deg))
    z=2*SPEC.module_length*math.sin(math.radians(SPEC.tilt_deg))
    x,y,w=strip['x'],strip['y'],strip['width']
    return [(x,y+d,0),(x+w,y+d,0),(x+w,y,z),(x,y,z)]

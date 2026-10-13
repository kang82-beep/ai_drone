"""Drawing-derived standard array; SI units, local coordinates, explicit provenance."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class ArraySpec:
    module_width: float = 1.001
    module_length: float = 1.675
    module_thickness: float = 0.034
    rated_watts: int = 245
    tilt_deg: float = 22
    modules_per_group: int = 10
    groups: int = 4
    slope_rows: int = 2
    lateral_gap: float = 0.025
    group_gap: float = 0.100
    ground_clearance: float | None = None

    @property
    def group_width(self):
        return self.modules_per_group*self.module_width+(self.modules_per_group-1)*self.lateral_gap

    @property
    def width(self):
        return self.groups*self.group_width+(self.groups-1)*self.group_gap


SPEC=ArraySpec()
PROVENANCE={
    'module_size':'PDF p.10 / SA-E-11110 / 1675 × 1001 × 34t',
    'power_tilt':'PDF p.10 / SA-E-11110 / 245Wp, 22°',
    'width_gaps':'PDF p.11 / SA-E-11120 / 10235 × 4 + 100 × 3 = 41240mm; 25mm gaps',
    'rows':'PDF p.10 / SA-E-11110 / 1675 × 2 = 3350mm',
    'count':'Derived: 4 groups × 10 columns × 2 slope rows = 80 modules',
    'datum':'Local low edge z=0; not terrain elevation. Actual ground clearance unknown.',
    'pending':['Foundation and support members','Terrain and installation height','Full-site array positions and exceptions','Plan/section inter-array spacing reconciliation','Physical equipment IDs'],
}


def build_array(spec=SPEC):
    """8 vertices/module, thickness along panel normal; low top edge is datum."""
    angle=math.radians(spec.tilt_deg)
    def point(x,s,t):
        return (x-spec.width/2, s*math.cos(angle)-t*math.sin(angle), s*math.sin(angle)+t*math.cos(angle))
    modules=[]
    for group in range(spec.groups):
        for row in range(spec.slope_rows):
            for column in range(spec.modules_per_group):
                x=group*(spec.group_width+spec.group_gap)+column*(spec.module_width+spec.lateral_gap)
                s=row*spec.module_length
                outline=[(x,s),(x+spec.module_width,s),(x+spec.module_width,s+spec.module_length),(x,s+spec.module_length)]
                vertices=[point(px,ps,t) for t in [0,-spec.module_thickness] for px,ps in outline]
                modules.append({'id':f'DRAFT-A01-G{group+1:02d}-R{row+1}-M{column+1:02d}',
                                'group':group+1,'row':row+1,'column':column+1,'vertices':vertices})
    return modules


def export_model(path):
    import json
    from pathlib import Path
    payload={'schema_version':1,'units':'m','model':'standard_array_only','spec':asdict(SPEC),'provenance':PROVENANCE,'modules':build_array()}
    Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

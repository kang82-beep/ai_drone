"""Extract the phase-3 CAD layout, preserving entity handles and plan geometry."""
from pathlib import Path
import sys,json,math,csv,hashlib,collections
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tmp/pdfdeps'))
import ezdxf
from ezdxf.disassemble import recursive_decompose
from shapely.geometry import Polygon
from shapely.ops import unary_union,triangulate

OUT=ROOT/'results/shinan3_blender';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path('C:/3호기준공도서CD/전기/1. 도면/CAD/3SA-E-11210_C.dwg')
doc=ezdxf.readfile(ROOT/'results/shinan3_source/layout.dxf')
assert doc.units==4, 'Drawing must be millimetres'
model=doc.modelspace()
inserts=[e for e in model.query('INSERT') if e.dxf.name=='모듈']
assert len(inserts)==1500
groups=[]
all_points=[]
for ins in inserts:
    polys=[]
    for entity in ins.virtual_entities():
        if entity.dxftype()!='LWPOLYLINE':continue
        points=[tuple(p)[:2] for p in entity.vertices_in_wcs()]
        if len(points)!=4:continue
        lengths=sorted(math.dist(points[i],points[(i+1)%4]) for i in range(4))
        if abs(lengths[0]-983)<.01 and abs(lengths[-1]-1425)<.01:
            polys.append(points)
    assert len(polys)==20,ins.dxf.handle
    all_points.extend(p for poly in polys for p in poly)
    groups.append({'cad_handle':ins.dxf.handle,'cad_rotation':ins.dxf.rotation,'polygons_mm':polys})
# Paper north is CAD -X, east is CAD +Y (electrical drawing north arrow).
origin=[min(p[0] for p in all_points),min(p[1] for p in all_points)]
def xy(p):return [(p[1]-origin[1])/1000,-(p[0]-origin[0])/1000]
groups.sort(key=lambda g:(-sum(p[0] for p in g['polygons_mm'][0])/4,sum(p[1] for p in g['polygons_mm'][0])/4))
modules=[]
for n,g in enumerate(groups,1):
    g['id']=f'S3-G{n:04}'
    g['polygons']=[[xy(p) for p in poly] for poly in g.pop('polygons_mm')]
    xs=[p[0] for poly in g['polygons'] for p in poly];ys=[p[1] for poly in g['polygons'] for p in poly]
    g['bounds']=[min(xs),min(ys),max(xs),max(ys)]
    g['polygons'].sort(key=lambda poly:(round(sum(p[1] for p in poly)/4,3),sum(p[0] for p in poly)/4))
    for i,poly in enumerate(g['polygons']):
        mid=f"{g['id']}-R{i//10+1}-M{i%10+1:02}"
        modules.append({'id':mid,'group_id':g['id'],'cad_insert_handle':g['cad_handle'],'polygon_xy_m':poly,
                        'center_xy_m':[sum(p[k] for p in poly)/4 for k in (0,1)],'rated_w':250})

boundaries=[]
for e in model.query('LWPOLYLINE'):
    if e.dxf.layer=='P-신청지' and e.closed:
        pts=[xy(tuple(p)[:2]) for p in e.vertices_in_wcs()]
        if Polygon(pts).is_valid:boundaries.append(pts)
assert boundaries
boundary=max(boundaries,key=lambda p:Polygon(p).area)

buildings=[]
for ins in model.query('INSERT'):
    if ins.dxf.name not in ['no.1','no.2','no.3']:continue
    # Find the paired dense wall coordinate bands, excluding canopy extents.
    angle=math.radians(ins.dxf.rotation+(0 if ins.dxf.name=='no.1' else 90))
    co,si=math.cos(angle),math.sin(angle)
    points=[];plan_lines=[]
    for e in recursive_decompose([ins]):
        if e.dxftype()=='LINE':pts=[tuple(e.dxf.start)[:2],tuple(e.dxf.end)[:2]]
        elif e.dxftype()=='LWPOLYLINE':
            pts=[tuple(p)[:2] for p in e.vertices_in_wcs()]
            if e.closed:pts.append(pts[0])
        else:continue
        points.extend(pts)
        for a,b in zip(pts,pts[1:]):
            if math.dist(a,b)>.1:plan_lines.append([xy(a),xy(b)])
    local=[(p[0]*co+p[1]*si,-p[0]*si+p[1]*co) for p in points]
    centers=[];bands=[]
    for k,target in [(0,20500),(1,9600)]:
        counts=collections.Counter(round(p[k],1) for p in local)
        candidates=[]
        for a,ca in counts.most_common(100):
            for b,cb in counts.most_common(100):
                if abs((b-a)-target)<=220:
                    candidates.append((ca+cb,a,b))
        assert candidates,ins.dxf.name
        _,a,b=max(candidates);centers.append((a+b)/2);bands.append([a,b])
    cadcenter=[centers[0]*co-centers[1]*si,centers[0]*si+centers[1]*co]
    buildings.append({'id':'S3-ER'+ins.dxf.name[-1],'cad_block':ins.dxf.name,'cad_handle':ins.dxf.handle,
                      'center':xy(cadcenter),'rotation':angle-math.pi/2,'length':20.5,'width':9.6,
                      'floor_z':.5,'eave_z':4.5,'ridge_z':6.,'wall_band_evidence_mm':bands,
                      'plan_lines':plan_lines,'placement_method':'CAD wall coordinate-band center; verify against plan'})

site=Polygon(boundary)
fields=unary_union([Polygon([[g['bounds'][0],g['bounds'][1]],[g['bounds'][2],g['bounds'][1]],
                            [g['bounds'][2],g['bounds'][3]],[g['bounds'][0],g['bounds'][3]]]).buffer(1.55,join_style=2) for g in groups]).intersection(site)
field_triangles=[]
for poly in (list(fields.geoms) if hasattr(fields,'geoms') else [fields]):
    for t in triangulate(poly):
        if poly.covers(t):field_triangles.append(list(t.exterior.coords)[:3])
result={'schema_version':1,'site':'Shinan phase 3','source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'cad_origin_mm':origin,'coordinate_transform':'X=(CAD_Y-originY)/1000 east; Y=-(CAD_X-originX)/1000 north; Z synthetic local ground',
        'groups':groups,'modules':modules,'boundary':boundary,'buildings':buildings,'field_triangles':field_triangles,
        'spec':{'module_width_m':.983,'module_length_m':1.645,'module_thickness_m':.042,'tilt_deg':30,'rated_w':250,
                'module_plan_depth_m':1.425,'group_width_m':10.055,'group_depth_m':2.85,'low_edge_z_assumed_m':.8},
        'assumptions':['Flat Z=0 ground; CAD INSERT elevation ignored because 2D drawing contains inconsistent Z values.',
                       'Low panel edge 0.8m is assumed; support member sizes are illustrative.',
                       'Panel projected depth 1.425m follows rounded CAD plan; physical length differs by <0.5mm from nominal.',
                       'Green field surfaces are buffered array envelopes, not surveyed paving boundaries.',
                       'Building wall centers derived from coordinate bands; roof sizes/heights from architectural section.',
                       'Drawing IDs are not field serial numbers or thermal-analysis confirmed IDs.']}
(OUT/'layout.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
with (OUT/'module_catalog.csv').open('w',encoding='utf-8-sig',newline='') as stream:
    w=csv.writer(stream);w.writerow(['module_id','group_id','cad_insert_handle','east_m','north_m','rated_w','link_status'])
    for m in modules:w.writerow([m['id'],m['group_id'],m['cad_insert_handle'],*m['center_xy_m'],250,'unlinked'])
print(json.dumps({'groups':len(groups),'modules':len(modules),'capacity_kw':len(modules)*.25,'buildings':[{k:v for k,v in b.items() if k!='plan_lines'} for b in buildings]},indent=2))

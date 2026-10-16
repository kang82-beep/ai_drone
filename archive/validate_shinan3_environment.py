from pathlib import Path
import json
from shapely.geometry import Polygon,Point
ROOT=Path(__file__).resolve().parent
data=json.loads((ROOT/'shinan3_viewer/assets/environment.json').read_text())
layout=json.loads((ROOT/'shinan3_viewer/assets/layout.json').read_text(encoding='utf-8'))
site=Polygon(layout['boundary']);terrain=data['meshes'][0]
raised_intersections=0
for face in terrain['faces']:
    verts=[terrain['vertices'][i] for i in face]
    if max(v[2] for v in verts)>.001 and Polygon([v[:2] for v in verts]).intersects(site):raised_intersections+=1
assert raised_intersections==0,'Terrain must not raise the CAD site'
closest=min(site.distance(Point(x,n))-r for x,n,h,r,th,c in data['trees'])
assert closest>0,'Tree crowns must remain outside the CAD boundary'
assert len(data['trees'])==9000 and data['terrain_elevation_measured'] is False
field_overlaps=sum(Polygon([v[:2] for v in m['vertices']]).intersection(site).area for m in data['meshes'] if m['name'].startswith('Farmland'))
assert field_overlaps<.01
result={'environment_trees':len(data['trees']),'environment_surface_meshes':len(data['meshes']),'raised_terrain_triangles_intersecting_cad_site':raised_intersections,'minimum_tree_crown_clearance_from_site_m':closest,'farmland_overlap_with_site_m2':field_overlaps,'measured_elevation':False,'collision_scope':'Original flat-site navigation, unchanged'}
(ROOT/'results/shinan3_review/environment_data_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))

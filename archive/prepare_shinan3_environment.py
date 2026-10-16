"""Simplified surrounding landscape, traced visually from VWorld references.
No surveyed elevation or geographic registration is claimed.
"""
from pathlib import Path
import json,math,random
from shapely.geometry import Polygon,Point,LineString
ROOT=Path(__file__).resolve().parent
layout=json.loads((ROOT/'shinan3_viewer/assets/layout.json').read_text(encoding='utf-8'))
site=Polygon(layout['boundary']);rng=random.Random(31003)
def p(px,py):return [(px-340)/2.035,(147-py)/2.035]
# Pixel anchors: three electrical-room roof centers in plant_overview.jpg.
# Correspondence is visual and approximate, used only for context placement.
fields_px=[[(40,250),(285,340),(325,260),(320,215),(158,175),(75,90)],
 [(80,400),(275,470),(318,550),(299,705),(166,650),(64,550)],
 [(12,750),(171,670),(275,732),(296,826),(180,929),(58,895)],
 [(10,938),(131,950),(282,876),(325,915),(295,990),(105,1058),(10,1020)],
 [(12,100),(55,46),(111,100),(82,201),(15,191)]]
fields=[Polygon([p(*v) for v in poly]) for poly in fields_px]
roads_px=[[(306,166),(293,258),(283,342),(307,438),(320,520),(309,640),(318,748),(345,850),(324,937),(402,975),(549,1010),(668,1120),(775,1153),(892,1103),(1006,953),(1070,647),(1094,377),(1130,102),(1160,-50)],
 [(-220,225),(42,291),(285,342)],
 [(-160,930),(99,1025),(245,994),(324,937)],
 [(0,1040),(80,1190),(233,1340)],
 [(340,448),(621,446),(797,445),(1029,445)],
 [(342,659),(622,657),(984,657)],
 [(621,240),(621,448),(624,657),(625,988)],
 [(797,133),(797,445),(797,657),(797,1012)],
 [(1095,468),(1243,508)]]
roads=[[p(*v) for v in line] for line in roads_px]
roadshapes=[LineString(line) for line in roads]
hill_centers=[(-240,70,75,220,230),(-250,-350,70,220,185),(100,210,65,270,160),(-30,-680,80,280,240),(-650,-150,115,320,390),(-650,-850,85,290,250),(270,600,100,380,320)]
def coast(n):return 407+30*math.sin((n+100)/240)+.022*n
def height(x,n):
    pt=Point(x,n);distance=site.distance(pt)
    if distance<35:return 0.
    h=sum(a*math.exp(-(((x-cx)/sx)**2+((n-cn)/sn)**2)*1.8) for cx,cn,a,sx,sn in hill_centers)
    h*=min(1,max(0,(distance-35)/65))
    for f in fields:
        h*=min(1,max(0,(f.distance(pt)-26)/38))
    for road in roadshapes:
        h*=min(1,max(0,(road.distance(pt)-24)/42))
    h*=min(1,max(0,(coast(n)-x)/95))
    return h
meshes=[]
def addmesh(name,verts,faces,color):meshes.append({'name':name,'vertices':verts,'faces':faces,'color':color})
# Continuous terrain grid from western hills to the eastern coastal levee.
vv=[];ff=[];colors=[];nx,ny=110,150
for j in range(ny+1):
    n=-1300+j*2200/ny
    for i in range(nx+1):
        x=-1200+(coast(n)+1200)*i/nx;h=height(x,n);vv.append([x,n,h])
        if site.covers(Point(x,n)):c=[.15,.18,.12]
        else:c=[.105,.155,.065]
        jitter=.94+.12*rng.random();colors.append([v*jitter for v in c])
for j in range(ny):
    for i in range(nx):
        a=j*(nx+1)+i;ff.extend([[a,a+1,a+nx+2],[a,a+nx+2,a+nx+1]])
addmesh('Context_Terrain_ASSUMED_HEIGHT',vv,ff,[.32,.40,.26]);meshes[-1]['vertex_colors']=colors
terrain_vertices=vv
def mesh_height(x,n):
    row=min(ny-1,max(0,int((n+1300)/2200*ny)))
    col=min(nx-1,max(0,int((x+1200)/(coast(n)+1200)*nx)))
    for i in (col,max(0,col-1),min(nx-1,col+1)):
        a=row*(nx+1)+i
        for indices in ((a,a+1,a+nx+2),(a,a+nx+2,a+nx+1)):
            pa,pb,pc=[terrain_vertices[k] for k in indices]
            den=(pb[1]-pc[1])*(pa[0]-pc[0])+(pc[0]-pb[0])*(pa[1]-pc[1])
            u=((pb[1]-pc[1])*(x-pc[0])+(pc[0]-pb[0])*(n-pc[1]))/den
            v=((pc[1]-pa[1])*(x-pc[0])+(pa[0]-pc[0])*(n-pc[1]))/den
            if min(u,v,1-u-v)>=-1e-4:return u*pa[2]+v*pb[2]+(1-u-v)*pc[2]
    return height(x,n)
for i,f in enumerate(fields):
    coords=list(f.exterior.coords)[:-1]
    addmesh('Farmland_'+str(i+1),[[x,n,.12+i*.006] for x,n in coords],[list(range(len(coords)))],[[.23,.29,.10],[.17,.25,.08],[.30,.27,.12],[.20,.28,.10],[.16,.23,.08]][i])
# Sampled roads conform to the approximate landscape.
def ribbon(name,line,width,color,lift=.14,heightfun=height):
    shape=LineString(line);verts=[];faces=[];steps=max(2,int(shape.length/4))
    for k in range(steps+1):
        d=k/steps*shape.length;q=shape.interpolate(d);a=shape.interpolate(max(0,d-.5));b=shape.interpolate(min(shape.length,d+.5));dx,dy=b.x-a.x,b.y-a.y;l=math.hypot(dx,dy) or 1
        for side in (-1,1):
            x=q.x-side*dy/l*width/2;n=q.y+side*dx/l*width/2
            verts.append([x,n,heightfun(x,n)+lift])
        if k:idx=2*k;faces.extend([[idx-2,idx-1,idx+1],[idx-2,idx+1,idx]])
    addmesh(name,verts,faces,color)
for i,line in enumerate(roads):ribbon('Road_'+str(i+1),line,5.0 if i<4 else 4.2,[.32,.31,.27],.23+i*.006,mesh_height)
# Gentle tidal-flat and sea bands east of the levee, not bathymetry.
for name,start,end,col,z in [('Levee',0,8,[.30,.30,.24],.7),('Tidal_Upper',8,85,[.22,.26,.20],-.18),('Tidal_Wet',85,280,[.14,.21,.20],-.27),('Coastal_Water',280,1700,[.045,.14,.19],-.36)]:
    v=[];f=[]
    for j in range(151):
        n=-1300+j*2200/150;x=coast(n)
        v.extend([[x+start,n,z],[x+end,n,z]])
        if j:a=j*2;f.extend([[a-2,a-1,a+1],[a-2,a+1,a]])
    addmesh(name,v,f,col)
for k in range(11):
    line=[]
    for j in range(25):
        n=-1150+k*185+j*2.7;x=coast(n)+35+j*10+math.sin(j*.6+k)*8;line.append([x,n])
    ribbon('Tidal_Channel_'+str(k),line,2.5+k%3,[.23,.37,.39],-.15,lambda x,n:0)
# Trees are simplified canopy masses. Exclude site, fields, road margins and coast.
trees=[]
for _ in range(42000):
    x=rng.uniform(-1000,460);n=rng.uniform(-1150,760);pt=Point(x,n)
    if x>coast(n)-22 or site.distance(pt)<24 or any(f.distance(pt)<10 for f in fields) or any(r.distance(pt)<8 for r in roadshapes):continue
    if rng.random()>.67:continue
    trees.append([x,n,mesh_height(x,n),rng.uniform(4.0,7.5),rng.uniform(7.0,12.5),rng.randrange(4)])
    if len(trees)>=9000:break
result={'version':1,'scope':'Satellite-guided simplified surroundings; terrain elevations, vegetation and shoreline detail are illustrative, not surveyed.',
 'source':'VWorld / NGII imagery retrieved 2026-10-03; capture date unverified',
 'visual_mapping':'plant_overview pixel to local: E=(px-340)/2.035; N=(147-py)/2.035; approximate roof-center correspondence only',
 'meshes':meshes,'trees':trees,'tree_count':len(trees),'terrain_elevation_measured':False,
 'site_collision_scope':'Existing flat-site navigation only; surrounding terrain is visual context, not a walkable physics mesh'}
(ROOT/'shinan3_viewer/assets/environment.json').write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
(ROOT/'shinan3_viewer/environment_data.js').write_text('export default '+json.dumps(result,separators=(',',':'))+';\n',encoding='utf-8')
print('Environment meshes',len(meshes),'trees',len(trees))

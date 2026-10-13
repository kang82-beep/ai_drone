"""Traceable cable containment model. Route geometry is not a circuit/netlist model."""
import math
from .site_structures import beam,buildings,box,FACES,COLORS as MATERIAL_COLORS

COLORS={'tray':'#bdc6cb','tray_cover':'#d7be74','tray_support':'#829ca9',
        'cable_S':'#a886da','cable_L':'#4db8d6','cable_D':'#f39b48','cable_H':'#ed6965',
        'conduit':'#7dbb8b'}
CABLE_KINDS=set(COLORS)
MATERIAL_COLORS.update(COLORS)

def route(key,area,page,points,widths,**extra):
    return dict(id=key,area=area,page=page,source=f'PDF p.{page}',points=points,
                compartments=widths,width_m=sum(w for _,w in widths),containment='tray',
                height_m=.1,position_status='drawing traced; simplified bends',**extra)

def indoor_routes(b):
    """Coordinates traced on 1862x1312 review sheets, scaled by building dimensions."""
    result=[];one=b['id']=='ER-01';area=b['id']
    # Reviewed page extents correspond to the 20.5/18m by 9.6m dimension chains.
    maps={28:(380,1518,310,842),29:(376,1518,344,886),30:(470,1468,264,808),31:(187,1187,334,868)}
    def add(key,page,pts,ws):
        x0,x1,y0,y1=maps[page];z=.25 if page in (28,30) else 3.1
        points=[]
        for x,y in pts:
            u=(x-x0)/(x1-x0)*b['length'];v=(y-y0)/(y1-y0)*b['depth']
            points.append([b['x']+b['depth']-v,b['y']+u,z] if b['rotated'] else [b['x']+u,b['y']+v,z])
        result.append(route(area+'-'+key,area,page,points,ws,drawing_tag=key,
                            elevation_basis='FL-250' if page in (28,30) else 'FL+2600',
                            review_points=pts,review_canvas=[1862,1312],
                            note='FL=GL+0.5m. Z interpreted as tray bottom. Bend tangencies digitized, not fabrication geometry.'))
    if one:
        add('T-H101',28,[(590,720),(1438,720)],[('H',.4)])
        add('T-S102-L102',28,[(590,620),(1438,620)],[('S',.1),('L',.1)])
        add('T-S105-L105',28,[(819,397),(609,397),(591,420),(591,620)],[('S',.1),('L',.1)])
        add('T-S106-L106',28,[(591,620),(523,620),(490,661)],[('S',.1),('L',.1)])
        add('T-S107-L107',28,[(510,466),(510,598),(523,620)],[('S',.1),('L',.1)])
        add('T-L108',28,[(590,620),(590,720)],[('L',.2)])
        add('T-L109',28,[(590,720),(590,808),(565,826),(535,826)],[('L',.2)])
        add('T-S103-L103',28,[(748,411),(748,486),(776,515),(1058,515),(1079,490),(1079,455)],[('S',.05),('L',.45)])
        add('T-S104-L104',28,[(721,411),(721,511),(751,533),(848,533),(887,494),(887,455)],[('S',.05),('L',.45)])
        add('T-D150',28,[(887,451),(1058,451)],[('D',.2)])
        add('T-D160',28,[(1099,451),(1268,451)],[('D',.2)])
        add('T-L111',29,[(767,423),(767,637),(790,666),(820,666)],[('L',.5)])
        add('T-L112',29,[(722,423),(722,637),(694,666),(623,666)],[('L',.5)])
    else:
        add('T-H201',30,[(706,395),(1130,395)],[('H',.5)])
        add('T-H202',30,[(706,395),(536,395),(504,427),(504,465),(527,495)],[('H',.5)])
        add('T-S203-L203',30,[(527,495),(1130,495)],[('S',.1),('L',.1)])
        add('T-S207-L207',30,[(527,495),(504,514),(504,696),(527,719)],[('S',.1),('L',.1)])
        add('T-S208-L208',30,[(527,719),(733,719)],[('S',.1),('L',.1)])
        add('T-L209',30,[(687,289),(687,365),(706,395)],[('L',.5)])
        add('T-S204-L204',30,[(713,719),(713,651),(742,617),(914,617),(944,645),(944,662)],[('S',.05),('L',.45)])
        add('T-S205-L205',30,[(681,719),(681,611),(712,585),(930,585),(968,619),(1135,619),(1166,650),(1166,662)],[('S',.05),('L',.45)])
        add('T-S206-L206',30,[(635,719),(635,584),(665,551),(944,551),(980,585),(1150,585),(1183,619),(1367,619),(1390,650),(1390,662)],[('S',.05),('L',.45)])
        for key,x0,x1 in [('T-D250',750,922),('T-D260',969,1157),('T-D270',1195,1370)]:
            add(key,30,[(x0,662),(x1,662)],[('D',.2)])
        add('T-L211',31,[(440,790),(440,582),(470,552),(558,552)],[('L',.5)])
        add('T-L212',31,[(395,790),(395,532)],[('L',.5)])
        add('T-L213',31,[(349,790),(349,582),(320,552),(250,552)],[('L',.5)])
    return result

def outdoor_routes(data):
    """Plan topology from p.32-36; snap row stations to the existing p.14 layout."""
    rows={int(r['id'].split('-')[-1]):r for r in data['rows']}
    def y(n):return rows[n]['y']+1.2
    result=[]
    def add(key,area,page,pts,ws):
        result.append(route(key,area,page,[[x,yy,.142] for x,yy in pts],ws,drawing_tag=key,
                            elevation_basis='p.37 support top GL+100mm + U-channel 42mm',
                            note='Topology and widths from regional plan; XY row stations aligned to p.14 scan. Co-located S/L/D paths represented as one partitioned envelope; assembly is an interpretation.'))
        result[-1]['position_status']='plan topology; row-aligned approximation'
    sld=[('S',.05),('L',.05),('D',.1)]
    # Each split retains the plan tag and its width change. 1.642m offsets are dimensioned.
    A1,A2,A3,A4=1.642,80.938,88.222,167.518
    for key,pts,ws in [
        ('T-S344-L344-D344',[(A1,y(5)),(A1,y(8))],sld),
        ('T-S343-L343-D343',[(A1,y(8)),(A2,y(8))],sld),
        ('T-S341-L341-D341',[(A2,y(8)),(A2,y(12))],sld),
        ('T-S362-L362-D362',[(A2,y(4)),(A2,y(8))],sld),
        ('T-S363-L363-D363',[(A2,y(1)),(A2,y(4))],sld),
        ('T-D364',[(A2,y(1)),(A2,y(1)-1.2)],[('D',.2)]),
        ('T-S351-L351-D351',[(42.982,y(12)),(A3,y(12))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S353-L353-D353',[(A3,y(48)),(A3,y(51))],sld),
        ('T-S355-L355-D355',[(A3,y(43)),(A3,y(48))],sld),
        ('T-S356-L356-D356',[(A3,y(39)),(A3,y(43))],sld),
        ('T-S357-L357-D357',[(A3,y(37)),(A3,y(39))],sld),
        ('T-S371-L371-D371',[(A3,y(51)),(A4,y(51))],sld),
        ('T-S372-L372-D372',[(A4,y(48)),(A4,y(51))],sld),
        ('T-S373-L373-D373',[(A4,y(43)),(A4,y(48))],sld),
        ('T-S374-L374-D374',[(A4,y(39)),(A4,y(43))],sld),
        ('T-S375-L375-D375',[(A4,y(36)),(A4,y(39))],sld),
        ('T-S376-L376-D376',[(A4,y(35)),(A4,y(36))],sld),
    ]:add(key,'A',32,pts,ws)
    for key,pts,ws in [
        ('T-S311-L311-D311',[(42.982,y(13)),(42.982,y(16))],[('S',.05),('L',.15),('D',.2)]),
        ('T-S310-L310-D310',[(42.982,y(16)),(42.982,y(18))],[('S',.05),('L',.1),('D',.15)]),
        ('T-S312-L312-D312',[(42.982,y(18)),(42.982,y(20))],sld),
        ('T-S313-L313-D313',[(42.982,y(21)),(42.982,y(23))],sld),
        ('T-S314-L314-D314',[(42.982,y(23)),(42.982,y(26))],[('S',.05),('L',.05),('D',.15)]),
        ('T-S315-L315-D315',[(42.982,y(26)),(80.938,y(26))],sld),
        ('T-S317-L317-D317',[(80.938,y(26)),(80.938,y(28))],sld),
        ('T-S318-L318-D318',[(80.938,y(29)),(80.938,y(31))],sld),
        ('T-S319-L319-D319',[(80.938,y(31)),(80.938,y(34))],sld),
        ('T-S321-L321-D321',[(42.982,y(18)),(88.222,y(18))],sld),
        ('T-D324',[(88.222,y(52)),(88.222,y(54))],[('D',.2)]),
        ('T-S323-L323-D323',[(88.222,y(54)),(88.222,y(56))],sld),
        ('T-S325-L325-D325',[(88.222,y(56)),(88.222,y(59))],sld),
        ('T-S327-L327-D327',[(88.222,y(60)),(88.222,y(62))],sld),
        ('T-S328-D328',[(88.222,y(62)),(88.222,y(65))],[('S',.05),('D',.15)]),
        ('T-S329-L329-D329',[(88.222,y(65)),(88.222,y(67))],sld),
        ('T-S331-L331-D331',[(88.222,y(56)),(167.518,y(56))],sld),
        ('T-D334',[(167.518,y(52)),(167.518,y(54))],[('D',.2)]),
        ('T-S332-L332-D332',[(167.518,y(54)),(167.518,y(56))],sld),
        ('T-S333-L333-D333',[(167.518,y(56)),(167.518,y(59))],sld),
        ('T-S335-L335-D335',[(167.518,y(60)),(167.518,y(62))],sld),
        ('T-S316-L316-D316',[(167.518,y(62)),(167.518,y(67))],sld),
    ]:add(key,'B',33,pts,ws)
    for key,pts,ws in [
        ('T-D432',[(88.222,y(68)),(88.222,y(69))],[('D',.2)]),
        ('T-S431-L431-D431',[(88.222,y(69)),(167.518,y(69))],sld),
        ('T-S433-L433-D433',[(88.222,y(69)),(88.222,y(73))],sld),
        ('T-S434-L434-D434',[(88.222,y(73)),(88.222,y(77))],sld),
        ('T-D435',[(88.222,y(77)),(88.222,y(80))],[('D',.2)]),
        ('T-D422',[(167.518,y(68)),(167.518,y(69))],[('D',.2)]),
        ('T-S423-L423-D423',[(167.518,y(69)),(167.518,y(73))],sld),
        ('T-S424-L424-D424',[(167.518,y(73)),(167.518,y(77))],sld),
        ('T-S425-L425-D425',[(167.518,y(77)),(167.518,y(81))],[('S',.05),('L',.15),('D',.15)]),
        ('T-S413-L413-D413',[(176.802,y(118)),(176.802,y(120))],sld),
        ('T-S414-L414-D414',[(176.802,y(120)),(176.802,y(125))],sld),
        ('T-S415-L415-D415',[(176.802,y(125)),(176.802,y(129))],sld),
        ('T-S416-D416',[(176.802,y(129)),(176.802,y(131))],[('S',.05),('D',.15)]),
        ('T-S445-L445-D445',[(256.098,y(118)),(256.098,y(121))],sld),
        ('T-S446-L446-D446',[(256.098,y(121)),(256.098,y(125))],sld),
        ('T-S447-L447-D447',[(256.098,y(125)),(256.098,y(129))],sld),
    ]:add(key,'C',34,pts,ws)
    for key,pts,ws in [
        ('T-S465-L465-D465',[(176.802,y(98)),(176.802,y(101))],sld),
        ('T-S464-L464-D464',[(176.802,y(101)),(176.802,y(105))],sld),
        ('T-S463-L463-D463',[(176.802,y(105)),(176.802,y(109))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S462-L462-D462',[(176.802,y(109)),(218.142,y(109))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S471-L471-D471',[(218.142,y(109)),(256.098,y(109))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S474-L474-D474',[(256.098,y(98)),(256.098,y(101))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S473-L473-D473',[(256.098,y(101)),(256.098,y(105))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S472-L472-D472',[(256.098,y(105)),(256.098,y(109))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S454-L454-D460',[(218.142,y(110)),(218.142,y(114))],[('S',.05),('L',.1),('D',.3)]),
        ('T-S451-L451-D451',[(256.098,y(110)),(256.098,y(114))],[('S',.05),('L',.05),('D',.15)]),
        ('T-S410-L410-D410',[(176.802,y(114)),(187.0,y(114))],[('S',.05),('L',.1),('D',.25)]),
        ('T-S440-L440-D440',[(187.0,y(114)),(218.142,y(114))],[('S',.05),('L',.05),('D',.3)]),
        ('T-S441-L441-D441',[(218.142,y(114)),(256.098,y(114))],[('S',.05),('L',.1),('D',.15)]),
        ('T-S411-L411-D411',[(176.802,y(114)),(176.802,y(117))],[('S',.05),('L',.05),('D',.2)]),
        ('T-S442-L442-D442',[(256.098,y(114)),(256.098,y(117))],sld),
        ('T-D457',[(263.382,y(145)),(263.382,y(147))],[('D',.2)]),
        ('T-S456-L456-D456',[(263.382,y(147)),(263.382,y(150))],sld),
        ('T-S453-L453-D453',[(263.382,y(151)),(263.382,y(152))],sld),
        ('T-S443-L443-D443',[(263.382,y(152)),(263.382,y(156))],sld),
    ]:add(key,'D',35,pts,ws)
    for key,pts,ws in [
        ('T-D479',[(256.098,y(82)),(256.098,y(83))],[('D',.2)]),
        ('T-S478-L478-D478',[(256.098,y(83)),(256.098,y(87))],sld),
        ('T-S477-L477-D477',[(256.098,y(87)),(256.098,y(91))],sld),
        ('T-S476-L476-D476',[(256.098,y(91)),(256.098,y(97))],sld),
        ('T-D469',[(176.802,y(83)),(176.802,y(87))],[('D',.2)]),
        ('T-S468-L468-D468',[(176.802,y(87)),(176.802,y(91))],sld),
        ('T-S467-L467-D467',[(176.802,y(91)),(176.802,y(97))],sld),
        ('T-D485',[(263.382,y(134)),(263.382,y(136))],[('D',.2)]),
        ('T-S483-L483-D483',[(263.382,y(136)),(263.382,y(140))],sld),
        ('T-S482-L482-D482',[(263.382,y(140)),(263.382,y(144))],sld),
        ('T-S486-L486-D486',[(263.382,y(140)),(342.678,y(140))],sld),
        ('T-S488-L488-D488',[(342.678,y(132)),(342.678,y(135))],sld),
        ('T-S487-L487-D487',[(342.678,y(135)),(342.678,y(140))],sld),
    ]:add(key,'E',36,pts,ws)
    return result

def conduit_routes(data,trays):
    """Road crossings and room entries. XY connectors explicitly inferred between traced ends."""
    by={r['id']:r for r in trays};result=[]
    od={30:.04,50:.0645,80:.105,100:.130,125:.160,150:.188,200:.260}
    def link(key,area,page,start,end,diameters):
        diam=max(diameters);outer=od[diam];z=-(1.2+outer/2) # p.41 H=D+1.2m
        a=list(start);b=list(end)
        pts=[a,[a[0],a[1],z],[b[0],a[1],z],[b[0],b[1],z],b]
        pts=[p for i,p in enumerate(pts) if i==0 or math.dist(p,pts[i-1])>1e-6]
        r=route(key,area,page,pts,[],drawing_tag=key,elevation_basis='p.41 H = D + 1200mm',
                note='Diameter from drawing callout. Buried orthogonal connector and risers inferred between traced endpoints; not an as-built cable route.')
        r.update(containment='conduit',diameters_mm=diameters,outer_diameters_m=[od[d] for d in diameters],width_m=sum(od[d] for d in diameters)+.04*(len(diameters)-1),position_status='inferred connection; diameter from drawing')
        result.append(r)
    def p(key,end):return by[key]['points'][end]
    for key,area,page,a,ai,b,bi,ds in [
        ('R-S352-L352-D352','A',32,'T-S351-L351-D351',0,'T-S311-L311-D311',0,[30,80,125]),
        ('R-S354-L354-D354','A',32,'T-S353-L353-D353',1,'T-D324',0,[30,50,80]),
        ('R-S373-L373-D373','A',32,'T-S372-L372-D372',1,'T-D334',0,[30,50,80]),
        ('R-S313-L313-D313','B',33,'T-S312-L312-D312',1,'T-S313-L313-D313',0,[30,50,80]),
        ('R-S326-L326-D326','B',33,'T-S325-L325-D325',1,'T-S327-L327-D327',0,[30,30,50]),
        ('R-S335-L335-D335','B',33,'T-S333-L333-D333',1,'T-S335-L335-D335',0,[30,80,50]),
        ('R-S318-L318-D318','B',33,'T-S317-L317-D317',1,'T-S318-L318-D318',0,[30,30,30]),
        ('R-S421-D421','C',34,'T-S316-L316-D316',1,'T-D422',0,[30,80]),
        ('R-S417-D417','C',34,'T-S411-L411-D411',1,'T-S413-L413-D413',0,[30,50]),
        ('R-S444-L444-D444','D',35,'T-S442-L442-D442',1,'T-S445-L445-D445',0,[30,50,80]),
        ('R-S466-L466-D466','D',35,'T-S467-L467-D467',1,'T-S465-L465-D465',0,[30,30,80]),
        ('R-S475-L475-D475','D',35,'T-S476-L476-D476',1,'T-S474-L474-D474',0,[30,50,125]),
        ('R-S455-L455-D455','D',35,'T-S456-L456-D456',1,'T-S453-L453-D453',0,[30,50,80]),
    ]:link(key,area,page,p(a,ai),p(b,bi),ds)
    # Long feeders shown p.27/33/35: route endpoint stations are inferred to the room trays.
    for key,area,page,a,ai,b,bi,ds in [
        ('R-D151','ER-01',33,'T-S351-L351-D351',0,'ER-01-T-D150',0,[200]),
        ('R-D161','ER-01',33,'T-S321-L321-D321',0,'ER-01-T-D160',0,[200]),
        ('R-L131','ER-01',33,'T-S310-L310-D310',0,'ER-01-T-S102-L102',0,[200]),
        ('R-D251','ER-02',35,'T-S410-L410-D410',1,'ER-02-T-D250',0,[200]),
        ('R-D261','ER-02',35,'T-S440-L440-D440',1,'ER-02-T-D260',0,[200]),
        ('R-D271','ER-02',35,'T-S462-L462-D462',1,'ER-02-T-D270',0,[200]),
        ('R-L231','ER-02',35,'T-S410-L410-D410',0,'ER-02-T-S203-L203',0,[100]),
    ]:link(key,area,page,p(a,ai),p(b,bi),ds)
    return result

def all_routes(data):
    routes=outdoor_routes(data)
    for b in buildings(data):routes.extend(indoor_routes(b))
    return routes+conduit_routes(data,routes)

def _annotate(part,r):
    part.update(route_id=r['id'],area=r['area'],source=f"{r['source']} | {r['drawing_tag']} | {r['position_status']}")
    return part

def route_parts(r,detail=True,covers=True,cables=True):
    """3D containment and representative cable paths, not wire counts or conductor sizes."""
    out=[]
    for i,(a,b) in enumerate(zip(r['points'],r['points'][1:])):
        length=math.dist(a,b)
        if length<1e-7:continue
        key=r['id']+f'-S{i:02d}';dx,dy=b[0]-a[0],b[1]-a[1];horizontal=math.hypot(dx,dy)
        normal=(-dy/horizontal,dx/horizontal,0) if horizontal>1e-8 else (1,0,0)
        def joint_normal(vertex):
            if vertex<=0 or vertex>=len(r['points'])-1:return normal
            aa,bb,cc=r['points'][vertex-1:vertex+2]
            dirs=[]
            for p,q in [(aa,bb),(bb,cc)]:
                d=math.hypot(q[0]-p[0],q[1]-p[1])
                if d<1e-8:return normal
                dirs.append((-(q[1]-p[1])/d,(q[0]-p[0])/d,0))
            den=1+sum(dirs[0][k]*dirs[1][k] for k in range(3))
            return tuple((dirs[0][k]+dirs[1][k])/den for k in range(3)) if den>.1 else normal
        na,nb=joint_normal(i),joint_normal(i+1)
        def shifted(p,offset=0,z=0):
            n=na if p is a else nb if p is b else normal
            return [p[k]+offset*n[k]+(z if k==2 else 0) for k in range(3)]
        def add(s,p,q,w,h,kind):out.append(_annotate(beam(key+s,p,q,w,h,kind),r))
        width=r['width_m']
        if r['containment']=='conduit':
            offset=-width/2
            for j,diam in enumerate(r['outer_diameters_m']):
                # Polygonal cylindrical envelope retains nominal outside diameter.
                pa,pb=shifted(a,offset+diam/2),shifted(b,offset+diam/2)
                part=cylinder(key+f'-ELP{j}',pa,pb,diam,'conduit')
                out.append(_annotate(part,r));offset+=diam+.04
            continue
        if not detail:
            add('-BODY',shifted(a,z=.05),shifted(b,z=.05),width,.1,'tray_cover' if covers else 'tray')
            continue
        for side in [-1,1]:
            add(f'-SIDE{side}',shifted(a,side*(width/2-.001),.05),shifted(b,side*(width/2-.001),.05),.002,.1,'tray')
        # 200mm rung pitch and 40x16 outer rung section from p.38; solid outer envelope.
        n=max(1,math.ceil(length/.2))
        for j in range(n):
            p=[a[k]+(b[k]-a[k])*(j+.5)/n for k in range(3)]
            add(f'-RUNG{j}',shifted(p,-width/2,.008),shifted(p,width/2,.008),.04,.016,'tray')
        offset=-width/2
        for j,(kind,w) in enumerate(r['compartments']):
            if cables:add(f'-PATH{j}',shifted(a,offset+w/2,.034),shifted(b,offset+w/2,.034),.018,.018,'cable_'+kind)
            offset+=w
            if j<len(r['compartments'])-1:add(f'-DIVIDER{j}',shifted(a,offset,.04),shifted(b,offset,.04),.002,.08,'tray')
        if covers:
            ww=(width+.007)/2
            verts=[]
            for z in [.1,.1016]:verts.extend([shifted(a,-ww,z),shifted(b,-ww,z),shifted(b,ww,z),shifted(a,ww,z)])
            out.append(_annotate(dict(id=key+'-COVER',kind='tray_cover',vertices=verts,faces=FACES),r))
        # Typical support form p.28/30/31/37; station spacing is a visualization assumption.
        for j in range(max(1,math.ceil(length/1.5))):
            t=(j+.5)/max(1,math.ceil(length/1.5));p=[a[k]+(b[k]-a[k])*t for k in range(3)]
            add(f'-SUPPORT{j}',shifted(p,-width/2-.025,-.021),shifted(p,width/2+.025,-.021),.042,.042,'tray_support')
            if a[2]>3:
                for s in [-1,1]:
                    q=shifted(p,s*(width/2+.025),-.042)
                    add(f'-HANGER{j}-{s}',q,[q[0],q[1],4.4],.012,.012,'tray_support')
            elif r['area'] in 'ABCDE':
                q=shifted(p,z=-.042);add(f'-STAKE{j}',[q[0],q[1],-.3],q,.042,.042,'tray_support')
    return out

def cylinder(key,a,b,diameter,kind):
    axis=[b[k]-a[k] for k in range(3)];norm=math.sqrt(sum(x*x for x in axis));axis=[x/norm for x in axis]
    ref=(0,0,1) if abs(axis[2])<.9 else (0,1,0)
    u=[axis[1]*ref[2]-axis[2]*ref[1],axis[2]*ref[0]-axis[0]*ref[2],axis[0]*ref[1]-axis[1]*ref[0]]
    norm=math.sqrt(sum(x*x for x in u));u=[x/norm for x in u]
    v=[axis[1]*u[2]-axis[2]*u[1],axis[2]*u[0]-axis[0]*u[2],axis[0]*u[1]-axis[1]*u[0]]
    n=8;vertices=[tuple(p[k]+diameter/2*(math.cos(j*2*math.pi/n)*u[k]+math.sin(j*2*math.pi/n)*v[k]) for k in range(3)) for p in (a,b) for j in range(n)]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return dict(id=key,kind=kind,vertices=vertices,faces=faces)

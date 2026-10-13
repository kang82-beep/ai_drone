"""Drawing netlist and reviewed module-region assignment, separate from cable routing."""
from .site_structures import buildings,building_parts,box,beam,COLORS,raised_modules
from .drawing_model import SPEC

GROUP_COLORS=dict(zip('ABCDE',['#e6ab48','#57b8dc','#8eca76','#db83b1','#a797e1']))
COLORS.update({'circuit_'+k:v for k,v in GROUP_COLORS.items()})


def region_spans(data):
    rows=data['rows'];out={f'JB-{g}{i}{j}':[] for g in 'ABCDE' for i in range(1,5) for j in range(1,4)}
    def put(jb,a,b=None,half=None):
        for n in range(a,(b or a)+1):
            r=rows[n-1];c=r['columns'];lo,hi=(0,40) if half=='W' else (40,80) if half=='E' else (0,c)
            if hi>c:raise ValueError((jb,n,c,half))
            out['JB-'+jb].append({'strip':r['id'],'column_start':lo,'column_end':hi})
    put('A42',1,2);put('A42',37,38,'W');put('A43',35,36);put('A43',37,38,'E');put('A41',3,4)
    for jb,a,b,h in [('A13',5,8,'W'),('A12',5,8,'E'),('A11',9,12,None),('A23',39,42,'W'),('A33',39,42,'E'),('A22',43,46,'W'),('A32',43,46,'E'),('A21',47,51,'W'),('A31',47,51,'E')]:put(jb,a,b,h)
    for jb,a,b in [('B11',13,16),('B12',17,20),('B13',21,25),('B41',26,28),('B42',29,34)]:put(jb,a,b)
    put('B41',66,67,'W');put('B43',65);put('B43',66,67,'E')
    for i,(a,b) in enumerate([(52,55),(56,59),(60,64)],1):put(f'B2{i}',a,b,'W');put(f'B3{i}',a,b,'E')
    for i,(a,b) in enumerate([(68,72),(73,76),(77,80)],1):put(f'C4{i}',a,b,'W');put(f'C3{i}',a,b,'E')
    put('C23',81);put('C23',130,131);put('C11',119,120);put('C11',121,121,'E');put('C21',121,125,'W');put('C12',122,125,'E');put('C22',126,129,'W');put('C13',126,129,'E')
    for i,a,b in [(3,97,100),(2,101,104),(1,105,109)]:put(f'D4{i}',a,b,'W');put(f'D3{i}',a,b,'E')
    put('D22',110);put('D13',111,113);put('D13',114,114,'E');put('D11',114,118,'W');put('D12',115,118,'E');put('D23',145,148);put('D22',149,151);put('D21',152,156)
    put('E41',82,83)
    for i,a,b in [(3,84,87),(2,88,91),(1,92,96)]:put(f'E1{i}',a,b,'W');put(f'E2{i}',a,b,'E')
    put('E43',132,133);put('E43',134,135,'E');put('E42',134,135,'W');put('E42',136);put('E32',137,140,'W');put('E33',137,140,'E');put('E31',141,144)
    return out


def build_network(data):
    spans=region_spans(data);rows={r['id']:r for r in data['rows']};nodes={};edges=[]
    def node(key,kind,pos,**kw):nodes[key]={'id':key,'type':kind,'position':list(pos),**kw}
    def edge(a,b,kind,source):edges.append({'id':a+'__'+b,'from':a,'to':b,'type':kind,'source':source,'geometry_status':'logical visualization; not surveyed cable path'})
    for b in buildings(data):
        for p in building_parts(b):
            if p['kind'] in ('equipment','inverter'):
                pos=[sum(v[i] for v in p['vertices'])/len(p['vertices']) for i in range(3)]
                node(p['id'],'cabinet',pos,mesh_id=p['id'],source=p['source'])
        node(b['id']+'-BUS','bus',(b['x']+3,b['y']+3,3),voltage_kV=22.9,source='PDF p.4–5; bus position symbolic')
    for g in 'ABCDE':
        room='ER-01' if g in 'AB' else 'ER-02';base=nodes[f'{room}-INV-{g}0']['position']
        node('INV-'+g,'inverter_group',base,room=room,rating_kW=1000,source='PDF p.4–5,12; five cabinets per group are not five 1MW inverters')
        for i in range(1,5):edge(f'{room}-INV-{g}{i}','INV-'+g,'dc_input','PDF p.12 / cabinet binding p.6–7')
        chain=['INV-'+g,f'{room}-LV-{g}',f'{room}-TR-{g}',f'{room}-VCB-'+str({'A':2,'B':3,'C':6,'D':7,'E':8}[g]),room+'-BUS']
        for a,b in zip(chain,chain[1:]):edge(a,b,'ac_generation','PDF p.4–5')
    for key,ss in spans.items():
        g=key[3];branch=int(key[4]);inp={1:2,2:3,3:1,4:4}[branch] if g=='D' else branch
        count=sum(2*(s['column_end']-s['column_start']) for s in ss)
        # Region-edge anchor near its southernmost member. Exact installation coordinates unknown.
        s=max(ss,key=lambda s:rows[s['strip']]['y']);r=rows[s['strip']];col=s['column_end']
        x=r['x']+col/10*(SPEC.group_width+SPEC.group_gap)-.7;y=r['y']+.4
        room='ER-01' if g in 'AB' else 'ER-02'
        node(key,'junction_box',(x,y,.85),group=g,input=inp,room=room,series_modules=20,parallel_strings=count//20,module_count=count,power_kWp=round(count*.245,3),spans=ss,source=f'PDF p.12, p.{22+ord(g)-65}; region interpretation',position_status='inferred region-edge anchor; photo IMG_5914 confirms JB-B13 appearance')
        edge(key,f'{room}-INV-{g}{inp}','pv_dc','PDF p.12')
    node('GRID','grid',(0,135,8),source='PDF p.4; symbolic endpoint, not surveyed pole position')
    for a,b in [('ER-02-BUS','ER-02-VCB-5'),('ER-02-VCB-5','ER-01-VCB-4'),('ER-01-VCB-4','ER-01-BUS'),('ER-01-BUS','ER-01-VCB-1'),('ER-01-VCB-1','ER-01-MOF-1'),('ER-01-MOF-1','ER-01-LBS-1'),('ER-01-LBS-1','GRID')]:edge(a,b,'ac_generation','PDF p.4–5')
    edge('ER-01-BUS','ER-01-PT-1','metering_branch','PDF p.4; shunt branch, not power series')
    edge('ER-01-BUS','ER-01-TR-1','auxiliary_ac','PDF p.4')
    edge('ER-01-TR-1','ER-01-MCCB-1','auxiliary_ac','PDF p.4')
    edge('ER-01-MCCB-1','ER-02-MCCB-2','auxiliary_ac','PDF p.4–5')
    for g in 'ABCDE':
        room='ER-01' if g in 'AB' else 'ER-02';jb=nodes[f'JB-{g}11'];x,y,z=jb['position']
        node('P-'+g,'auxiliary_distribution',(x-1,y,.7),source='PDF p.13: 600x300x600mm cabinet; site position assumed')
        edge(room+'-MCCB-'+('1' if room=='ER-01' else '2'),'P-'+g,'auxiliary_ac','PDF p.13')
        for key in spans:
            if key[3]==g:edge('P-'+g,key,'auxiliary_ac','PDF p.13 load schedule; logical supply relation, daisy-chain geometry not modeled')
    return {'nodes':list(nodes.values()),'edges':edges,'notes':['Generation and auxiliary AC are separate edge types.','PDF p.13 C/E auxiliary blocks contain D41–D43 labels; corresponding C/E load schedules used, discrepancy retained here.','Module-region ownership is a reviewed interpretation of p.22–26, not surveyed string wiring.','JB and power-box locations are inferred; logical edges are not cable lengths, bend paths or conductor schedules.']}


def field_parts(network):
    out=[]
    for n in network['nodes']:
        if n['type'] not in ('junction_box','auxiliary_distribution'):continue
        x,y,z=n['position'];key=n['id'];jb=n['type']=='junction_box';w,d,h=(.75,.3,1.05) if jb else (.6,.3,.6)
        source='IMG_5914 cabinet/window/canopy appearance; JB dimensions assumed' if jb else n['source']
        out.append(box(key,x-w/2,y-d/2,z-h/2,w,d,h,'junction',source))
        out.append(box(key+'-HOOD',x-w/2-.03,y-d/2-.03,z+h/2,w+.06,d+.06,.045,'frame',source))
        out.append(box(key+'-WINDOW',x-w*.22,y+d/2+.01,z,.44*w,.01,.27,'glass',source))
        for i,dx in enumerate([-.25,.25]):out.append(box(key+f'-LEG-{i}',x+dx-.025,y-.025,.15,.05,.05,max(.05,z-h/2-.15),'steel',source))
    return out


def circuit_parts(data,network,group='A'):
    nodes={n['id']:n for n in network['nodes']};parts=[];selected={n['id'] for n in nodes.values() if n.get('group')==group}
    # Follow only generation edges towards the grid.
    seen=set(selected);changed=True
    while changed:
        changed=False
        for e in network['edges']:
            if e['type'] in ('pv_dc','dc_input','ac_generation') and e['from'] in seen and e['to'] not in seen:seen.add(e['to']);changed=True
    rows={r['id']:r for r in data['rows']}
    for key in selected:
        for s in nodes[key]['spans']:
            r=rows[s['strip']]
            for i,m in enumerate(raised_modules(r)):
                if s['column_start']<=i%r['columns']<s['column_end']:parts.append(dict(m,kind='circuit_'+group))
    parts.extend(p for p in field_parts(network) if p['id'].split('-')[1].startswith(group))
    for b in buildings(data):parts.extend(p for p in building_parts(b) if p['id'] in seen)
    for e in network['edges']:
        if e['from'] not in seen or e['to'] not in seen or e['type'] not in ('pv_dc','dc_input','ac_generation'):continue
        a=nodes[e['from']]['position'];b=nodes[e['to']]['position']
        if sum((a[i]-b[i])**2 for i in range(3))<1e-10:continue
        p=beam('NET-'+e['id'],a,b,.08,.08,'circuit_'+group);p['source']=e['source']+'; logical connection, not installed cable geometry';parts.append(p)
    return parts

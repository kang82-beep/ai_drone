"""Export full structures and review images without changing the original module-only model."""
import json
from collections import Counter
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from pv_inspector.site_model import load_site,strip_outline
from pv_inspector.site_structures import *
from pv_inspector.desktop import project
from pv_inspector.mesh_render import rasterize
from pv_inspector.cable_routes import all_routes,route_parts
from pv_inspector.circuit_model import build_network,field_parts,circuit_parts

OUT=Path(__file__).resolve().parent/'results'/'drawing_site'

def render(parts,path,title,subtitle,yaw=-.35,elevation=.65):
    projected=[]
    for part in parts:
        pp=[project(p,yaw,elevation) for p in part['vertices']]
        for face in part['faces']:
            pts=[pp[i] for i in face]
            projected.append((sum(p[2] for p in pts)/len(pts),pts,COLORS[part['kind']]))
    xs=[p[0] for _,pts,_ in projected for p in pts];ys=[p[1] for _,pts,_ in projected for p in pts]
    scale=min(1460/(max(xs)-min(xs)),790/(max(ys)-min(ys)))
    cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
    # Convert projected centre back into the ground plane for the shared depth renderer.
    import math
    b=cy/math.sin(elevation)
    world_x=cx*math.cos(yaw)+b*math.sin(yaw);world_y=-cx*math.sin(yaw)+b*math.cos(yaw)
    im,_=rasterize(parts,1600,1050,yaw,elevation,scale,world_x,world_y,screen_y=570)
    draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',30);small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',19)
    def screen(v):
        xx,yy,_=project((v[0]-world_x,v[1]-world_y,v[2]),yaw,elevation)
        return (800+xx*scale,570+yy*scale)
    for p in parts:
        if p['id'].startswith('NET-'):
            vv=p['vertices'];ends=[tuple(sum(v[k] for v in chunk)/4 for k in range(3)) for chunk in (vv[:4],vv[4:])]
            draw.line([screen(v) for v in ends],fill=COLORS[p['kind']],width=2)
        elif p['kind']=='junction' and p['id'].startswith('JB-') and any(q['id'].startswith('NET-') for q in parts):
            v=tuple(sum(v[k] for v in p['vertices'])/8 for k in range(3))
            draw.text(screen(v),p['id'],font=small,fill='white',stroke_width=2,stroke_fill='#101d2b')
    draw.text((48,32),title,font=font,fill='white');draw.text((48,87),subtitle,font=small,fill='#adc2cf')
    draw.text((48,1000),'도면 기반 형상 + 명시적 가정값 · 로컬 좌표(m) · 검사 결과 미연결',font=small,fill='#adc2cf')
    im.save(path)

def main():
    data=load_site();bs=buildings(data);counts=Counter();index=1
    routes=all_routes(data)
    network=build_network(data)
    (OUT/'electrical_network.json').write_text(json.dumps(network,ensure_ascii=False,indent=2),encoding='utf-8')
    cable_meshes=[p for r in routes for p in route_parts(r)]
    with (OUT/'plant_complete.obj').open('w',encoding='utf-8') as f:
        f.write('# Units m; ground z=0; see complete_model.json for provenance and assumptions\nmtllib plant_complete.mtl\n')
        def write(parts):
            nonlocal index
            for p in parts:
                counts[p['kind']]+=1
                f.write(f"o {p['id']}\nusemtl {p['kind']}\n")
                for x,y,z in p['vertices']:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
                for face in p['faces']:f.write('f '+' '.join(str(index+j) for j in face)+'\n')
                index+=len(p['vertices'])
        for r in data['rows']:
            modules=raised_modules(r);write(modules);write(module_frames(modules));write(supports(r))
        for b in bs:write(building_parts(b))
        write(cable_meshes)
        write(field_parts(network))
    with (OUT/'plant_complete.mtl').open('w',encoding='ascii') as f:
        for kind,color in COLORS.items():
            rgb=[int(color[i:i+2],16)/255 for i in [1,3,5]]
            f.write(f'newmtl {kind}\nKd '+ ' '.join(f'{v:.4f}' for v in rgb)+'\nKa 0.15 0.15 0.15\n\n')
    manifest={'units':'m','ground_datum':'flat assumed ground z=0','assumptions':ASSUMPTIONS,'buildings':bs,'object_counts':dict(counts),'module_geometry':'p.10–11','layout':'p.14, scan approximate','building_geometry':'p.6/7 equipment plans; p.61 section','cable_routes':'cable_routes.json; p.27–41; inferred connectors explicitly marked','pending':['Surveyed terrain and coordinates','Structural engineering dimensions for racks/foundations','As-built cable bends, individual circuit mapping and conductor sizes'],'legacy_obj':'plant_modules.obj retains old low-edge datum; do not overlay without +0.9m Z transform'}
    (OUT/'complete_model.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest['electrical_network']='electrical_network.json: 60 JBs, 20 DC input sections, five inverter groups; generation and auxiliary AC separated'
    manifest['pending']=['Surveyed terrain and coordinates','Verified rack/foundation dimensions and subsurface design','As-built cable bends and conductor sizes','Surveyed JB/power-box positions and individual string routing']
    manifest['photos']={'files':[f'IMG_{i}.JPG' for i in range(5909,5944)],'appearance':'photo-informed geometry, not photogrammetry','details':'concrete apron, anchor caps, grey cladding, blue roof trim, roof ventilators, windows, green floor, aisle markings, inverter orange bands, cabinet vents and handles, JB envelope'}
    (OUT/'complete_model.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for g in 'ABCDE':
        parts=circuit_parts(data,network,g)
        render(parts,OUT/f'circuit_{g}.png',f'인버터 {g} · 접속함에서 계통까지','색상 선 = 논리 회로 연결 / 실제 포설 경로 아님 · 접속함 위치 추정',elevation=1.2)
        with (OUT/f'circuit_{g}.obj').open('w',encoding='utf-8') as f:
            f.write('# Logical circuit visualization, NOT physical cable geometry\nmtllib plant_complete.mtl\n');idx=1
            for p in parts:
                f.write(f"o {p['id']}\nusemtl {p['kind']}\n")
                for x,y,z in p['vertices']:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
                for face in p['faces']:f.write('f '+' '.join(str(idx+j) for j in face)+'\n')
                idx+=len(p['vertices'])
    for r in routes:r['model_length_m']=sum(math.dist(a,b) for a,b in zip(r['points'],r['points'][1:]))
    route_data={'units':'m','routes':routes,'source_pdf':'3d/신안군 태양광 발전단지 2차 (5MW) 조성공사.pdf',
                'notes':['Centreline lengths are model geometry, not procurement cable lengths.',
                         'S/L/D/H cable solids are representative paths, not conductor counts or actual cable diameters.',
                         'Indoor low trays use bottom GL+0.25m; overhead GL+3.1m. FL is GL+0.5m.',
                         'Outdoor tray bottom GL+0.142m interpreted from p.37 support detail.',
                         'ELP OD and burial centre from p.41; buried connectors and riser positions are inferred.',
                         'Regional XY paths are aligned to existing p.14 row stations; not exact CAD digitization.',
                         'Supports at <=1.5m are illustrative; not an engineered support schedule.']}
    (OUT/'cable_routes.json').write_text(json.dumps(route_data,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'cable_routes.obj').open('w',encoding='utf-8') as f:
        f.write('# Cable containment only, same coordinates as plant_complete.obj\nmtllib plant_complete.mtl\n');idx=1
        for p in cable_meshes:
            f.write(f"o {p['id']}\nusemtl {p['kind']}\n")
            for x,y,z in p['vertices']:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
            for face in p['faces']:f.write('f '+' '.join(str(idx+j) for j in face)+'\n')
            idx+=len(p['vertices'])
    overview=[]
    for r in data['rows']:overview.append({'id':r['id'],'kind':'module','vertices':[(x,y,z+.9) for x,y,z in strip_outline(r)],'faces':[(0,1,2,3)]})
    for b in bs:overview.extend(building_parts(b))
    overview.extend(field_parts(network))
    render(overview,OUT/'site_complete_preview.png','신안 2차 · 발전소 전체','156개 배열 / 20,420개 모듈 / 전기실 2동',elevation=.95)
    export_cable_previews(data,routes,bs)
    r=dict(data['rows'][0]);r.update(groups=1,columns=10,width=SPEC.group_width)
    mm=raised_modules(r)
    render(mm+list(module_frames(mm))+supports(r),OUT/'structure_detail.png','모듈 · 프레임 · 지지대 · 기초','모듈 치수·22° 경사는 도면 / 저단 0.9m·부재 단면·기초는 시각화 가정',yaw=-.3,elevation=.24)
    render(supports(r),OUT/'structure_uncovered.png','하부 지지구조 · 패널 숨김','레일·경사보·기둥·가새·베이스플레이트·기초 / 매립부 확인을 위해 지면 생략',yaw=-.3,elevation=.35)
    for b in bs:
        parts=building_parts(b)
        render(parts,OUT/f'{b["id"]}_exterior.png',b['label']+' · 외관','바닥 GL+0.5m / 처마 FL+4.0m / 용마루 FL+5.5m',yaw=2.7)
        render([p for p in parts if p['kind'] not in SHELL_KINDS],OUT/f'{b["id"]}_interior.png',b['label']+' · 내부 설비','인버터·변압기·배전반: 도면의 설비 명칭과 외형 치수 적용',yaw=-.45)
    parts=building_parts(bs[1])
    render([p for p in parts if '-INV-C' in p['id']],OUT/'photo_inverter_detail.png','사진 반영 · 인버터 C 캐비닛','IMG_5939–5940 · 흰색 외함 / 주황 띠 / 손잡이 / 통풍구 · 세부 치수 추정',yaw=2.7,elevation=.4)
    render([p for p in field_parts(network) if p['id'].startswith('JB-B13')],OUT/'photo_junction_detail.png','사진 반영 · JB-B13 접속함','IMG_5914 · 창 / 상부 덮개 / 다리 · 외형 치수 및 배치 위치 추정',yaw=-.45,elevation=.4)
    print(json.dumps(dict(counts)))


def export_cable_previews(data,routes,bs):
    # A plan overlay makes 50mm compartments readable across a 344m site without changing mesh dimensions.
    im=Image.new('RGB',(1600,1500),'#101d2b');draw=ImageDraw.Draw(im)
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',30);small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
    sx=3.95;ox=90;oy=190
    def point(p):return (ox+p[0]*sx,oy+p[1]*sx)
    for row in data['rows']:
        draw.polygon([point(p) for p in strip_outline(row)],fill='#244150')
    for b in bs:
        w,d=(b['depth'],b['length']) if b['rotated'] else (b['length'],b['depth'])
        draw.rectangle([point((b['x'],b['y'])),point((b['x']+w,b['y']+d))],fill='#787b76')
        draw.text(point((b['x'],b['y']-5)),b['id'],font=small,fill='white')
    for r in routes:
        if r['area'].startswith('ER-') and r['containment']=='tray':continue
        color='#7dbb8b' if r['containment']=='conduit' else '#e5bc62'
        pp=[point(p) for p in r['points']]
        if r['containment']=='conduit':
            for a,b in zip(pp,pp[1:]):
                length=math.dist(a,b)
                for j in range(0,int(length),10):
                    draw.line([tuple(a[k]+(b[k]-a[k])*j/max(length,1) for k in range(2)),tuple(a[k]+(b[k]-a[k])*min(j+5,length)/max(length,1) for k in range(2))],fill=color,width=2)
        else:draw.line(pp,fill=color,width=3)
    for area,x,y in [('A',110,75),('B',113,185),('C',128,270),('D',225,147),('E',295,26)]:
        draw.text(point((x,y)),area,font=font,fill='#fff0bd',stroke_width=1)
    draw.text((70,35),'케이블 트레이 · 발전소 전체 경로',font=font,fill='white')
    draw.text((70,90),'금색 실선: 도면 주 경로 / 초록 점선: 추정 지중 연결 / 경로 선 두께는 가독성을 위해 강조',font=small,fill='#adc2cf')
    draw.text((70,1420),'PDF p.27–41 · A~E 배선 구역 · 정확한 회로별 연결/전선 수량은 미확정',font=small,fill='#adc2cf')
    im.save(OUT/'cable_routes_preview.png')
    for b in bs:
        rr=[r for r in routes if r['area']==b['id'] and r['containment']=='tray']
        for level,subset in [('floor',[r for r in rr if r['elevation_basis']=='FL-250']),('overhead',[r for r in rr if r['elevation_basis']=='FL+2600'])]:
            parts=[p for r in subset for p in route_parts(r,covers=False)]
            render(parts,OUT/f'{b["id"]}_cable_{level}.png',b['label']+' · '+('바닥 아래 트레이' if level=='floor' else '상부 트레이'),
                   '덮개·건물 생략 / FL-250mm' if level=='floor' else '덮개·건물 생략 / FL+2600mm',yaw=-math.pi/2 if b['rotated'] else 0,elevation=1.3)
    sample=dict(routes[0],points=[[0,0,.142],[1.2,0,.142]])
    render(route_parts(sample,covers=False),OUT/'tray_detail.png','야외 트레이 · 상세','높이 100mm / 가로대 200mm 간격 / 색상 선은 대표 배선 경로',yaw=-.45,elevation=1.25)

if __name__=='__main__':main()

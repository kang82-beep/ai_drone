"""Full drawing-based site with strip-level overview and individual-module detail."""
import math
import tkinter as tk
from tkinter import ttk, messagebox
from .site_model import load_site,strip_modules,strip_outline
from .desktop import project
from .site_structures import buildings,building_parts,raised_modules,supports,module_frames,COLORS,ASSUMPTIONS,SHELL_KINDS
from .mesh_render import rasterize
from PIL import ImageTk
from .cable_routes import all_routes,route_parts,CABLE_KINDS
from .circuit_model import build_network,field_parts,circuit_parts


class SiteWindow:
    def __init__(self,parent):
        self.analysis_links = None
        self.data=load_site();self.rows=self.data['rows']
        self.by_id={r['id']:r for r in self.rows}
        self.buildings={b['id']:b for b in buildings(self.data)}
        self.structure_visible=tk.BooleanVar(value=True)
        self.shell_visible=tk.BooleanVar(value=True)
        self.panels_visible=tk.BooleanVar(value=True)
        self.parts=[]
        self.routes=all_routes(self.data);self.route_by_id={r['id']:r for r in self.routes}
        self.network=build_network(self.data);self.field_parts=field_parts(self.network)
        self.cable_visible=tk.BooleanVar(value=True);self.cover_visible=tk.BooleanVar(value=True)
        self.cable_only=tk.BooleanVar(value=False)
        self.group=tk.StringVar(value='전체 배열')
        self.window=tk.Toplevel(parent);self.window.title('신안 2차 · 도면 기반 발전소 전체 3D')
        self.window.geometry('1400x900');self.window.minsize(950,650)
        self.focus=None;self.selected=None;self.zoom=1;self.yaw=-.22;self.elevation=.9
        self.items={};self.anchor=None;self.detail_modules=[]
        bar=ttk.Frame(self.window,padding=12);bar.pack(fill='x')
        ttk.Label(bar,text='SHINAN / 도면 기반 발전소',font=('맑은 고딕',18,'bold')).pack(side='left')
        for label,fn in [('전체',self.reset),('평면',self.top),('확대',lambda:self.scale(1.3)),('축소',lambda:self.scale(1/1.3))]:
            ttk.Button(bar,text=label,command=fn).pack(side='left',padx=4)
        self.status=tk.StringVar(value=f"{len(self.rows)}개 배열 구간 · 도면 추출 {self.data['module_count']:,}모듈 · 치수 기반 형상 / 위치 정합 검토 중")
        ttk.Label(self.window,textvariable=self.status,padding=10).pack(fill='x')
        ttk.Checkbutton(bar,text='프레임·기초',variable=self.structure_visible,command=self.draw).pack(side='left',padx=5)
        ttk.Checkbutton(bar,text='패널',variable=self.panels_visible,command=self.draw).pack(side='left',padx=5)
        ttk.Checkbutton(bar,text='건물 외피',variable=self.shell_visible,command=self.draw).pack(side='left',padx=5)
        self.group_box=ttk.Combobox(bar,textvariable=self.group,values=['전체 배열'],state='readonly',width=12)
        self.group_box.pack(side='left',padx=4);self.group_box.bind('<<ComboboxSelected>>',lambda e:self.open_strip(self.focus,True) if self.focus in self.by_id else None)
        wirebar=ttk.Frame(self.window,padding=(12,0,12,6));wirebar.pack(fill='x')
        ttk.Checkbutton(wirebar,text='트레이·전선관',variable=self.cable_visible,command=self.draw).pack(side='left')
        ttk.Checkbutton(wirebar,text='트레이 덮개',variable=self.cover_visible,command=self.draw).pack(side='left',padx=8)
        ttk.Checkbutton(wirebar,text='배선만 표시',variable=self.cable_only,command=self.draw).pack(side='left',padx=8)
        ttk.Button(wirebar,text='배선 전체',command=lambda:self.open_wiring('wire:all')).pack(side='left',padx=8)
        ttk.Label(wirebar,text='금색: 트레이 / 초록 점선: 추정 전선관 연결 · 전체 보기의 경로 선은 두께 강조').pack(side='left',padx=8)
        pane=ttk.Panedwindow(self.window,orient='horizontal');pane.pack(fill='both',expand=True,padx=12)
        left=ttk.Frame(pane);pane.add(left,weight=1)
        ttk.Label(left,text='배열 선택: 모듈 상세로 이동').pack()
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse');self.tree.pack(fill='both',expand=True)
        self.tree.insert('','end',iid='site',text='전체 발전소',open=True)
        self.tree.insert('site','end',iid='wire:all',text='케이블 트레이 · 배선 경로',open=False)
        for area in ['A','B','C','D','E','ER-01','ER-02']:
            self.tree.insert('wire:all','end',iid='wire:'+area,text=area+' · 배선')
            for r in self.routes:
                if r['area']==area:self.tree.insert('wire:'+area,'end',iid='route:'+r['id'],text=r['drawing_tag'])
        self.tree.insert('site','end',iid='buildings',text='전기실 · 내부 설비',open=True)
        self.tree.insert('site','end',iid='circuits',text='회로 연결 · 인버터 A~E',open=True)
        for g in 'ABCDE':
            count=sum(n.get('module_count',0) for n in self.network['nodes'] if n.get('group')==g)
            self.tree.insert('circuits','end',iid='circuit:'+g,text=f'{g} · {count:,}장 · {count*.245:.1f}kWp')
        for b in self.buildings.values():self.tree.insert('buildings','end',iid=b['id'],text=b['label'])
        for lane in range(1,5):self.tree.insert('site','end',iid=f'lane{lane}',text=f'공간 구획 L{lane} · 인버터 구분 아님',open=True)
        for r in self.rows:self.tree.insert(f"lane{r['lane']}",'end',iid=r['id'],text=f"{r['id']} · {r['columns']*2}장")
        self.tree.bind('<<TreeviewSelect>>',self.tree_select)
        main=ttk.Frame(pane);pane.add(main,weight=4)
        self.canvas=tk.Canvas(main,bg='#101d2b',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<ButtonPress-1>',self.press);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<MouseWheel>',lambda e:self.scale(1.15 if e.delta>0 else 1/1.15))
        self.info=tk.StringVar(value='전체 화면에서는 배열 단위로 표시합니다.\n배열을 클릭하면 실제 치수의 모듈을 개별 선택할 수 있습니다.')
        from .module_links import load_index
        try:
            self.analysis_links = load_index()
        except (OSError, ValueError) as exc:
            self.info.set('3D 분석 연결을 불러오지 못했습니다: ' + str(exc))
        ttk.Button(self.window, text='선택 모듈 분석 결과', command=self.show_analysis).pack(anchor='w', padx=12)
        ttk.Button(self.window, text='연결 모듈 목록 / ID 검색', command=self.list_analysis).pack(anchor='w', padx=12)
        ttk.Label(self.window,textvariable=self.info,padding=10).pack(fill='x')
        ttk.Label(self.window,text='도면: 모듈·전기실 치수·설비 외형 | 가정: 패널 저단 0.9m·지지대·기초·평탄 지면 | 로컬 좌표·검사 미연결',padding=8).pack(fill='x')

    def reset(self):
        self.focus=None;self.selected=None;self.zoom=1;self.yaw=-.22;self.elevation=.9;self.draw()

    def top(self):self.yaw=0;self.elevation=math.pi/2;self.draw()
    def scale(self,f):self.zoom=max(.3,min(10,self.zoom*f));self.draw()
    def press(self,e):self.anchor=(e.x,e.y);self.last=(e.x,e.y)
    def drag(self,e):
        if self.anchor:
            self.yaw+=(e.x-self.last[0])*.008;self.elevation=max(.08,min(math.pi/2,self.elevation+(e.y-self.last[1])*.006));self.last=(e.x,e.y);self.draw()
    def release(self,e):
        if self.anchor and math.hypot(e.x-self.anchor[0],e.y-self.anchor[1])<5:
            key=None
            for item in reversed(self.canvas.find_overlapping(e.x-3,e.y-3,e.x+3,e.y+3)):
                if item in self.items:key=self.items[item];break
            if key is None and hasattr(self,'pick_map') and 0<=e.y<self.pick_map.shape[0] and 0<=e.x<self.pick_map.shape[1]:
                index=int(self.pick_map[e.y,e.x])
                if index>=0:key=self.render_parts[index]['id']
            if key and key.startswith('route:'):self.open_wiring(key)
            elif key in self.by_id:self.tree.selection_set(key);self.tree.see(key);self.open_strip(key)
            elif key in self.buildings:self.tree.selection_set(key);self.open_building(key)
            elif key:
                self.selected=key
                part=next((p for p in self.parts if p['id']==key),{})
                if part.get('route_id'):self.info.set(self.route_info(self.route_by_id[part['route_id']]))
                else:
                    count = len((self.analysis_links or {}).get('modules', {}).get(key, {}).get('records', []))
                    self.info.set(f"{key} | {part.get('kind','module')} | 연결 관측 {count}건 · 선택 모듈 분석 결과 버튼으로 확인 (후보 포함)")
                self.draw()
        self.anchor=None

    def tree_select(self,e=None):
        keys=self.tree.selection()
        if not keys:return
        if keys[0].startswith(('wire:','route:')):self.open_wiring(keys[0])
        elif keys[0].startswith('circuit:'):self.open_circuit(keys[0][-1])
        elif keys[0] in self.by_id:self.open_strip(keys[0])
        elif keys[0] in self.buildings:self.open_building(keys[0])
        else:self.reset()

    def show_analysis(self):
        from .module_links import load_index
        from .module_links_ui import show_module_results
        try:
            self.analysis_links = load_index()
            if self.selected not in self.analysis_links['modules']:
                messagebox.showinfo('모듈 선택', '배열을 연 뒤 개별 모듈을 클릭하세요.', parent=self.window); return
            show_module_results(self.window, self.analysis_links, self.selected)
        except (OSError, ValueError) as exc:
            messagebox.showerror('연결 자료 확인', str(exc), parent=self.window)

    def list_analysis(self):
        from .module_links import load_index
        try:
            self.analysis_links = load_index()
        except (OSError, ValueError) as exc:
            messagebox.showerror('연결 자료 확인', str(exc), parent=self.window); return
        win=tk.Toplevel(self.window);win.title('분석 연결 모듈 검색');win.geometry('620x520')
        query=tk.StringVar()
        ttk.Label(win,text='기존 A구역 후보 포함 · 모듈 ID 검색',padding=10).pack()
        ttk.Entry(win,textvariable=query).pack(fill='x',padx=12)
        tree=ttk.Treeview(win,columns=('count',),show='tree headings',selectmode='browse')
        tree.heading('#0',text='도면 모듈 ID');tree.heading('count',text='연결 관측 수')
        tree.pack(fill='both',expand=True,padx=12,pady=10)
        def refresh(*_):
            tree.delete(*tree.get_children())
            for mid,module in self.analysis_links['modules'].items():
                if module['records'] and query.get().lower() in mid.lower():
                    tree.insert('','end',iid=mid,text=mid,values=(len(module['records']),))
        def select():
            selected=tree.selection()
            if not selected:return
            mid=selected[0];strip=mid.rsplit('-R',1)[0]
            if strip in self.by_id:
                self.open_strip(strip);self.selected=mid;self.draw()
                self.info.set(mid+' · 연결 후보 포함 · 선택 모듈 분석 결과로 확인')
            win.destroy();self.show_analysis()
        query.trace_add('write',refresh);refresh()
        ttk.Button(win,text='선택 모듈로 이동 / 결과 확인',command=select).pack(pady=10)

    def open_strip(self,key,keep_group=False):
        self.focus=key;self.selected=None;self.zoom=1;self.yaw=-.18;self.elevation=.7
        r=self.by_id[key]
        if not keep_group:self.group.set('전체 배열')
        self.group_box['values']=['전체 배열']+[f'묶음 {i+1}' for i in range(r['groups'])]
        self.view_strip=dict(r)
        if self.group.get()!='전체 배열':
            from .drawing_model import SPEC
            g=int(self.group.get().split()[-1])-1
            self.view_strip.update(x=r['x']+g*(SPEC.group_width+SPEC.group_gap),width=SPEC.group_width,columns=10,groups=1)
        self.detail_modules=raised_modules(r)
        if self.group.get()!='전체 배열':
            self.detail_modules=[m for i,m in enumerate(self.detail_modules) if g*10<=i%r['columns']<(g+1)*10]
        self.parts=self.detail_modules+list(module_frames(self.detail_modules))+supports(self.view_strip)
        for p in self.field_parts:
            if any(r['x']-1<=v[0]<=r['x']+r['width']+1 and r['y']-1<=v[1]<=r['y']+4 for v in p['vertices']):self.parts.append(p)
        # Include only nearby runs; selecting a route in the tree shows its full geometry.
        x0,x1=self.view_strip['x']-1,self.view_strip['x']+self.view_strip['width']+1
        y0,y1=r['y']-1,r['y']+4
        self.local_routes=[rr for rr in self.routes if any(x0<=p[0]<=x1 and y0<=p[1]<=y1 for p in rr['points'])]
        for rr in self.local_routes:self.parts.extend(route_parts(rr))
        self.info.set(f"{key} · {r['columns']*2}모듈 · 폭 {r['width']:.3f}m | p.14 배치 + p.10–11 치수 | 모듈을 클릭하세요")
        self.draw()

    def open_building(self,key):
        self.focus=key;self.selected=None;self.zoom=1;self.yaw=-.45;self.elevation=.7
        self.parts=building_parts(self.buildings[key])
        for rr in self.routes:
            if rr['area']==key and rr['containment']=='tray':self.parts.extend(route_parts(rr))
        self.info.set(f'{self.buildings[key]["label"]} | 건물 외피를 끄면 인버터·변압기·배전반을 볼 수 있습니다. | 치수 p.6/7 · 높이 p.61')
        self.draw()

    def route_info(self,r):
        widths=' / '.join(f'{k} {w*1000:g}mm' for k,w in r['compartments']) if r['containment']=='tray' else 'ELP '+ '/'.join(str(d) for d in r['diameters_mm'])+'mm'
        length=sum(math.dist(a,b) for a,b in zip(r['points'],r['points'][1:]))
        return f"{r['drawing_tag']} | {r['source']} | {widths} | {r['elevation_basis']}\n모델 경로 {length:.1f}m · {r['position_status']} · 케이블 선은 대표 경로이며 회로 수·규격이 아닙니다."

    def open_circuit(self,group):
        self.focus='circuit:'+group;self.selected=None;self.zoom=1;self.yaw=-.15;self.elevation=1.1
        self.cable_only.set(False);self.parts=circuit_parts(self.data,self.network,group)
        self.info.set(f'인버터 {group} | 접속함 12대 → 입력 4구간 → 인버터 → 저압반 → 변압기 → VCB → 계통\n색상 선: 도면상 회로 관계를 잇는 직선 표시 · 실제 포설 경로/전선 길이가 아닙니다. PDF p.4–5,12 · 접속함 위치 추정')
        self.draw()

    def open_wiring(self,key):
        self.focus=key;self.selected=None;self.zoom=1;self.yaw=-.3;self.elevation=.85
        self.cable_visible.set(True)
        if key.startswith('route:'):
            rr=[self.route_by_id[key[6:]]];self.info.set(self.route_info(rr[0]))
        else:
            area=key[5:];rr=[r for r in self.routes if area=='all' or r['area']==area]
            if area.startswith('ER-'):rr=[r for r in rr if r['containment']=='tray']
            self.info.set(f'{area} · {len(rr)}개 경로 | 덮개를 끄면 대표 배선 경로와 트레이 내부를 확인합니다. | 전선관 연결은 추정 포함')
        self.wiring_routes=rr
        self.parts=[p for r in rr for p in route_parts(r,detail=key!='wire:all')]
        self.draw()

    def draw(self):
        self.canvas.delete('all');self.items.clear()
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        if self.focus and self.focus.startswith(('wire:','route:','circuit:')):
            pts=[project(v,self.yaw,self.elevation) for p in self.parts for v in p['vertices']]
            if not pts:return
            lo=[min(p[i] for p in pts) for i in range(2)];hi=[max(p[i] for p in pts) for i in range(2)]
            a=(lo[0]+hi[0])/2;b=(lo[1]+hi[1])/2/max(.08,math.sin(self.elevation))
            cx=a*math.cos(self.yaw)+b*math.sin(self.yaw);cy=-a*math.sin(self.yaw)+b*math.cos(self.yaw)
            scale=min((w-80)/max(2,hi[0]-lo[0]),(h-90)/max(2,hi[1]-lo[1]))*self.zoom
        elif self.focus in self.buildings:
            b=self.buildings[self.focus];dx,dy=(b['depth'],b['length']) if b['rotated'] else (b['length'],b['depth'])
            cx=b['x']+dx/2;cy=b['y']+dy/2;scale=min(w/(max(dx,dy)+8),h/23)*self.zoom
        elif self.focus:
            r=self.view_strip;cx=r['x']+r['width']/2;cy=r['y']+1.55
            scale=min(w/(r['width']+3),h/9)*self.zoom
        else:cx,cy=172.16,146;scale=min(w/405,h/360)*self.zoom
        render_parts=[]
        if self.focus:
            for m in self.parts:
                if m['kind'] in CABLE_KINDS and not self.cable_visible.get():continue
                if m['kind']=='tray_cover' and not self.cover_visible.get():continue
                if m['kind'] not in CABLE_KINDS and self.cable_only.get():continue
                if not self.panels_visible.get() and m['kind'] in ('module','frame'):continue
                if not self.structure_visible.get() and m['kind'] in ('frame','steel','foundation') and self.focus not in self.buildings:continue
                if not self.shell_visible.get() and m['kind'] in SHELL_KINDS:continue
                render_parts.append(m)
        else:
            for r in ([] if self.cable_only.get() else self.rows):
                render_parts.append({'id':r['id'],'kind':'module','vertices':[(x,y,z+.9) for x,y,z in strip_outline(r)],'faces':[(0,1,2,3)]})
            for b in ([] if self.cable_only.get() else self.buildings.values()):
                for part in building_parts(b):
                    if not self.shell_visible.get() and part['kind'] in SHELL_KINDS:continue
                    render_parts.append(dict(part,id=b['id']))
            if self.cable_visible.get():
                for r in self.routes:render_parts.extend(route_parts(r,detail=False,covers=self.cover_visible.get()))
            if not self.cable_only.get():render_parts.extend(self.field_parts)
        self.render_parts=render_parts
        im,self.pick_map=rasterize(render_parts,max(1,w),max(1,h),self.yaw,self.elevation,scale,cx,cy,selected=self.selected)
        self.photo=ImageTk.PhotoImage(im);self.canvas.create_image(0,0,anchor='nw',image=self.photo)
        if self.focus and self.focus.startswith('circuit:'):
            for p in render_parts:
                if not p['id'].startswith('NET-'):continue
                coords=[]
                for chunk in (p['vertices'][:4],p['vertices'][4:]):
                    x,y,z=[sum(v[k] for v in chunk)/4 for k in range(3)]
                    xx,yy,_=project((x-cx,y-cy,z),self.yaw,self.elevation);coords.extend((w/2+xx*scale,h/2+yy*scale))
                item=self.canvas.create_line(coords,fill=COLORS[p['kind']],width=2);self.items[item]=p['id']
        if self.cable_visible.get() and (not self.focus or self.focus=='wire:all'):
            for r in self.routes:
                coords=[]
                for x,y,z in r['points']:
                    xx,yy,_=project((x-cx,y-cy,z),self.yaw,self.elevation);coords.extend((w/2+xx*scale,h/2+yy*scale))
                opts={'dash':(4,3)} if r['containment']=='conduit' else {}
                item=self.canvas.create_line(coords,fill='#7dbb8b' if opts else '#e1bf64',width=2,**opts)
                self.items[item]='route:'+r['id']
        self.canvas.create_text(16,18,anchor='nw',fill='#d8e6f0',text='전체 배열 · 클릭하여 상세 보기' if not self.focus else self.focus,font=('맑은 고딕',12))
        if not self.focus:
            self.canvas.create_text(16,h-22,anchor='w',fill='#a9c1d1',text='배열 또는 전기실 클릭 → 상세 보기 | 지지구조는 배열 상세에서 표시')


def open_site(parent):
    try:return SiteWindow(parent)
    except (OSError,ValueError,KeyError) as exc:messagebox.showerror('전체 모델 열기 실패',str(exc),parent=parent)

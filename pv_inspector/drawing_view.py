"""Drawing-based module inspector, separate from the illustrative site overview."""
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .drawing_model import SPEC, PROVENANCE, build_array, export_model
from .desktop import project


class DrawingWindow:
    def __init__(self,parent):
        self.window=tk.Toplevel(parent)
        self.window.title('도면 기반 3D · 표준 어레이 A01')
        self.window.geometry('1400x880')
        self.window.minsize(1000,650)
        self.modules=build_array()
        self.yaw=-0.20;self.elevation=0.70;self.zoom=1
        self.focus=None;self.selected=None;self.anchor=None;self.items={}
        top=ttk.Frame(self.window,padding=12);top.pack(fill='x')
        ttk.Label(top,text='도면 기반 3D  /  표준 어레이',font=('맑은 고딕',18,'bold')).pack(side='left')
        for title,command in [('전체 어레이',self.reset),('평면',lambda:self.view(math.pi/2)),('입면',lambda:self.view(0)),('확대',lambda:self.scale(1.4)),('축소',lambda:self.scale(1/1.4)),('모델 저장',self.save)]:
            ttk.Button(top,text=title,command=command).pack(side='left',padx=3)
        ttk.Label(self.window,text='도면 p.10–11 · 80모듈 · 41.24m · 22° · 19.6kWp(계산값) | 표준 어레이 검증 단계',padding=10).pack(fill='x')
        body=ttk.Panedwindow(self.window,orient='horizontal');body.pack(fill='both',expand=True,padx=12)
        left=ttk.Frame(body);body.add(left,weight=1)
        ttk.Label(left,text='구조 트리 · 묶음 더블클릭: 상세 보기').pack(anchor='w')
        self.tree=ttk.Treeview(left,show='tree',selectmode='browse',height=26)
        self.tree.pack(fill='both',expand=True)
        self.tree.insert('','end',iid='plant',text='신안 2차 · 전체 배치 미구현',open=True)
        self.tree.insert('plant','end',iid='array',text='표준 어레이 A01 · 80모듈',open=True)
        for g in range(1,5):
            self.tree.insert('array','end',iid=f'g{g}',text=f'묶음 G{g:02d} · 20모듈',open=False)
            for row in range(1,3):self.tree.insert(f'g{g}','end',iid=f'g{g}r{row}',text=f'경사 방향 {row}열 · 10모듈')
        for m in self.modules:self.tree.insert(f"g{m['group']}r{m['row']}",'end',iid=m['id'],text=f"M{m['column']:02d} · 245Wp")
        self.tree.bind('<<TreeviewSelect>>',self.select_tree)
        self.tree.bind('<Double-1>',self.focus_tree)
        center=ttk.Frame(body);body.add(center,weight=4)
        self.canvas=tk.Canvas(center,bg='#101d2b',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<MouseWheel>',lambda e:self.scale(1.15 if e.delta>0 else 1/1.15))
        right=ttk.Frame(body,width=260,padding=12);body.add(right,weight=1)
        ttk.Label(right,text='선택 객체 · 도면 근거',font=('맑은 고딕',12,'bold')).pack(anchor='w')
        self.details=tk.StringVar(value=self.default_details())
        ttk.Label(right,textvariable=self.details,wraplength=255,justify='left').pack(anchor='nw',pady=12)
        ttk.Label(self.window,text='드래그: 회전 · 휠: 확대 · 클릭: 모듈 선택 | 바닥선은 모델 기준면이며 실제 지면이 아닙니다. 지지대·기초·설치높이는 미확정.',padding=12).pack(fill='x')

    def default_details(self):
        return '모듈 크기\n1,675 × 1,001 × 34mm\n\n경사 22° / 245Wp\n출처: p.10 SA-E-11110\n\n가로 간격 25mm\n묶음 간격 100mm\n전체 가로 41,240mm\n출처: p.11 SA-E-11120\n\n80장 = 4묶음 × 10장 × 2열\n\n미확정\n• 지면 이격 높이\n• 지지대·기초 상세\n• 전체 발전소 배열 위치\n• 배열 간격 도면 대조\n\nRGB 분리 결과는 형상 생성에 사용하지 않았습니다.'

    def select_tree(self,event=None):
        selected=self.tree.selection()
        if not selected:return
        key=selected[0]
        self.selected=key if key.startswith('DRAFT') else None
        self.details.set((key+'\n임시 구조 ID · 실제 설비 ID 미연결\n\n' if self.selected else '')+self.default_details())
        self.draw()

    def focus_tree(self,event=None):
        selected=self.tree.selection()
        if not selected:return
        key=selected[0]
        if key.startswith('g'):self.focus=int(key[1])
        elif key.startswith('DRAFT'):self.focus=next(m['group'] for m in self.modules if m['id']==key)
        else:self.focus=None
        self.zoom=1;self.draw()

    def reset(self):
        self.focus=None;self.yaw=-0.20;self.elevation=.70;self.zoom=1;self.draw()

    def view(self,elevation):
        self.yaw=0;self.elevation=elevation;self.draw()

    def scale(self,factor):
        self.zoom=max(.3,min(12,self.zoom*factor));self.draw()

    def press(self,e):self.anchor=(e.x,e.y);self.last=(e.x,e.y)

    def drag(self,e):
        if not self.anchor:return
        self.yaw+=(e.x-self.last[0])*.008
        self.elevation=max(-.3,min(math.pi/2,self.elevation+(e.y-self.last[1])*.006))
        self.last=(e.x,e.y);self.draw()

    def release(self,e):
        if self.anchor and math.hypot(e.x-self.anchor[0],e.y-self.anchor[1])<5:
            hits=self.canvas.find_overlapping(e.x,e.y,e.x,e.y)
            key=next((self.items[i] for i in reversed(hits) if i in self.items),None)
            if key:self.tree.selection_set(key);self.tree.see(key);self.select_tree()
        self.anchor=None

    def draw(self):
        self.canvas.delete('all');self.items.clear()
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        visible=[m for m in self.modules if self.focus is None or m['group']==self.focus]
        center=sum(sum(v[0] for v in m['vertices'])/8 for m in visible)/len(visible)
        span=SPEC.width if self.focus is None else SPEC.group_width
        factor=min(w/(span+2),h/7)*self.zoom
        def screen(v):
            return project((v[0]-center,v[1]-1.55,v[2]-.63),self.yaw,self.elevation)
        faces=[]
        for m in visible:
            ps=[screen(v) for v in m['vertices']]
            for ids,color in [([0,1,2,3],'#247da4'),([4,5,6,7],'#203d50'),([0,1,5,4],'#bdcbd3'),([1,2,6,5],'#95a7b4'),([2,3,7,6],'#bdcbd3'),([3,0,4,7],'#95a7b4')]:
                points=[ps[i] for i in ids]
                faces.append((sum(p[2] for p in points)/4,points,color,m['id']))
        for _,points,color,key in sorted(faces,key=lambda f:f[0]):
            coords=[a for x,y,z in points for a in (w/2+x*factor,h/2+y*factor)]
            item=self.canvas.create_polygon(coords,fill='#d59e36' if key==self.selected else color,outline='#a5cee0',width=.6)
            self.items[item]=key
        self.canvas.create_text(16,16,anchor='nw',fill='#d2e5f2',text=f"{'전체 어레이' if self.focus is None else '묶음 G'+str(self.focus)} · {len(visible)}모듈\n도면 치수 기반 / 단위 m",font=('맑은 고딕',12))
        self.canvas.create_text(16,h-26,anchor='w',fill='#92aabc',text='기준: 모듈 저단 상면 z=0 / 실제 지면 높이 미확정')

    def save(self):
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.json',initialfile='drawing_array.json',filetypes=[('모델 JSON','*.json')])
        if path:
            try:export_model(path)
            except OSError as exc:messagebox.showerror('저장 실패',str(exc),parent=self.window)

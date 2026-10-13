"""Desktop review of paired RGB/thermal evidence with explicit landmark calibration."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from PIL import Image, ImageTk

from .module_review import ROOT, OUT, ReviewSession, project

STATUS_LABELS={'pending':'검토 대기','confirmed':'모듈 연결 확인','rejected':'연결 기각'}


class ImagePane(ttk.Frame):
    def __init__(self, parent, title, click=None):
        super().__init__(parent)
        ttk.Label(self,text=title,font=('맑은 고딕',11,'bold')).pack(anchor='w',pady=4)
        self.canvas=tk.Canvas(self,bg='#14202b',highlightthickness=0,width=400,height=350)
        self.canvas.pack(fill='both',expand=True)
        self.click=click;self.source=None;self.points=[];self.polygons=[];self.drag=None;self.photo=None
        self.scale=1.;self.offset=np.array([0.,0.]);self.path=None
        self.canvas.bind('<Configure>',lambda e:self.fit())
        self.canvas.bind('<MouseWheel>',self.zoom)
        self.canvas.bind('<Button-1>',self.select)
        self.canvas.bind('<ButtonPress-3>',lambda e:setattr(self,'drag',np.array([e.x,e.y])))
        self.canvas.bind('<B3-Motion>',self.pan)
        self.canvas.bind('<Double-Button-3>',lambda e:self.fit())

    def load(self,path):
        self.path=path
        self.source=Image.open(path).convert('RGB') if path and Path(path).is_file() else None
        self.points=[];self.polygons=[];self.fit()

    def fit(self):
        if self.source:
            w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
            self.scale=min(w/self.source.width,h/self.source.height)
            self.offset=np.array([(w-self.source.width*self.scale)/2,(h-self.source.height*self.scale)/2])
        self.draw()

    def draw(self):
        self.canvas.delete('all')
        if not self.source:
            self.canvas.create_text(15,25,text='영상 없음',fill='white',anchor='nw');return
        w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        im=self.source.transform((w,h),Image.Transform.AFFINE,
             (1/self.scale,0,-self.offset[0]/self.scale,0,1/self.scale,-self.offset[1]/self.scale),
             resample=Image.Resampling.BILINEAR)
        self.photo=ImageTk.PhotoImage(im);self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        for points,color in self.polygons:
            p=np.asarray(points)*self.scale+self.offset
            self.canvas.create_line(*np.vstack([p,p[0]]).ravel(),fill=color,width=2)
        for i,point in enumerate(self.points,1):
            x,y=np.array(point)*self.scale+self.offset
            self.canvas.create_oval(x-4,y-4,x+4,y+4,outline='#ffea00',width=2)
            self.canvas.create_text(x+7,y-8,text=str(i),fill='#ffea00',anchor='w')

    def select(self,event):
        if self.source and self.click:
            p=(np.array([event.x,event.y])-self.offset)/self.scale
            if 0<=p[0]<self.source.width and 0<=p[1]<self.source.height:self.click(p.tolist())

    def zoom(self,event):
        if not self.source:return
        anchor=np.array([event.x,event.y]);point=(anchor-self.offset)/self.scale
        self.scale=max(.015,min(8.,self.scale*(1.2 if event.delta>0 else 1/1.2)))
        self.offset=anchor-point*self.scale;self.draw()

    def pan(self,event):
        if self.drag is None:return
        p=np.array([event.x,event.y]);self.offset+=p-self.drag;self.drag=p;self.draw()


class ModuleReviewWindow:
    def __init__(self, root, output=OUT):
        self.root=root;self.session=ReviewSession(output);self.key=None;self.pending={};self.region_mode=False
        self.events=queue.Queue();self.busy=False
        root.title('A구역 | 열화상·RGB 모듈 연결 검토');root.geometry('1480x960');root.minsize(1100,760)
        header=ttk.Frame(root,padding=10);header.pack(fill='x')
        ttk.Label(header,text='A구역 모듈 연결 검토',font=('맑은 고딕',18,'bold')).pack(side='left')
        ttk.Label(header,text='휠: 확대 · 오른쪽 드래그: 이동 · 오른쪽 더블클릭: 전체').pack(side='right')
        top=ttk.Frame(root,padding=(10,0));top.pack(fill='x')
        self.case_var=tk.StringVar();self.case_box=ttk.Combobox(top,textvariable=self.case_var,state='readonly',width=75)
        self.case_box.pack(side='left');self.case_box.bind('<<ComboboxSelected>>',self.change_case)
        self.case_keys=list(self.session.cases)
        self.case_box['values']=[f"{k}  |  {c['image_id']}  |  {c['validation_zone']}" for k,c in self.session.cases.items()]
        self.status=tk.StringVar(value='검토 대기');ttk.Label(top,textvariable=self.status).pack(side='left',padx=12)
        self.info=tk.StringVar();ttk.Label(root,textvariable=self.info,padding=10,wraplength=1420).pack(fill='x')
        self.tabs=ttk.Notebook(root);self.tabs.pack(fill='both',expand=True,padx=10)
        evidence=ttk.Frame(self.tabs);self.tabs.add(evidence,text='① 원본과 주변 촬영')
        grid=ttk.Frame(evidence);grid.pack(fill='both',expand=True)
        self.original=[]
        for name in ('열화상 원본 · 노란색은 검출 영역','같은 촬영 RGB · 픽셀 위치는 서로 다릅니다','정사영상 · 파란색은 도면 모듈'):
            pane=ImagePane(grid,name);pane.pack(side='left',fill='both',expand=True,padx=3);self.original.append(pane)
        row=ttk.Frame(evidence);row.pack(fill='x',pady=6)
        ttk.Label(row,text='주변 촬영 (같은 모듈로 확인된 자료가 아닙니다):').pack(side='left')
        self.neighbor_box=ttk.Combobox(row,state='readonly',width=42);self.neighbor_box.pack(side='left')
        self.neighbor_box.bind('<<ComboboxSelected>>',self.show_neighbor)
        ttk.Button(row,text='현재 결과 원본으로 복귀',command=self.restore_originals).pack(side='left',padx=5)
        self.panes={}
        for stage,title,left,right in [('thermal_rgb','② 열화상 ↔ RGB','열화상: 먼저 같은 모서리 클릭','RGB: 다음으로 대응 모서리 클릭'),
                                        ('rgb_ortho','③ RGB ↔ 정사영상','RGB: 먼저 같은 모서리 클릭','정사영상: 다음으로 대응 모서리 클릭')]:
            page=ttk.Frame(self.tabs);self.tabs.add(page,text=title)
            controls=ttk.Frame(page);controls.pack(fill='x',pady=5)
            ttk.Label(controls,text='동일한 모서리를 왼쪽→오른쪽 순서로 6쌍 이상 선택하세요. 대상 모듈을 둘러싸고 넓게 분산해야 합니다.').pack(side='left')
            ttk.Button(controls,text='마지막 쌍 취소',command=lambda s=stage:self.undo(s)).pack(side='right')
            ttk.Button(controls,text='대응점 초기화',command=lambda s=stage:self.clear_pairs(s)).pack(side='right')
            views=ttk.Frame(page);views.pack(fill='both',expand=True)
            a=ImagePane(views,left,lambda p,s=stage:self.landmark(s,0,p));a.pack(side='left',fill='both',expand=True,padx=3)
            b=ImagePane(views,right,lambda p,s=stage:self.landmark(s,1,p));b.pack(side='left',fill='both',expand=True,padx=3)
            self.panes[stage]=(a,b)
            if stage=='thermal_rgb':
                ttk.Button(page,text='열화상 모듈 영역 지정: 네 모서리를 순서대로 클릭',command=self.start_region).pack(anchor='w',pady=5)
        bottom=ttk.Frame(root,padding=10);bottom.pack(fill='x')
        self.result=tk.StringVar(value='아직 연결을 확인하지 않았습니다.')
        ttk.Label(bottom,textvariable=self.result,wraplength=1420).pack(anchor='w')
        details=ttk.Frame(bottom);details.pack(fill='x',pady=6)
        ttk.Label(details,text='검토자').pack(side='left');self.reviewer=tk.StringVar();ttk.Entry(details,textvariable=self.reviewer,width=16).pack(side='left',padx=5)
        ttk.Label(details,text='확인 근거 / 메모').pack(side='left');self.note=tk.StringVar();ttk.Entry(details,textvariable=self.note).pack(side='left',fill='x',expand=True,padx=5)
        actions=ttk.Frame(bottom);actions.pack(fill='x')
        ttk.Button(actions,text='정합 검사 · 모듈 후보 계산',command=self.calculate).pack(side='left',padx=3)
        ttk.Button(actions,text='진행 저장',command=lambda:self.save('pending')).pack(side='left',padx=3)
        ttk.Button(actions,text='모듈 연결 확인 저장',command=lambda:self.save('confirmed')).pack(side='left',padx=3)
        ttk.Button(actions,text='현재 연결 기각',command=lambda:self.save('rejected')).pack(side='left',padx=3)
        self.export_button=ttk.Button(actions,text='확인 상태를 Blender에 반영',command=self.export_blender)
        self.export_button.pack(side='right')
        ttk.Label(bottom,text='빨간 패널: 연결 확인한 이상 의심 결과 · 주황색: 연결 검토 중 · 기각은 연결을 기각하며 정상 판정이 아닙니다.').pack(anchor='w',pady=(6,0))
        self.case_box.current(0);self.load_case(self.case_keys[0]);self.root.after(200,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def drafts(self):
        self.evidence['reviewer']=self.reviewer.get();self.evidence['note']=self.note.get()
        return self.evidence

    def change_case(self,event=None):
        if self.key and not self.save('pending',silent=True,preserve=True):
            self.case_box.current(self.case_keys.index(self.key));return
        self.load_case(self.case_keys[self.case_box.current()])

    def load_case(self,key):
        self.key=key;self.case=self.session.cases[key];self.evidence=self.session.evidence(key)
        self.saved=copy.deepcopy(self.evidence);self.pending={};self.region_mode=False
        self.reviewer.set(self.evidence.get('reviewer',''));self.note.set(self.evidence.get('note',''))
        c=self.case
        pairing='날짜·촬영 번호로 연결' if c['rgb'] else 'RGB 누락 또는 중복'
        alignment=c['rgb_alignment'].get('reason','기하 검사 통과 · 모듈 동일성 확인 필요')
        self.info.set(f"{c['module_uid']} · {c['validation_zone']} · 이상 의심 | 기존 최고 {c.get('max_temp')}°C · ΔT {c.get('delta_temp')}°C (최고−평균)\n"
                      f"촬영 쌍: {pairing} | RGB 자동 정합: {alignment} | 기존 근접 후보: {c.get('drawing_candidate_id','없음')}")
        self.restore_originals()
        self.panes['thermal_rgb'][0].load(c['thermal']);self.panes['thermal_rgb'][1].load(c['rgb'])
        self.panes['rgb_ortho'][0].load(c['rgb']);self.panes['rgb_ortho'][1].load(c['ortho'])
        self.neighbor_box['values']=[Path(n['thermal']).name for n in c['neighbor_captures']];self.neighbor_box.set('')
        self.result.set('현재 연결 상태: '+STATUS_LABELS[self.evidence['status']]);self.refresh()

    def restore_originals(self):
        c=self.case
        for pane,path in zip(self.original,[c['thermal'],c['rgb'],c['ortho']]):pane.load(path)
        x1,y1,x2,y2=c['bbox'];self.original[0].polygons=[([[x1,y1],[x2,y1],[x2,y2],[x1,y2]],'#ffe600')]
        self.original[0].draw()
        matrix=np.array(self.session.manifest['registration']['matrix_3x2']);inv=np.linalg.inv(matrix[:2])
        tile_inv=np.linalg.inv(c['tile_to_local']);polygons=[]
        for module in self.session.module_list:
            xy=np.array(module['polygon'])[:,:2];local=(xy-matrix[2])@inv
            tile=project(local,tile_inv)
            if np.all(tile.max(axis=0)>0) and np.all(tile.min(axis=0)<self.original[2].source.size):
                polygons.append((tile.tolist(),'#37cedb'))
        self.original[2].polygons=polygons;self.original[2].draw()

    def show_neighbor(self,event=None):
        i=self.neighbor_box.current()
        if i<0:return
        n=self.case['neighbor_captures'][i]
        self.original[0].load(n['thermal']);self.original[1].load(n['rgb'])
        self.status.set('주변 촬영 참고 중 · 동일 모듈 여부 미확인')

    def refresh(self):
        for stage,panes in self.panes.items():
            pairs=self.evidence.get(stage+'_pairs',[])
            for side,pane in enumerate(panes):
                pane.points=[p[side] for p in pairs];pane.polygons=[]
                if side==0 and stage in self.pending:pane.points.append(self.pending[stage])
                if stage=='thermal_rgb' and side==0 and self.evidence.get('thermal_polygon'):
                    pane.polygons=[(self.evidence['thermal_polygon'],'#ff8c32')] if len(self.evidence['thermal_polygon'])>=2 else []
                pane.draw()
        self.status.set(f"{STATUS_LABELS[self.evidence['status']]} · 열화상/RGB {len(self.evidence.get('thermal_rgb_pairs',[]))}쌍 · RGB/지도 {len(self.evidence.get('rgb_ortho_pairs',[]))}쌍")

    def changed(self):
        self.evidence['status']='pending';self.evidence.pop('proposal',None)
        self.result.set('대응점이 변경되었습니다. 다시 검사하고 연결 확인을 저장하세요.')

    def landmark(self,stage,side,point):
        self.changed()
        if self.region_mode and stage=='thermal_rgb' and side==0:
            self.evidence['thermal_polygon'].append(point)
            if len(self.evidence['thermal_polygon'])==4:self.region_mode=False
        elif side==0:self.pending[stage]=point
        elif stage in self.pending:self.evidence.setdefault(stage+'_pairs',[]).append([self.pending.pop(stage),point])
        else:self.result.set('왼쪽 영상에서 먼저 모서리를 선택해 주세요.')
        self.refresh()

    def undo(self,stage):
        self.changed()
        if stage in self.pending:self.pending.pop(stage)
        elif self.evidence.get(stage+'_pairs'):self.evidence[stage+'_pairs'].pop()
        self.refresh()

    def clear_pairs(self,stage):
        self.changed();self.evidence[stage+'_pairs']=[];self.pending.pop(stage,None);self.refresh()

    def start_region(self):
        self.changed();self.region_mode=True;self.evidence['thermal_polygon']=[]
        self.result.set('왼쪽 열화상에서 대상 모듈 네 모서리를 시계 방향 또는 반시계 방향으로 클릭하세요.');self.refresh()

    def calculate(self):
        try:
            p=self.session.propose(self.key,self.drafts())
            self.result.set(f"시각 정합 후보: {p['module_id']} · 중심 오차 {p['distance_m']:.2f}m · 영역 겹침 {p['overlap_fraction']:.0%} · 확인 저장 전까지 미확정")
            if p['temperature']:
                t=p['temperature'];self.result.set(self.result.get()+f" | 원본 온도: {t['temperature_status']} / 최고 {t['max_temp']}°C")
            local=(np.asarray(p['projected_polygon'])-np.asarray(self.session.manifest['registration']['matrix_3x2'])[2])@np.linalg.inv(np.asarray(self.session.manifest['registration']['matrix_3x2'])[:2])
            tile=project(local,np.linalg.inv(self.case['tile_to_local']))
            self.original[2].polygons.append((tile.tolist(),'#ff8c32'));self.original[2].draw()
        except (ValueError,KeyError) as exc:messagebox.showwarning('검토 필요',str(exc),parent=self.root)

    def save(self,status,silent=False,preserve=False):
        try:
            draft=self.drafts()
            if preserve and draft==self.saved:return True
            self.evidence=self.session.save(self.key,draft,status,self.reviewer.get(),self.note.get())
            self.saved=copy.deepcopy(self.evidence);self.refresh()
            if not silent:self.result.set('저장 완료: '+STATUS_LABELS[status]+' · 변경 이력을 함께 보관했습니다.')
            return True
        except ValueError as exc:
            messagebox.showerror('저장 실패',str(exc),parent=self.root);return False

    def export_blender(self):
        if self.busy:return
        if not self.save('pending',silent=True,preserve=True):return
        self.busy=True;self.export_button.configure(state='disabled');self.result.set('확인 상태를 적용해 Blender 파일을 생성 중입니다…')
        def work():
            try:
                self.session.export()
                blender=Path('C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
                log=self.session.output/'blender_build.log'
                with log.open('w',encoding='utf-8') as f:
                    result=subprocess.run([str(blender),'--background','--python-exit-code','1','--python',str(ROOT/'add_blender_registered_a.py'),'--','--reviewed'],
                                          cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if result.returncode:raise ValueError(f'Blender 생성 실패. 로그: {log}')
                self.events.put(('ok','Blender 반영 완료. Open_Thermal_A_Reviewed.bat으로 열어 주세요.'))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            kind,text=self.events.get_nowait();self.busy=False;self.export_button.configure(state='normal');self.result.set(text)
            if kind=='error':messagebox.showerror('반영 실패',text,parent=self.root)
        except queue.Empty:pass
        self.root.after(200,self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('생성 중','Blender 파일 생성이 끝난 뒤 닫아 주세요.',parent=self.root);return
        if self.save('pending',silent=True,preserve=True):self.root.destroy()


def open_module_review(parent=None):
    if not (OUT/'manifest.json').exists():
        messagebox.showinfo('자료 준비','먼저 python run_module_review.py --prepare 를 실행해 주세요.',parent=parent);return
    window=tk.Toplevel(parent) if parent else tk.Tk()
    try:ModuleReviewWindow(window)
    except Exception as exc:
        window.destroy();messagebox.showerror('검토 자료 오류',str(exc),parent=parent);return
    if parent is None:window.mainloop()

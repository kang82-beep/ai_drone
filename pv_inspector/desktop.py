"""Local operations window and an illustrative, orthographically projected 3D site."""
from __future__ import annotations

import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def project(point, yaw, elevation):
    """Return screen-plane coordinates and camera depth for a world point."""
    x, y, z = point
    a = x * math.cos(yaw) - y * math.sin(yaw)
    b = x * math.sin(yaw) + y * math.cos(yaw)
    return a, b * math.sin(elevation) - z * math.cos(elevation), b * math.cos(elevation) + z * math.sin(elevation)


def site_faces():
    """Schematic only: repeated array strips, not surveyed module geometry."""
    faces = []
    def face(points, color, name):
        faces.append((points, color, name))
    face([(-185,-150,0),(165,-150,0),(185,105,0),(110,150,0),(-170,140,0)], '#526650', '부지 / 개략 경계')
    for col in range(4):
        for row in range(4):
            x, y = -158 + col * 84, -128 + row * 69
            count = 9
            if (col, row) in [(0,0),(3,3)]:
                count = 5
            for strip in range(count):
                sy = y + strip * 6
                if (col,row) == (2,2) and strip < 3:
                    continue
                if (col,row) == (0,2):
                    continue
                name = f'배열 {col+1}-{row+1} / 열 {strip+1}'
                face([(x,sy,2),(x+77,sy,2),(x+77,sy+3.5,3.5),(x,sy+3.5,3.5)], '#287da0', name)
    for x,y,name in [(-151,20,'진입부 건물'),(22,14,'내부 건물')]:
        face([(x,y,0),(x+18,y,0),(x+18,y,7),(x,y,7)], '#9aaabd', name)
        face([(x+18,y,0),(x+18,y+11,0),(x+18,y+11,7),(x+18,y,7)], '#75879b', name)
        face([(x,y+11,0),(x+18,y+11,0),(x+18,y+11,7),(x,y+11,7)], '#8799ac', name)
        face([(x,y,0),(x,y+11,0),(x,y+11,7),(x,y,7)], '#75879b', name)
        face([(x,y,7),(x+18,y,7),(x+18,y+11,7),(x,y+11,7)], '#d4e2ec', name)
    return faces


class OperationsWindow:
    def __init__(self, root, webview_module=None):
        self.root = root
        self.webview = webview_module
        self.process = None
        self.events = queue.Queue()
        self.yaw, self.elevation, self.zoom = -0.35, 0.85, 1.0
        self.drag_origin = None
        self.selected = None
        self.faces = site_faces()
        self.items = {}
        self.input_path = tk.StringVar()
        self.config_path = tk.StringVar(value=str(ROOT / 'config.local.json'))
        self.output_path = tk.StringVar()
        self.status = tk.StringVar(value='대기 · 실시간 센서 미연결')
        self.detail = tk.StringVar(value='배열이나 건물을 클릭하면 정보가 표시됩니다.')
        root.title('신안 태양광 | 운영 콘솔 · 3D 맵')
        root.geometry('1280x820')
        root.minsize(950,650)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TButton', padding=7)
        header = ttk.Frame(root, padding=14)
        header.pack(fill='x')
        ttk.Label(header,text='SHINAN  /  태양광 운영 콘솔',font=('맑은 고딕',19,'bold')).pack(side='left')
        ttk.Label(header,textvariable=self.status).pack(side='right')
        controls = ttk.LabelFrame(root,text='분석 운영',padding=10)
        controls.pack(fill='x',padx=14,pady=(0,10))
        for row,(label,var,command) in enumerate([
            ('드론 이미지 폴더',self.input_path,self.choose_input),
            ('설정 JSON',self.config_path,self.choose_config),
            ('결과 폴더',self.output_path,self.choose_output),
        ]):
            ttk.Label(controls,text=label).grid(row=row,column=0,padx=6)
            ttk.Entry(controls,textvariable=var).grid(row=row,column=1,sticky='ew',pady=3)
            ttk.Button(controls,text='찾아보기',command=command).grid(row=row,column=2,padx=6)
        controls.columnconfigure(1,weight=1)
        buttons = ttk.Frame(controls)
        buttons.grid(row=3,column=0,columnspan=3,sticky='w',pady=(6,0))
        review_buttons = ttk.Frame(controls)
        review_buttons.grid(row=4,column=0,columnspan=3,sticky='w',pady=(6,0))
        ttk.Button(review_buttons,text='현장 검토표',command=lambda:self.open_report('field_review.html')).pack(side='left',padx=3)
        self.run_buttons = []
        settings_button = ttk.Button(review_buttons, text='경로 및 지도 설정', command=self.edit_settings)
        settings_button.pack(side='left', padx=3)
        self.run_buttons.append(settings_button)
        ttk.Button(review_buttons, text='Blender 분석 3D', command=self.open_blender_analysis).pack(side='left', padx=3)
        for title,command in [('입력 검사',lambda:self.run(True)),('분석 실행',lambda:self.run(False))]:
            btn=ttk.Button(buttons,text=title,command=command)
            btn.pack(side='left',padx=3)
            self.run_buttons.append(btn)
        ttk.Button(buttons,text='결과 보고서',command=lambda:self.open_report('results.html')).pack(side='left',padx=3)
        ttk.Button(buttons,text='검사 지도',command=lambda:self.open_report('map.html')).pack(side='left',padx=3)
        from .orthoview import open_ortho
        ttk.Button(buttons,text='드론 RGB 지도',command=lambda:open_ortho(root)).pack(side='left',padx=3)
        from .drawing_view import DrawingWindow
        ttk.Button(buttons,text='도면 기반 3D',command=lambda:DrawingWindow(root)).pack(side='left',padx=3)
        from .site_view import open_site
        ttk.Button(buttons,text='발전소 전체 3D',command=lambda:open_site(root)).pack(side='left',padx=3)
        from .module_review_ui import open_module_review
        ttk.Button(buttons,text='A구역 연결 검토',command=lambda:open_module_review(root)).pack(side='left',padx=3)
        body=ttk.Frame(root,padding=(14,0,14,10))
        body.pack(fill='both',expand=True)
        toolbar=ttk.Frame(body)
        toolbar.pack(fill='x')
        ttk.Label(toolbar,text='3D 발전단지 · 초기 개략 모델',font=('맑은 고딕',12,'bold')).pack(side='left')
        for title,command in [('시점 초기화',self.reset),('평면 보기',self.top),('＋',lambda:self.scale(1.15)),('－',lambda:self.scale(1/1.15))]:
            ttk.Button(toolbar,text=title,command=command).pack(side='right',padx=2)
        self.canvas=tk.Canvas(body,bg='#111e2b',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True,pady=6)
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.drag)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<MouseWheel>',lambda e:self.scale(1.1 if e.delta>0 else 1/1.1))
        ttk.Label(body,textvariable=self.detail).pack(anchor='w')
        ttk.Label(body,text='드래그: 회전 · 휠: 확대/축소 | 도면 배치 참고용. 치수·높이·구역은 미검증이며 검사 결과와 미연결.').pack(anchor='w')
        self.log=tk.Text(root,height=7,bg='#172330',fg='#d5e1ed',font=('Consolas',10),state='disabled')
        self.log.pack(fill='x',padx=14,pady=(0,14))
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)
        if Path(self.config_path.get()).is_file():
            self.load_settings(self.config_path.get())

    def apply_settings(self, path, values):
        self.config_path.set(path)
        for key, var in [('INPUT_IMG_DIR', self.input_path), ('OUTPUT_ROOT', self.output_path)]:
            value = values.get(key, '')
            var.set(str((ROOT / value).resolve()) if value else '')

    def load_settings(self, path):
        from .settings_ui import read_settings
        try:
            values = read_settings(path)
            self.apply_settings(path, values)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror('설정 읽기 실패', str(exc), parent=self.root)

    def edit_settings(self):
        if self.process is not None:
            return
        from .settings_ui import SettingsDialog
        try:
            SettingsDialog(self.root, self.config_path.get(), self.input_path.get(),
                           self.output_path.get(), self.apply_settings)
        except (OSError, ValueError) as exc:
            messagebox.showerror('설정 읽기 실패', str(exc), parent=self.root)

    def open_blender_analysis(self):
        from .settings_ui import read_settings
        from .module_links import validate_blender_export
        try:
            settings = read_settings(self.config_path.get())
            executable = settings.get('BLENDER_EXE', '')
            scene = settings.get('BLENDER_SCENE', '')
            if not executable or not scene:
                raise ValueError('경로 및 지도 설정에서 Blender 실행 파일과 분석 연결 Blender 파일을 선택하세요.')
            executable, scene = ROOT / executable, ROOT / scene
            if not executable.is_file() or not scene.is_file():
                raise ValueError('Blender 실행 파일 또는 장면 파일이 없습니다. 경로 설정을 확인하세요.')
            validate_blender_export(scene)
            subprocess.Popen([str(executable), str(scene), '--python', str(ROOT / 'blender_module_results_ui.py')],
                             cwd=ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, ValueError) as exc:
            messagebox.showerror('Blender 분석 연결 확인', str(exc), parent=self.root)

    def choose_input(self):
        path=filedialog.askdirectory(title='드론 열화상/가시광 이미지가 있는 폴더를 선택하세요')
        if path:self.input_path.set(path)

    def choose_config(self):
        path=filedialog.askopenfilename(filetypes=[('JSON 설정','*.json')])
        if path:self.load_settings(path)

    def choose_output(self):
        path=filedialog.askdirectory(title='기존 결과를 열거나, 분석용 빈 폴더를 선택하세요')
        if path:self.output_path.set(path)

    def run(self,check):
        if self.process is not None:return
        settings=Path(self.config_path.get())
        if not settings.is_file():
            messagebox.showerror('설정 확인','존재하는 설정 JSON을 선택하세요.');return
        output=self.output_path.get().strip()
        if not check:
            try:
                invalid = not output or (Path(output).exists() and (not Path(output).is_dir() or any(Path(output).iterdir())))
            except OSError as exc:
                messagebox.showerror('결과 폴더',str(exc));return
            if invalid:
                messagebox.showerror('결과 폴더','분석에는 새 폴더 또는 빈 결과 폴더가 필요합니다.');return
        args=[sys.executable,'-u','-m','pv_inspector','--config',str(settings.resolve())]
        input_dir=self.input_path.get().strip()
        if input_dir:args+=['--input',input_dir]
        if output and not check:args+=['--output',output]
        if check:args+=['--check']
        try:
            self.process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                env=os.environ | {'PYTHONIOENCODING':'utf-8'})
        except OSError as exc:
            messagebox.showerror('실행 실패',str(exc));return
        self.status.set('입력 검사 중' if check else '분석 중 · 로그를 확인하세요')
        for btn in self.run_buttons:btn.configure(state='disabled')
        process=self.process
        def read():
            for line in process.stdout:self.events.put(('log',line))
            process.stdout.close()
            self.events.put(('done',process.wait()))
        threading.Thread(target=read,daemon=True).start()

    def poll(self):
        for _ in range(300):
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='log':
                self.log.configure(state='normal');self.log.insert('end',value)
                if int(self.log.index('end-1c').split('.')[0])>2000:self.log.delete('1.0','500.0')
                self.log.see('end');self.log.configure(state='disabled')
            else:
                self.process=None
                self.status.set('작업 완료' if value==0 else f'작업 실패 · 종료 코드 {value}')
                for btn in self.run_buttons:btn.configure(state='normal')
        self.root.after(100,self.poll)

    def open_report(self,name):
        if not self.output_path.get().strip():
            messagebox.showinfo('결과 선택','먼저 결과 폴더를 선택하세요.');return
        path=Path(self.output_path.get())/name
        if not path.is_file():messagebox.showinfo('보고서 없음',f'{name} 파일이 없습니다.');return
        self.open_in_app_window(name,path)

    def open_in_app_window(self,title,path):
        """Show an HTML report in its own native webview window (Leaflet/JS needs a real browser engine, which Tkinter has none of)."""
        url=path.resolve().as_uri()
        if self.webview is None:
            webbrowser.open(url);return
        try:
            self.webview.create_window(title,url,width=1280,height=860)
        except Exception as exc:
            self.log.configure(state='normal');self.log.insert('end',f'[뷰어] 앱 창으로 열지 못해 브라우저로 엽니다: {exc}\n');self.log.see('end');self.log.configure(state='disabled')
            webbrowser.open(url)

    def reset(self):
        self.yaw,self.elevation,self.zoom=-0.35,0.85,1.0
        self.draw()

    def top(self):
        self.elevation=math.pi/2;self.draw()

    def scale(self,factor):
        self.zoom=max(0.3,min(4,self.zoom*factor));self.draw()

    def press(self,event):
        self.drag_origin=(event.x,event.y)
        self.last=(event.x,event.y)

    def drag(self,event):
        if self.drag_origin is None:return
        self.yaw+=(event.x-self.last[0])*0.008
        self.elevation=max(0.15,min(math.pi/2,self.elevation+(event.y-self.last[1])*0.006))
        self.last=(event.x,event.y);self.draw()

    def release(self,event):
        if self.drag_origin and math.hypot(event.x-self.drag_origin[0],event.y-self.drag_origin[1])<5:
            hits=self.canvas.find_overlapping(event.x,event.y,event.x,event.y)
            self.selected=next((self.items[i] for i in reversed(hits) if i in self.items),None)
            self.detail.set(f'{self.selected} · 개략 모델 / 실제 설비 ID 및 진단 상태 미연결' if self.selected else '선택된 설비 없음')
            self.draw()
        self.drag_origin=None

    def draw(self):
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        scale=min(w/450,h/360)*self.zoom
        self.canvas.delete('all');self.items.clear()
        projected=[]
        for points,color,name in self.faces:
            ps=[project(p,self.yaw,self.elevation) for p in points]
            projected.append((sum(p[2] for p in ps)/len(ps),ps,color,name))
        for _,ps,color,name in sorted(projected,key=lambda f:f[0]):
            coords=[v for x,y,_ in ps for v in (w/2+x*scale,h/2+y*scale)]
            item=self.canvas.create_polygon(coords,fill=color,outline='#ffcb66' if name==self.selected else '#142c3b',width=2 if name==self.selected else 1)
            self.items[item]=name
        self.canvas.create_text(18,18,anchor='nw',fill='#90b3cb',text='LOCAL 3D  /  SHINAN 2 · 5 MW\n개략 배치 · 실시간 데이터 미연결',font=('맑은 고딕',11))

    def close(self):
        if self.process is not None:
            messagebox.showinfo('작업 진행 중','분석이 완료된 뒤 창을 닫아주세요. 로그에서 진행 상태를 확인할 수 있습니다.');return
        self.root.destroy()
        if self.webview is not None:
            for w in list(self.webview.windows):
                try: w.destroy()
                except Exception: pass


def _run_tk(webview_module):
    root = tk.Tk()
    OperationsWindow(root, webview_module)
    root.mainloop()


def main():
    """pywebview owns the process main thread (a hard requirement of the library);
    the operations window itself runs inside the worker thread pywebview hands to `func`,
    so report windows can be opened in-app with `webview.create_window(...)` on demand."""
    try:
        import webview
        webview.create_window('bootstrap', 'about:blank', hidden=True)
    except Exception:
        _run_tk(None)
        return
    try:
        webview.start(_run_tk, webview, gui='edgechromium', debug=False)
    except Exception:
        _run_tk(None)


if __name__=='__main__':
    main()

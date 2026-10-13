"""Windowed GeoTIFF viewer. No full-resolution raster is held in memory."""
import queue
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk


def load_module_layers(path, root=None):
    """Load independent candidate layers; stale refined geometry is never reused."""
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    layers={}
    for name,folder in [('기존 색상 후보','module_split_site'),('기존 방식 재검출','module_arrays_baseline'),('배열 기반 검토','module_arrays_site'),('배열 기반 검토','module_arrays_site_v2')]:
        try:
            data=json.loads((root/'results'/folder/'modules.json').read_text(encoding='utf-8'))
            source=Path(path)
            if Path(data['source']).resolve()!=source.resolve():continue
            if folder.startswith('module_arrays_site'):
                stat=source.stat()
                if data['source_size']!=stat.st_size or data['source_mtime_ns']!=stat.st_mtime_ns:continue
            pending=[]
            for slot in data.get('slots',[]):
                if slot['status']!='unconfirmed':continue
                polygon=slot['expected_polygon']
                pending.append(dict(id=slot['id']+'-pending',polygon=polygon,
                    center=[sum(p[0] for p in polygon)/len(polygon),sum(p[1] for p in polygon)/len(polygon)],
                    status='review',origin='unconfirmed_slot'))
            layers[name]=dict(modules=data['modules'],review=data.get('review_candidates',[])+pending)
        except (OSError,ValueError,KeyError):continue
    return layers


def read_view(path, viewport, size):
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling, ColorInterp
    from rasterio.windows import Window
    from PIL import Image
    with rasterio.open(path) as src:
        if viewport is None:
            viewport = (0, 0, src.width, src.height)
        x,y,w,h = viewport
        factor = min(size[0]/w,size[1]/h)
        ow,oh = max(1,round(w*factor)),max(1,round(h*factor))
        colors=list(src.colorinterp)
        if all(c in colors for c in (ColorInterp.red,ColorInterp.green,ColorInterp.blue)):
            indexes=[colors.index(c)+1 for c in (ColorInterp.red,ColorInterp.green,ColorInterp.blue)]
        elif src.count == 1:
            indexes=[1,1,1]
        else:
            raise ValueError('RGB 밴드 정보가 없는 영상입니다.')
        data=src.read(indexes,window=Window(x,y,w,h),out_shape=(3,oh,ow),masked=True,resampling=Resampling.bilinear)
        if data.dtype != np.uint8:
            raise ValueError('현재 뷰어는 8비트 RGB 영상을 지원합니다.')
        image=Image.fromarray(data.filled(0).transpose(1,2,0))
        meta={'width':src.width,'height':src.height,'crs':str(src.crs),'resolution':src.res,'transform':src.transform}
        return image,viewport,meta


class OrthoWindow:
    def __init__(self,parent,path):
        self.path=path
        self.window=tk.Toplevel(parent)
        self.window.title('드론 RGB 정사영상 · '+str(path))
        self.window.geometry('1100x800')
        self.viewport=None
        self.meta=None
        self.busy=False
        self.pending=False
        self.closed=False
        self.generation=0
        self.results=queue.Queue()
        self.photo=None
        self.display=None
        self.press_position=None
        self.modules=[]
        self.selected=None
        self.show_modules=tk.BooleanVar(value=True)
        self.layers=load_module_layers(path)
        self.layer_name=tk.StringVar(value='배열 기반 검토' if '배열 기반 검토' in self.layers else next(iter(self.layers),'후보 없음'))
        self.show_review=tk.BooleanVar(value=False)
        self.modules=self.layers.get(self.layer_name.get(),{}).get('modules',[])
        bar=ttk.Frame(self.window,padding=8);bar.pack(fill='x')
        ttk.Button(bar,text='전체 보기',command=self.reset).pack(side='left')
        ttk.Button(bar,text='확대',command=lambda:self.zoom(0.5)).pack(side='left')
        ttk.Button(bar,text='축소',command=lambda:self.zoom(2)).pack(side='left')
        ttk.Checkbutton(bar,text='모듈 경계',variable=self.show_modules,command=self.draw_modules).pack(side='left')
        layer_select=ttk.Combobox(bar,textvariable=self.layer_name,values=list(self.layers),state='readonly',width=16)
        layer_select.pack(side='left',padx=5);layer_select.bind('<<ComboboxSelected>>',lambda e:self.select_layer())
        ttk.Checkbutton(bar,text='미확인 후보·빈칸',variable=self.show_review,command=self.select_layer).pack(side='left')
        ttk.Label(bar,text='휠: 확대/축소 · 드래그: 이동 · 원본 해상도 구간 읽기').pack(side='left',padx=12)
        self.status=tk.StringVar(value='영상 정보를 읽는 중…')
        ttk.Label(self.window,textvariable=self.status,padding=8).pack(fill='x')
        self.selection_text=tk.StringVar(value=f'모듈 후보 {len(self.modules):,}개 · 초록: 기본 기준 / 주황: 추가 검토 · 클릭: 임시 ID 확인')
        ttk.Label(self.window,textvariable=self.selection_text,padding=8).pack(fill='x')
        self.canvas=tk.Canvas(self.window,bg='#111e2b',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.request())
        self.canvas.bind('<MouseWheel>',lambda e:self.zoom(0.7 if e.delta>0 else 1/0.7))
        self.canvas.bind('<ButtonPress-1>',lambda e:setattr(self,'press_position',(e.x,e.y)))
        self.canvas.bind('<ButtonRelease-1>',self.pan)
        self.select_layer()
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.after(100,self.poll)
        self.window.after(150,self.request)

    def reset(self):
        self.viewport=None;self.request()

    def select_layer(self):
        layer=self.layers.get(self.layer_name.get(),{'modules':[],'review':[]})
        self.modules=layer['modules']+(layer['review'] if self.show_review.get() else [])
        self.selected=None
        self.selection_text.set(f"{self.layer_name.get()} · 모듈 후보 {len(layer['modules']):,} · 미확인 항목 {len(layer['review']):,} · 실제 설비 수/고장 상태 아님")
        self.draw_modules()

    def zoom(self,factor):
        if self.viewport is None or not self.meta:return
        x,y,w,h=self.viewport
        nw=max(32,min(self.meta['width'],w*factor))
        nh=max(32,min(self.meta['height'],h*factor))
        self.viewport=self.clamp(x+(w-nw)/2,y+(h-nh)/2,nw,nh)
        self.request()

    def clamp(self,x,y,w,h):
        return max(0,min(self.meta['width']-w,x)),max(0,min(self.meta['height']-h,y)),w,h

    def pan(self,event):
        if not self.display or not self.meta or not self.press_position:return
        viewport,iw,ih=self.display
        x,y,w,h=viewport
        dx,dy=event.x-self.press_position[0],event.y-self.press_position[1]
        if abs(dx)+abs(dy)<5 and self.show_modules.get():
            import cv2
            import numpy as np
            ox=(self.canvas.winfo_width()-iw)/2;oy=(self.canvas.winfo_height()-ih)/2
            px=x+(event.x-ox)*w/iw;py=y+(event.y-oy)*h/ih
            self.selected=None
            for m in self.modules:
                cx,cy=m['center']
                if abs(cx-px)<100 and abs(cy-py)<120 and cv2.pointPolygonTest(np.array(m['polygon'],dtype=np.float32),(px,py),False)>=0:
                    self.selected=m['id']
                    origins={'merged_split':'합쳐진 영역 분리','gap_reinspection':'빈칸 원본 재검사','boundary_refined':'경계 보정','unconfirmed_slot':'미확인 예상 칸'}
                    detail=origins.get(m.get('origin'), '추가 검토' if m['status']=='review' else '모듈 후보')
                    self.selection_text.set(f"{m['id']} | {detail} | 원본 픽셀 ({cx:.1f}, {cy:.1f}) | 실제 설비 ID·고장 상태 미연결")
                    break
            if not self.selected:self.selection_text.set('선택된 모듈 없음')
            self.press_position=None;self.draw_modules();return
        self.viewport=self.clamp(x-dx*w/iw,y-dy*h/ih,w,h)
        self.press_position=None;self.request()

    def request(self):
        if self.closed:return
        self.generation+=1
        self.pending=True
        if not self.busy:self.start()

    def start(self):
        self.pending=False;self.busy=True
        generation=self.generation
        viewport=self.viewport
        size=(max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height()))
        self.status.set('원본 영상 읽는 중… 최초 전체 보기는 시간이 걸릴 수 있습니다.')
        def worker():
            try:self.results.put((generation,read_view(self.path,viewport,size),None))
            except Exception as exc:self.results.put((generation,None,str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll(self):
        if self.closed:return
        try:
            generation,result,error=self.results.get_nowait()
        except queue.Empty:pass
        else:
            self.busy=False
            if generation==self.generation:
                if error:self.status.set('영상 읽기 실패: '+error)
                else:
                    from PIL import ImageTk
                    image,self.viewport,self.meta=result
                    self.photo=ImageTk.PhotoImage(image,master=self.window)
                    self.canvas.delete('all')
                    self.canvas.create_image(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,image=self.photo)
                    self.display=(self.viewport,image.width,image.height)
                    self.draw_modules()
                    m=self.meta
                    self.status.set(f"{m['width']:,} × {m['height']:,} px | {m['crs']} | 픽셀 간격 {m['resolution']} (좌표계 단위) | 2D RGB · 고도 정보 없음")
            if self.pending:self.start()
        self.window.after(100,self.poll)

    def draw_modules(self):
        self.canvas.delete('module')
        if not self.show_modules.get() or not self.display:return
        (x,y,w,h),iw,ih=self.display
        ox=(self.canvas.winfo_width()-iw)/2;oy=(self.canvas.winfo_height()-ih)/2
        for m in self.modules:
            cx,cy=m['center']
            if not (x-120<=cx<=x+w+120 and y-200<=cy<=y+h+200):continue
            coords=[v for px,py in m['polygon'] for v in (ox+(px-x)*iw/w,oy+(py-y)*ih/h)]
            color='#ffffff' if m['id']==self.selected else ('#ffad32' if m['status']=='review' else '#00ff91')
            self.canvas.create_polygon(coords,fill='',outline=color,width=2 if w<4000 else 1,tags='module')
            if w<2200:
                self.canvas.create_text(ox+(cx-x)*iw/w,oy+(cy-y)*ih/h,text=m['id'].split('-')[-1],fill='white',font=('Consolas',9),tags='module')

    def close(self):
        self.closed=True;self.window.destroy()


def open_ortho(parent):
    from tkinter import filedialog, messagebox
    try:
        import rasterio
        from PIL import ImageTk
    except ImportError:
        messagebox.showerror('패키지 필요','RGB 지도에는 rasterio와 Pillow가 필요합니다.');return
    path=filedialog.askopenfilename(title='드론 RGB GeoTIFF 선택',filetypes=[('GeoTIFF','*.tif *.tiff')])
    if path:OrthoWindow(parent,path)

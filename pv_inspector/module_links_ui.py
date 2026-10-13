"""Read-only observation lookup for a selected drawing module."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser


def show_module_results(parent, data, module_id):
    win = tk.Toplevel(parent); win.title('3D 모듈 분석 연결 · ' + module_id)
    win.geometry('1050x560')
    module = data['modules'].get(module_id, {'records': []})
    records = [data['records'][i] for i in module['records']]
    ttk.Label(win, text=module_id + f' · 연결 관측 {len(records)}건', padding=12).pack(anchor='w')
    ttk.Label(win, text='후보 연결은 확정 진단이 아닙니다. 연결 없음도 정상 판정을 뜻하지 않습니다.\n' + '\n'.join(data['warnings']),
              wraplength=1000, padding=10).pack(anchor='w')
    columns = ('status', 'image', 'module', 'final', 'max', 'delta')
    tree = ttk.Treeview(win, columns=columns, show='headings', selectmode='browse')
    for key, title, width in [('status','연결 상태',150),('image','촬영 ID',300),('module','관측 모듈',85),
                              ('final','분석 판정',85),('max','최고 °C',85),('delta','ΔT °C',85)]:
        tree.heading(key, text=title); tree.column(key, width=width)
    tree.pack(fill='both', expand=True, padx=12)
    for i, r in enumerate(records):
        fmt = lambda v: '' if v is None else f'{float(v):.2f}'
        status = {'historical_candidate':'기존 후보 · 미확정','confirmed':'영상 연결 확인','unmatched':'미연결','rejected':'연결 기각'}.get(r['link_status'],r['link_status'])
        label = {'normal':'정상','attention':'주의','abnormal':'이상'}.get(r['final'],r['final'])
        tree.insert('', 'end', iid=str(i), values=(status, r['image_id'], r['module_id'], label, fmt(r.get('max_temp')), fmt(r.get('delta_temp'))))
    def open_asset(key):
        selection = tree.selection()
        if not selection: return
        value = records[int(selection[0])].get(key)
        if not value or not Path(value).is_file():
            messagebox.showinfo('원본 파일 없음', '기록된 원본 경로에 파일이 없습니다. 원본 자료를 복원해 주세요.', parent=win); return
        webbrowser.open(Path(value).resolve().as_uri())
    buttons = ttk.Frame(win, padding=12); buttons.pack(fill='x')
    ttk.Button(buttons, text='선택 관측 크롭', command=lambda: open_asset('crop')).pack(side='left')
    ttk.Button(buttons, text='선택 관측 열화상', command=lambda: open_asset('thermal')).pack(side='left', padx=8)

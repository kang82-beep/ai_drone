"""Path settings editor; preserves analysis settings outside this form."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    ('INPUT_IMG_DIR', '드론 이미지 폴더 *', 'directory'),
    ('OUTPUT_ROOT', '결과 폴더 * (새 폴더 또는 빈 폴더)', 'output'),
    ('MASKRCNN_WEIGHTS', '모듈 검출 모델 * (.pth)', 'model'),
    ('CLF_WEIGHTS', '이상 분류 모델 * (.pth)', 'model'),
    ('DJI_IRP_EXE', 'DJI SDK 실행 파일 * (dji_irp.exe)', 'exe'),
    ('BLENDER_EXE', 'Blender 실행 파일 (선택)', 'exe'),
    ('BLENDER_SCENE', '분석 연결 Blender 파일 (선택)', 'blend'),
    ('MRK_CSV_PATH', 'MRK 위치 보정 자료 (선택)', 'file'),
    ('NAV_CSV_PATH', 'NAV 보조 자료 (선택)', 'file'),
    ('REGION_GEOJSON_PATH', '구역 경계 GeoJSON (선택)', 'json'),
    ('MODULE_CATALOG_JSON', '설비 카탈로그 JSON (선택)', 'json'),
    ('ORTHO_TIF_PATH', '정사영상 GeoTIFF (선택)', 'tif'),
]


def read_settings(path):
    values = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(values, dict):
        raise ValueError('설정 파일은 JSON 객체여야 합니다.')
    return values


def prepare_settings(original, edits):
    values = dict(original)
    errors = []
    for key, label, kind in FIELDS:
        value = edits.get(key, '').strip().strip('"')
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            path = path.resolve()
            value = str(path)
            if kind == 'directory' and not path.is_dir():
                errors.append(f'{label}: 폴더가 없습니다.')
            elif kind == 'output':
                if path.exists() and not path.is_dir():
                    errors.append(f'{label}: 폴더 경로를 지정하세요.')
            elif kind not in ('directory', 'output') and not path.is_file():
                errors.append(f'{label}: 파일이 없습니다.')
        elif '*' in label:
            errors.append(f'{label}: 경로를 지정하세요.')
        values[key] = value
    for flag, key, label in [('SNAP_ENABLE', 'MODULE_CATALOG_JSON', '설비 카탈로그'),
                             ('USE_ORTHO_TIF', 'ORTHO_TIF_PATH', '정사영상')]:
        values[flag] = bool(edits.get(flag, False))
        if values[flag] and not values[key]:
            errors.append(f'{label} 사용을 선택했으므로 파일을 지정하세요.')
    values['VWORLD_API_KEY'] = edits.get('VWORLD_API_KEY', '').strip()
    if errors:
        raise ValueError('\n'.join(errors))
    return values


def save_settings(path, values):
    """Replace only after a complete write, so a failed save keeps the old file."""
    path = Path(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         suffix='.tmp', delete=False) as stream:
            temp = Path(stream.name)
            json.dump(values, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


class SettingsDialog:
    def __init__(self, parent, path, input_path, output_path, on_saved):
        self.path = Path(path).resolve()
        self.original = read_settings(self.path) if self.path.is_file() else {}
        self.on_saved = on_saved
        self.window = tk.Toplevel(parent)
        self.window.title('경로 및 지도 설정')
        self.window.geometry('920x700')
        self.window.minsize(740, 500)
        self.window.transient(parent)
        self.window.grab_set()
        canvas = tk.Canvas(self.window, highlightthickness=0)
        scroll = ttk.Scrollbar(self.window, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        box = ttk.Frame(canvas, padding=16)
        content = canvas.create_window((0, 0), window=box, anchor='nw')
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(content, width=e.width))
        box.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        box.columnconfigure(1, weight=1)
        ttk.Label(box, text='필수 경로(*)를 선택하세요. 선택 항목은 사용하지 않으면 비워두세요.').grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))
        self.variables = {}
        overrides = {'INPUT_IMG_DIR': input_path, 'OUTPUT_ROOT': output_path}
        for row, (key, label, kind) in enumerate(FIELDS, 1):
            value = overrides.get(key) or self.original.get(key, '')
            var = tk.StringVar(value=value)
            self.variables[key] = var
            ttk.Label(box, text=label).grid(row=row, column=0, sticky='w', padx=(0, 10))
            ttk.Entry(box, textvariable=var).grid(row=row, column=1, sticky='ew', pady=6)
            ttk.Button(box, text='찾아보기', command=lambda v=var, k=kind: self.browse(v, k)).grid(row=row, column=2, padx=(8, 0))
        row = len(FIELDS) + 1
        for flag, label in [('SNAP_ENABLE', '설비 카탈로그로 위치 연결 사용'), ('USE_ORTHO_TIF', '정사영상 배경 사용')]:
            var = tk.BooleanVar(value=self.original.get(flag, False))
            self.variables[flag] = var
            ttk.Checkbutton(box, text=label, variable=var).grid(row=row, column=1, sticky='w')
            row += 1
        keyvar = tk.StringVar(value=self.original.get('VWORLD_API_KEY', ''))
        self.variables['VWORLD_API_KEY'] = keyvar
        ttk.Label(box, text='브이월드 지도 인증키').grid(row=row, column=0, sticky='w')
        ttk.Entry(box, textvariable=keyvar, show='*').grid(row=row, column=1, sticky='ew', pady=8)
        row += 1
        ttk.Label(box, text='결과 폴더는 직접 새 경로를 입력할 수 있습니다. 기존 결과가 있으면 분석 실행이 차단됩니다.\n저장 후 입력 검사를 실행하세요. 지도 키 변경은 새로 생성하는 보고서부터 반영됩니다.', wraplength=820).grid(row=row, column=0, columnspan=3, sticky='w', pady=10)
        row += 1
        buttons = ttk.Frame(box)
        buttons.grid(row=row, column=0, columnspan=3, sticky='e')
        ttk.Button(buttons, text='취소', command=self.window.destroy).pack(side='left', padx=5)
        ttk.Button(buttons, text='다른 이름으로 저장', command=lambda: self.save(True)).pack(side='left', padx=5)
        ttk.Button(buttons, text='저장 및 적용', command=self.save).pack(side='left', padx=5)

    def browse(self, var, kind):
        if kind in ('directory', 'output'):
            path = filedialog.askdirectory(parent=self.window, mustexist=(kind != 'output'))
        else:
            filters = {'model': [('모델 가중치', '*.pth *.pt')], 'exe': [('실행 파일', '*.exe')],
                       'json': [('JSON / GeoJSON', '*.json *.geojson')], 'tif': [('GeoTIFF', '*.tif *.tiff')],
                       'blend': [('Blender 장면', '*.blend')]}
            path = filedialog.askopenfilename(parent=self.window, filetypes=filters.get(kind, []) + [('모든 파일', '*.*')])
        if path:
            var.set(path)

    def save(self, save_as=False):
        try:
            # Re-read to preserve unrelated edits made since opening the dialog.
            original = read_settings(self.path) if self.path.is_file() else self.original
            values = prepare_settings(original, {key: var.get() for key, var in self.variables.items()})
            destination = str(self.path)
            if save_as:
                destination = filedialog.asksaveasfilename(parent=self.window, defaultextension='.json',
                    initialdir=str(self.path.parent), initialfile='config.site.json', filetypes=[('JSON 설정', '*.json')])
                if not destination:
                    return
            save_settings(destination, values)
            self.on_saved(str(Path(destination).resolve()), values)
            self.window.destroy()
        except (OSError, ValueError) as exc:
            messagebox.showerror('설정 저장 실패', str(exc), parent=self.window)

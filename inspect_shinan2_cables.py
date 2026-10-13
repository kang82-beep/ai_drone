from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tmp/pdfdeps'))
import fitz
OUT=ROOT/'results/shinan2_cables';OUT.mkdir(exist_ok=True)
doc=fitz.open(next(Path('C:/3d').glob('*.pdf')))
for number in [3,12,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,42,43,44,64]:
    page=doc[number-1]
    path=OUT/f'p{number:02d}.png'
    if not path.exists():page.get_pixmap(matrix=fitz.Matrix(3600/page.rect.width,3600/page.rect.width),alpha=False).save(path)
print('Cable references rendered.')

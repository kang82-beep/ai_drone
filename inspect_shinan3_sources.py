from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parent/'tmp/pdfdeps'))
import fitz

ROOT=Path('C:/3호기준공도서CD')
OUT=Path('results/shinan3_source');OUT.mkdir(parents=True,exist_ok=True)
summary=[]
for f in ROOT.rglob('*.pdf'):
    d=fitz.open(f)
    tag='electrical' if f.name=='신안태양광 3차 도면.pdf' else ('civil' if f.name=='토목 건축 도면.pdf' else f.stem)
    pages=[p.get_text() for p in d]
    (OUT/(tag+'.txt')).write_text('\n'.join('PAGE '+str(i+1)+'\n'+t for i,t in enumerate(pages)),encoding='utf-8')
    summary.append({'path':str(f),'tag':tag,'pages':len(d),'text_chars':sum(map(len,pages))})
    if tag in ('electrical','civil'):
        (OUT/(tag+'_index.txt')).write_text('\n'.join(str(i+1)+' | '+t[-700:].replace('\n',' ') for i,t in enumerate(pages)),encoding='utf-8')
(OUT/'inventory.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))

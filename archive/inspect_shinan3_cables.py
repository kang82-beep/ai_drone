from pathlib import Path
import sys,subprocess,json,collections
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tmp/pdfdeps'))
import ezdxf,fitz
OUT=ROOT/'results/shinan3_cables';OUT.mkdir(exist_ok=True)
CAD=Path('C:/3호기준공도서CD/전기/1. 도면/CAD')
codes=sys.argv[1:] or ['10010','11220','11230','11240','11250','11310','11320','12210','12110','10210','10110']
for code in codes:
    src=next(CAD.glob('3SA-E-'+code+'_*.dwg'));dst=OUT/(src.stem+'.dxf')
    if not dst.exists():
        result=subprocess.run([str(ROOT/'tmp/libredwg/dwg2dxf.exe'),'-y','-o',str(dst),str(src)],capture_output=True)
        (OUT/(src.stem+'.log')).write_bytes(result.stdout+result.stderr)
        assert dst.exists(),src
    doc=ezdxf.readfile(dst);m=doc.modelspace()
    texts=[]
    for e in m:
        if e.dxftype() in ('TEXT','MTEXT'):
            texts.append({'text':e.dxf.text if e.dxftype()=='TEXT' else e.plain_text(),'xy':list(e.dxf.insert),'layer':e.dxf.layer,'handle':e.dxf.handle})
    summary={'file':src.name,'units':doc.units,'layers':dict(collections.Counter(e.dxf.layer for e in m)),'types':dict(collections.Counter(e.dxftype() for e in m)), 'inserts':dict(collections.Counter(e.dxf.name for e in m.query('INSERT'))),'texts':texts}
    (OUT/(src.stem+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(src.stem,summary['types'],list(summary['inserts'].items())[:15],flush=True)

"""Export actual module solids to an interoperable OBJ, without terrain assumptions."""
from pathlib import Path
from pv_inspector.site_model import load_site,strip_modules


def main():
    data=load_site();out=Path(__file__).resolve().parent/'results'/'drawing_site'
    index=1
    with (out/'plant_modules.obj').open('w',encoding='utf-8') as f:
        f.write('# Drawing-derived module solids; units=m; local coordinates; clearance unknown\n')
        for strip in data['rows']:
            for m in strip_modules(strip):
                f.write(f"o {m['id']}\n")
                for x,y,z in m['vertices']:f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
                for face in [(0,1,2,3),(7,6,5,4),(4,5,1,0),(5,6,2,1),(6,7,3,2),(7,4,0,3)]:
                    f.write('f '+' '.join(str(index+i) for i in face)+'\n')
                index+=8
    print(f"Exported {(index-1)//8} module objects")


if __name__=='__main__':main()

"""Prepare or open the A-zone RGB/thermal review workbench."""
import argparse
from pathlib import Path
from pv_inspector.module_review import OUT, build_bundle, ReviewSession


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--export',action='store_true')
    parser.add_argument('--no-auto',action='store_true')
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    if args.prepare:
        data=build_bundle(output=args.output,auto=not args.no_auto)
        print('Prepared',len(data['cases']),'cases; dataset',data['dataset_id'])
    if args.export:print(ReviewSession(args.output).export())
    if not args.prepare and not args.export:
        import tkinter as tk
        from pv_inspector.module_review_ui import ModuleReviewWindow
        root=tk.Tk();ModuleReviewWindow(root,args.output);root.mainloop()


if __name__=='__main__':main()

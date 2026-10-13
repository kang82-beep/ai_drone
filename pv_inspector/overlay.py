"""PV inspection: overlay."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFile, ExifTags
import os, re, json, time, math, shutil, subprocess, io
from .files import ensure_dir

def draw_overlay(base_img_path: str, overlays: List[Dict], save_path: str):
    im = Image.open(base_img_path).convert('RGB')
    draw = ImageDraw.Draw(im, 'RGBA')

    def poly(points, outline, fill):
        draw.polygon(points, outline=outline, fill=fill)

    def rect(b, outline, fill):
        x1, y1, x2, y2 = b
        draw.rectangle([x1, y1, x2, y2], outline=outline, fill=fill, width=3)

    for it in overlays:
        label = it.get('label')
        if label == 'abnormal':
            color = (255, 0, 0, config.BOX_ALPHA_ABNORMAL)
            outline = (255, 0, 0, config.OUTLINE_ALPHA)
        else:
            color = (255, 165, 0, config.BOX_ALPHA_ATTENTION)
            outline = (255, 165, 0, config.OUTLINE_ALPHA)

        if it.get('quad'):
            pts = [(float(x), float(y)) for x, y in it['quad']]
            poly(pts, outline=outline, fill=color)
            tx, ty = pts[0]
        elif it.get('bbox'):
            rect(it['bbox'], outline=outline, fill=color)
            tx, ty = it['bbox'][0], it['bbox'][1]
        else:
            continue

        tag = it.get('tag', '')
        if tag:
            try:
                tw = draw.textlength(tag)
            except Exception:
                tw = 8 * len(tag)
            th = 12
            draw.rectangle([tx+1, ty+1, tx+6+tw, ty+6+th], fill=(0,0,0,140))
            draw.text((tx + 3, ty + 3), tag, fill=config.TEXT_FILL)

    ensure_dir(os.path.dirname(save_path))
    im.save(save_path, 'JPEG', quality=92)


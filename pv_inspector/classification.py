"""PV inspection: classification."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageDraw, ImageFile, ExifTags
from torchvision import models, transforms, datasets
from torch import nn
import numpy as np
import os, re, json, time, math, shutil, subprocess, io
import pandas as pd
import torch
from tqdm import tqdm
from .files import ensure_dir, ensure_unique_path

def classify_and_sort(
    clf: nn.Module, class_order: List[str], crop_paths: List[str], out_base: str,
    tf, tf_flip, device, move_files=False,
    delta_lookup: Optional[Dict[str,float]] = None, hotspot_lookup: Optional[Dict[str,bool]] = None,
    neighbor_lookup: Optional[Dict[str,bool]] = None
) -> pd.DataFrame:
    ensure_dir(out_base)
    out_name = (lambda en: config.KO_LABEL_MAP.get(en, en)) if config.USE_KO_LABELS else (lambda en: en)
    normal_top = os.path.join(out_base, out_name("normal")); abnormal_top = os.path.join(out_base, out_name("abnormal"))
    ensure_dir(normal_top); ensure_dir(abnormal_top)
    normal_sub_normal = os.path.join(normal_top, out_name("normal")); ensure_dir(normal_sub_normal)
    normal_sub_attention = os.path.join(normal_top, out_name("attention")); ensure_dir(normal_sub_attention)

    rows = []
    loader = datasets.folder.default_loader
    def to_tensor_list(pil_list, transform):
        xs = [transform(im) for im in pil_list]
        return torch.stack(xs, dim=0)
    i_abn = class_order.index("abnormal"); i_att = class_order.index("attention"); i_nor = class_order.index("normal")

    with torch.no_grad():
        for i in tqdm(range(0, len(crop_paths), config.BATCH_SIZE), desc="[분류]"):
            batch_paths = crop_paths[i:i+config.BATCH_SIZE]
            batch_imgs = []
            for p in batch_paths:
                try: batch_imgs.append(loader(p))
                except Exception as exc: raise RuntimeError(f"Cannot read crop: {p}") from exc
            x = to_tensor_list(batch_imgs, tf).to(device)
            logits = clf(x); probs = torch.softmax(logits, dim=1)
            if config.USE_TTA:
                x2 = to_tensor_list(batch_imgs, tf_flip).to(device)
                probs = (probs + torch.softmax(clf(x2), dim=1)) / 2.0
            probs = probs.cpu().numpy()
            if probs.shape != (len(batch_paths), len(class_order)) or not np.isfinite(probs).all():
                raise ValueError("Classifier produced invalid probabilities; refusing to save a diagnosis")
            for p, pr in zip(batch_paths, probs):
                p_abn = float(pr[i_abn]); p_att = float(pr[i_att]); p_nor = float(pr[i_nor])
                if config.USE_HIERARCHICAL_DECISION:
                    if p_abn >= config.TH_ABNORMAL:
                        final_name = "abnormal"; final_bin = "abnormal"; final_sub = None
                        dst_dir = abnormal_top
                    else:
                        denom = max(p_att + p_nor, 1e-8)
                        p_att_cond = p_att / denom
                        if p_att_cond >= config.TH_ATT_WITHIN:
                            final_name = "attention"; final_bin = "normal"; final_sub = "attention"; dst_dir = normal_sub_attention
                        else:
                            final_name = "normal"; final_bin = "normal"; final_sub = "normal"; dst_dir = normal_sub_normal
                else:
                    pred_idx = int(np.argmax(pr))
                    final_name = class_order[pred_idx]
                    final_bin = "abnormal" if final_name == "abnormal" else "normal"
                    final_sub = final_name if final_bin == "normal" else None
                    dst_dir = {"abnormal": abnormal_top, "attention": normal_sub_attention, "normal": normal_sub_normal}.get(final_name, normal_sub_normal)

                model_decision = final_name
                decision_reasons = ["hierarchical" if config.USE_HIERARCHICAL_DECISION else "argmax"]
                dt = delta_lookup.get(p) if delta_lookup is not None else None
                hs = hotspot_lookup.get(p) if hotspot_lookup is not None else False
                nb = bool(neighbor_lookup.get(p)) if neighbor_lookup is not None else False
                if final_name == "normal":
                    if (config.DELTA_ATT_ENABLE and dt is not None and dt >= config.DELTA_ATT_TH) or hs or nb:
                        if config.DELTA_ATT_ENABLE and dt is not None and dt >= config.DELTA_ATT_TH:
                            decision_reasons.append("delta_temperature")
                        if hs:
                            decision_reasons.append("hotspot")
                        if nb:
                            decision_reasons.append("neighbor_delta")
                        final_name = "attention"; final_bin = "normal"; final_sub = "attention"; dst_dir = normal_sub_attention

                os.makedirs(dst_dir, exist_ok=True)
                base = os.path.basename(p); dst_path = ensure_unique_path(os.path.join(dst_dir, base))
                try:
                    if move_files: shutil.move(p, dst_path)
                    else: shutil.copy2(p, dst_path)
                except Exception as exc: raise RuntimeError(f"Cannot save classified crop: {p}") from exc

                rows.append({
                    "crop_path": p, "dst_path": dst_path,
                    "final": final_name, "final_bin": final_bin, "final_sub": final_sub,
                    "model_decision": model_decision,
                    "decision_reason": ";".join(decision_reasons),
                    "prob_abnormal": p_abn, "prob_attention": p_att, "prob_normal": p_nor,
                    "delta_temp": dt, "hotspot_gate": bool(hs),
                })
    return pd.DataFrame(rows)


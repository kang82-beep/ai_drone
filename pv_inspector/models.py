"""PV inspection: models."""
from __future__ import annotations
from . import config
from torchvision import models, transforms, datasets
from torch import nn
import torchvision

def get_maskrcnn_model(num_classes=2):
    model = torchvision.models.detection.maskrcnn_resnet50_fpn(weights=None, weights_backbone=None)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    hidden_layer = 256
    model.roi_heads.mask_predictor = torchvision.models.detection.mask_rcnn.MaskRCNNPredictor(
        in_features_mask, hidden_layer, num_classes
    )
    return model


def build_effb3(num_classes: int):
    m = models.efficientnet_b3(weights=None)
    in_f = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_f, num_classes)
    return m


def make_transforms(img_size: int, use_gray: bool):
    base = []
    if use_gray:
        base.append(transforms.Grayscale(num_output_channels=3))
        mean, std = [0.5]*3, [0.5]*3
    else:
        mean, std = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]
    tf = transforms.Compose([
        transforms.Resize(int(img_size * 1.05)),
        transforms.CenterCrop(img_size),
        *base,
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    tf_flip = transforms.Compose([
        transforms.Resize(int(img_size * 1.05)),
        transforms.CenterCrop(img_size),
        transforms.RandomHorizontalFlip(p=1.0),
        *base,
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])
    return tf, tf_flip


"""Small fixed-shape CNNs using installed torchvision only; normalization embedded."""
import hashlib
import json
from pathlib import Path
import torch
from torchvision import models

LABELS = Path('artifacts/multidomain/training-labels.json')
SOURCE = Path('artifacts/forms/sources')


class Classifier(torch.nn.Module):
    def __init__(self, backbone):
        super().__init__(); self.backbone=backbone
        self.register_buffer('mean',torch.tensor([.485,.456,.406]).reshape(1,3,1,1))
        self.register_buffer('std',torch.tensor([.229,.224,.225]).reshape(1,3,1,1))
    def forward(self,x): return self.backbone((x-self.mean)/self.std)


def make_model(arch, pretrained=False):
    if arch=='baseline':
        m=models.densenet121(num_classes=len(json.loads(LABELS.read_text(encoding="utf-8"))))
        file=SOURCE/'BiernyVR--pokemon-classifier-mobilenetv3/pokemon_densenet121_best.pth'
        assert hashlib.sha256(file.read_bytes()).hexdigest()=='58e54044ed3ff747a26717313570e4c0b0f2204e7bdfcef7351d011861b2defe'
        state=torch.load(file,map_location='cpu',weights_only=True)
        m.load_state_dict(state.get('model_state_dict',state),strict=True)
    elif arch=='mobilenet_v3_large':
        m=models.mobilenet_v3_large()
        if pretrained:
            state=torch.load(SOURCE/'torchvision/mobilenet_v3_large-5c1a4163.pth',map_location='cpu',weights_only=True)
            m.load_state_dict(state,strict=True)
        m.classifier[-1]=torch.nn.Linear(m.classifier[-1].in_features,len(json.loads(LABELS.read_text(encoding="utf-8"))))
    elif arch=='efficientnet_b0':
        m=models.efficientnet_b0()
        if pretrained:
            state=torch.load(SOURCE/'torchvision/efficientnet_b0_rwightman-7f5810bc.pth',map_location='cpu',weights_only=True)
            m.load_state_dict(state,strict=True)
        m.classifier[-1]=torch.nn.Linear(m.classifier[-1].in_features,len(json.loads(LABELS.read_text(encoding="utf-8"))))
    else: raise ValueError(arch)
    return Classifier(m)


def same_head(first,second):
    return [(p['id'],p['name']) for p in first]==[(p['id'],p['name']) for p in second]


def load_checkpoint(file,allow_metadata_update=False):
    checkpoint=torch.load(file,map_location='cpu',weights_only=True)
    model=make_model(checkpoint['config']['arch'])
    model.load_state_dict(checkpoint['model'],strict=True)
    current=json.loads(LABELS.read_text(encoding='utf-8'))
    if checkpoint['labels']!=current and not (allow_metadata_update and same_head(checkpoint['labels'],current)):
        raise ValueError('checkpoint labels mismatch')
    return model,checkpoint

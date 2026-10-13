"""Atomic checkpoints for a single input/config/code snapshot."""
import hashlib
import json
from pathlib import Path
import os


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    os.replace(temp,path)


def prepare_run(config):
    root=Path(config.OUTPUT_ROOT)
    settings={k:v for k,v in vars(config).items() if k.isupper() and k not in ('RESUME_RUN',)}
    settings={k:sorted(v) if isinstance(v,set) else v for k,v in settings.items()}
    paths=sorted(Path(config.INPUT_IMG_DIR).rglob('*'))
    paths += [Path(config.MASKRCNN_WEIGHTS),Path(config.CLF_WEIGHTS),Path(config.DJI_IRP_EXE)]
    signature=[(str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in paths if p.is_file()]
    code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))}
    payload=dict(settings=settings,inputs=signature,code=code)
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    manifest=root/'run_manifest.json'
    if root.exists() and any(root.iterdir()):
        if not config.RESUME_RUN or not manifest.exists():
            raise FileExistsError('Choose an empty output directory or enable RESUME_RUN for an existing run')
        previous=json.loads(manifest.read_text(encoding='utf-8'))
        if previous['signature']!=digest:
            raise ValueError('Inputs, settings, or code changed; use a new output directory')
    else:
        atomic_json(manifest,dict(signature=digest,**payload))
    return root/'checkpoints'

"""Check the app's opaque pixel-sprite path without changing the frozen policy."""
import json
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image
import torch
from model import load_checkpoint


def main():
    root = Path('artifacts/multidomain')
    policy = json.loads((root / 'recognition-manifest.json').read_text())
    selection = json.loads((root / 'selection.json').read_text())
    assert hashlib.sha256((root/'selected.pt').read_bytes()).hexdigest() == policy['checkpointSHA256'] == selection['checkpoint_sha256']
    assert hashlib.sha256((root/'training-labels.json').read_bytes()).hexdigest() == policy['labelsSHA256']
    assert hashlib.sha256((root/'data/manifest.jsonl').read_bytes()).hexdigest() == policy['trainingManifestSHA256'] == selection['manifest_sha256']
    assert policy['confidenceThreshold'] == selection['confidenceThreshold'] and policy['logitMargin'] == selection['logitMargin']
    labels = json.loads((root / 'training-labels.json').read_text(encoding='utf-8'))
    entries = json.loads(Path('iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    entries += json.loads(Path('iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    ids = [25, 6, 65, 83, 86, 98, 129, 152, 248, 384, 445, 658, 700, 778, 906, 1000, 1025,
           110206, 110083, 110082, 110314, 110315, 110362, 110363]
    catalog = {p['id']: p for p in entries}
    images = []
    for number in ids:
        entry = catalog[number]
        asset = entry.get('spriteAsset', f'pokemon-{number:03d}')
        path = Path('iDex/Resources/PokemonSprites.xcassets') / (asset + '.imageset/sprite.png')
        rgba = Image.open(path).convert('RGBA')
        rgb = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
        rgb = rgb.resize((384, 384), Image.Resampling.NEAREST).resize((224, 224), Image.Resampling.BILINEAR)
        images.append(torch.from_numpy(np.asarray(rgb).copy()).permute(2, 0, 1).float()/255)
    fixture_ids = list(ids)
    for value in [0, 127, 255]:
        fixture_ids.append(f'solid-{value}')
        images.append(torch.full((3,224,224),value/255.))
    fixture_ids.append('noise')
    noise = np.random.default_rng(20261101).integers(0,256,(3,224,224),dtype=np.uint8)
    images.append(torch.from_numpy(noise).float()/255.)
    model, _ = load_checkpoint(root / 'selected.pt')
    model.eval()
    torch.set_num_threads(6)
    with torch.inference_mode():
        logits = model(torch.stack(images))
    results = []
    for number, values in zip(fixture_ids, logits):
        scores, indexes = values.topk(3)
        confidence = values.softmax(0)[indexes[0]].item()
        margin = (scores[0] - scores[1]).item()
        predicted = labels[indexes[0].item()]['id']
        accepted = predicted in policy['confirmedEntryIDs'] and confidence >= policy['confidenceThreshold'] and margin >= policy['logitMargin']
        passed = predicted == number and accepted if isinstance(number,int) else not accepted
        results.append(dict(entryID=number, topEntryID=predicted, correct=predicted == number,
                            confidence=confidence, margin=margin, accepted=accepted,
                            passed=passed, top3=[labels[i]['id'] for i in indexes.tolist()]))
    report = dict(passed=all(row['passed'] for row in results), fixtures=results,
                  checkpointSHA256=policy['checkpointSHA256'],
                  role='Predeclared app integration fixtures, not generalization accuracy.')
    (root / 'reports').mkdir(parents=True, exist_ok=True)
    (root / 'reports/sprite-smoke.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    if not report['passed']:
        raise ValueError('Frozen model failed app sprite/blank integration; policy was not changed')


if __name__ == '__main__':
    main()

"""Check the app's opaque pixel-sprite path without changing the frozen policy."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from PIL import Image
import torch
from model import load_checkpoint


def main():
    root = Path('artifacts/forms')
    policy = json.loads((root / 'recognition-manifest.json').read_text())
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
    model, _ = load_checkpoint(root / 'selected.pt')
    model.eval()
    torch.set_num_threads(6)
    with torch.inference_mode():
        logits = model(torch.stack(images))
    results = []
    for number, values in zip(ids, logits):
        scores, indexes = values.topk(3)
        confidence = values.softmax(0)[indexes[0]].item()
        margin = (scores[0] - scores[1]).item()
        predicted = labels[indexes[0].item()]['id']
        accepted = predicted in policy['confirmedEntryIDs'] and confidence >= policy['confidenceThreshold'] and margin >= policy['logitMargin']
        results.append(dict(entryID=number, topEntryID=predicted, correct=predicted == number,
                            confidence=confidence, margin=margin, accepted=accepted,
                            top3=[labels[i]['id'] for i in indexes.tolist()]))
    (root / 'reports/sprite-smoke.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results))


if __name__ == '__main__':
    main()

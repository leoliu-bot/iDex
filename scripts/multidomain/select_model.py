"""Freeze a checkpoint on validation, then calibrate acceptance without test access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import torch
import metrics

ROOT = Path('artifacts/multidomain')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def choose(paths):
    candidates = []
    manifest = ROOT/'data/manifest.jsonl'
    expected_manifest = sha(manifest)
    labels = json.loads((ROOT/'training-labels.json').read_text(encoding='utf-8'))
    for path in paths:
        state = torch.load(path, map_location='cpu', weights_only=True)
        if state['manifest_sha256'] != expected_manifest or state['labels'] != labels:
            raise ValueError('Selection candidates must match the expanded frozen manifest and label order')
        if 'selection_score' not in state.get('validation', {}):
            raise ValueError('Candidate lacks the predeclared balanced validation score')
        candidates.append((state['best_val'], -path.stat().st_size, str(path), state))
    _, _, name, state = max(candidates, key=lambda x: x[:3])
    destination = ROOT / 'selected.pt'
    if destination.exists():
        raise ValueError('Candidate already frozen; use a fresh artifact root.')
    shutil.copy2(name, destination)
    record = {'selectedFrom': name, 'checkpoint_sha256': sha(destination),
              'manifest_sha256': state['manifest_sha256'], 'arch': state['config']['arch'],
              'size': state['config']['size'], 'classes': len(state['labels']),
              'validationTop1': state['validation']['top1'], 'validationScore': state['best_val'],
              'validationDetails': state['validation'],
              'selectionRule': 'Maximum validation composite: 0.5 class-macro recall + 0.5 equal domain mean of source-group accuracy (domains with >=30 images and >=5 groups); no test predictions inspected.'}
    (ROOT / 'candidate.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


def calibrate(predictions):
    if (ROOT / 'selection.json').exists():
        raise ValueError('Selection already frozen.')
    record = json.loads((ROOT / 'candidate.json').read_text())
    if sha(ROOT / 'selected.pt') != record['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    manifest_sha = sha(ROOT / 'data/manifest.jsonl')
    labels_sha = sha(ROOT / 'training-labels.json')
    if record['manifest_sha256'] != manifest_sha:
        raise ValueError('Frozen candidate manifest changed')
    metadata = json.loads(predictions.with_suffix('.metadata.json').read_text())
    expected = {'checkpoint_sha256': record['checkpoint_sha256'],
                'manifest_sha256': manifest_sha, 'labels_sha256': labels_sha,
                'predictions_sha256': sha(predictions)}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f'Prediction {key} mismatch')
    rows = metrics.load_rows(predictions)
    if any(row['split'] not in ['val', 'ood_val'] for row in rows):
        raise ValueError('Calibration may access validation only')
    if metadata.get('rows') != len(rows):
        raise ValueError('Prediction row count mismatch')
    labels = json.loads((ROOT / 'training-labels.json').read_text(encoding='utf-8'))
    prepared = metrics._prepare(rows, labels, .25, .5, 1., 15)
    logits = np.asarray([row['logits'] for row in rows])
    top = np.partition(logits, -2, axis=1)[:, -2:]
    margins = top.max(axis=1) - top.min(axis=1)
    known, correct = prepared['known'], prepared['correct']
    choices = []
    for confidence in [.25, .35, .45, .5, .6, .7, .8, .9, .95, .98, .99]:
        for margin in [.5, 1., 1.5, 2., 3., 4.]:
            accepted = prepared['confirmable'] & (prepared['confidence'] >= confidence) & (margins >= margin)
            n = int(accepted.sum())
            accuracy = float((accepted & correct).sum() / n) if n else 0.
            far = float((accepted & ~known).sum() / (~known).sum()) if (~known).any() else 1.
            count = int((accepted & known).sum())
            if count >= 30 and accuracy >= .97 and far <= .05:
                choices.append((count, accuracy, -confidence, -margin))
    if not choices:
        raise ValueError('No policy meets the predeclared validation gate; do not publish a model.')
    _, _, confidence, margin = max(choices)
    confidence, margin = -confidence, -margin
    record.update(confidenceThreshold=confidence, logitMargin=margin,
                  calibrationRule='Validation only: >=97% accepted accuracy, <=5% natural-negative FAR, then maximum known acceptance; small public diagnostic, not camera certification.')
    contract = {'modelResource': 'NationalClassifier', 'classCount': len(labels), 'inputSize': record['size'],
                'confidenceThreshold': confidence, 'logitMargin': margin,
                'checkpointSHA256': record['checkpoint_sha256'], 'labelsSHA256': labels_sha,
                'confirmedEntryIDs': [label['id'] for label in labels if label.get('confirmed', True)]}
    report = metrics.metrics(rows, labels, confidence, margin, bootstrap_replicates=500)
    # Finish metric computation and JSON validation before publishing any policy.
    # Each replacement is atomic; selection.json is the final commit marker.
    artifacts = [(ROOT / 'reports/validation.json', report),
                 (ROOT / 'recognition-manifest.json', contract),
                 (ROOT / 'selection.json', record)]
    rendered = [(path, json.dumps(value, indent=2, allow_nan=False) + '\n')
                for path, value in artifacts]
    (ROOT / 'reports').mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        for path, payload in rendered:
            temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.partial')
            staged.append((temporary, path))
            temporary.write_text(payload, encoding='utf-8', newline='\n')
        for temporary, path in staged:
            temporary.replace(path)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    print(json.dumps(contract), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['choose', 'calibrate'])
    parser.add_argument('--checkpoint', type=Path, action='append')
    parser.add_argument('--predictions', type=Path)
    args = parser.parse_args()
    if args.stage == 'choose':
        choose(args.checkpoint)
    else:
        calibrate(args.predictions)

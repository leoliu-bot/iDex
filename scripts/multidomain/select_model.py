"""Freeze a checkpoint on validation, then calibrate acceptance without test access."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import torch
import metrics

ROOT = Path('artifacts/multidomain')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def choose(paths):
    candidates = []
    for path in paths:
        state = torch.load(path, map_location='cpu', weights_only=True)
        candidates.append((state['best_val'], -path.stat().st_size, str(path), state))
    _, _, name, state = max(candidates, key=lambda x: x[:3])
    destination = ROOT / 'selected.pt'
    if destination.exists():
        raise ValueError('Candidate already frozen; use a fresh artifact root.')
    shutil.copy2(name, destination)
    record = {'selectedFrom': name, 'checkpoint_sha256': sha(destination),
              'manifest_sha256': state['manifest_sha256'], 'arch': state['config']['arch'],
              'size': state['config']['size'], 'classes': len(state['labels']),
              'validationTop1': state['best_val'], 'selectionRule': 'Maximum positive validation top1; no test predictions inspected.'}
    (ROOT / 'candidate.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)


def calibrate(predictions):
    if (ROOT / 'selection.json').exists():
        raise ValueError('Selection already frozen.')
    record = json.loads((ROOT / 'candidate.json').read_text())
    if sha(ROOT / 'selected.pt') != record['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    rows = metrics.load_rows(predictions)
    if any(row['split'] not in ['val', 'ood_val'] for row in rows):
        raise ValueError('Calibration may access validation only')
    metadata = json.loads(predictions.with_suffix('.metadata.json').read_text())
    if metadata['checkpoint_sha256'] != record['checkpoint_sha256']:
        raise ValueError('Prediction checkpoint mismatch')
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
    (ROOT / 'selection.json').write_text(json.dumps(record, indent=2) + '\n')
    contract = {'modelResource': 'NationalClassifier', 'classCount': len(labels), 'inputSize': record['size'],
                'confidenceThreshold': confidence, 'logitMargin': margin,
                'checkpointSHA256': record['checkpoint_sha256'], 'labelsSHA256': sha(ROOT / 'training-labels.json'),
                'confirmedEntryIDs': [label['id'] for label in labels if label.get('confirmed', True)]}
    (ROOT / 'recognition-manifest.json').write_text(json.dumps(contract, indent=2) + '\n')
    report = metrics.metrics(rows, labels, confidence, margin, bootstrap_replicates=500)
    (ROOT / 'reports/validation.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
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

"""Report a frozen 1.3 candidate against the unchanged 1.2 release, without inference.

Run from the repository root after both final prediction files exist. New source
groups, reused public/forms holdouts and reused natural negatives stay separate.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import uuid
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics
from release_contract import validate as validate_contract

ROOT = Path('artifacts/multidomain')
SPLITS = ('test_multidomain', 'test_public', 'test_forms', 'ood_test_public')
CAVEATS = [
    'Public-source diagnostics and manufacturer product photos do not establish physical-phone camera accuracy.',
    'Related artwork, capture sessions and public pretraining contamination may survive source/perceptual grouping.',
    'Anime has very few explicitly audited groups; report its sample counts without claiming general anime accuracy.',
    'The head classifies species/forms, not shiny-versus-normal appearance; no shiny-recognition claim is supported.',
    'Reused public, alternate-form and natural-negative holdouts are diagnostics, separate from fresh source-group holdouts.',
]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    payload = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.partial')
    try:
        temporary.write_text(payload, encoding='utf-8', newline='\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def counts_by(rows, field):
    return {value: {'images': len(part), 'groups': len({r['group'] for r in part})}
            for value in sorted({r[field] for r in rows})
            for part in [[r for r in rows if r[field] == value]]}


def guarded_predictions(path, reference, checkpoint_sha, expected, current_labels, manifest_sha, labels_sha, size, arch):
    metadata = read(path.with_suffix('.metadata.json'))
    wanted = dict(checkpoint_sha256=checkpoint_sha, predictions_sha256=sha(path),
                  manifest_sha256=manifest_sha, labels_sha256=labels_sha, size=size, arch=arch)
    for key, value in wanted.items():
        check(metadata.get(key) == value, f'{path}: metadata {key} mismatch')
    check(metadata.get('reference') is reference, f'{path}: reference flag mismatch')
    rows = metrics.load_rows(path)
    check(len(rows) == metadata.get('rows'), f'{path}: row count mismatch')
    check(len(rows) == len(expected) and {r['sha256'] for r in rows} == set(expected),
          f'{path}: must contain each frozen final-test image exactly once')
    columns = [label['id'] for label in current_labels]
    for row in rows:
        check(row.get('label_ids') == columns, f'{path}: logit columns differ from the frozen head')
        check(all(row.get(key) == expected[row['sha256']][key] for key in metrics.PAIRED_FIELDS),
              f'{path}: prediction row differs from the frozen manifest')
    # Validate duplicate hashes, targets, finite logits and all logit dimensions.
    metrics._prepare(rows, current_labels, .25, .5, 1., 15)
    return rows, metadata


def stage_receipt(root, stage, manifest_sha):
    name = stage['name']
    directory = root / 'runs' / name
    result = dict(name=name, plannedEpochs=stage['epochs'], status='not_started',
                  observedEpochs=0, epochWorkSeconds=0., checkpointSHA256={}, sourceSnapshots={})
    history_path = directory / 'history.jsonl'
    if not history_path.exists():
        return result
    history = metrics.load_rows(history_path)
    epochs = [row['epoch'] for row in history]
    check(epochs == list(range(1, len(epochs) + 1)), f'{name}: history epochs are duplicated or incomplete')
    environment_path, status_path = directory / 'environment.json', directory / 'run_status.json'
    environment = read(environment_path)
    status = read(status_path) if status_path.exists() else {}
    if status:
        check(status['last_epoch'] == len(epochs), f'{name}: status/history epoch count mismatch')
    if name != 'robust-warmup':
        check(environment['manifest_sha256'] == manifest_sha, f'{name}: training data SHA mismatch')
    for source, recorded in environment.get('code_hashes', {}).items():
        snapshot = directory / 'source' / Path(source.replace('\\', '/')).name
        actual = sha(snapshot) if snapshot.is_file() else None
        check(actual == recorded, f'{name}: source snapshot changed or missing: {source}')
        result['sourceSnapshots'][source] = {'recordedSHA256': recorded, 'snapshotSHA256': actual}
    result.update(status=status.get('status', 'unfinished'), observedEpochs=len(epochs),
                  historySHA256=sha(history_path), environmentSHA256=sha(environment_path),
                  runStatusSHA256=sha(status_path) if status else None,
                  epochWorkSeconds=sum(row['seconds'] for row in history),
                  lastSessionElapsedSeconds=status.get('elapsed_seconds'),
                  manifestSHA256=environment['manifest_sha256'], config=environment['config'],
                  environment={k: environment.get(k) for k in ('python', 'torch', 'torchvision', 'PIL', 'cuda', 'gpu', 'seed', 'parameters')},
                  peakGPUBytes=max((row['gpu_peak_bytes'] for row in history), default=0),
                  peakRSSBytes=max((row['rss_bytes'] for row in history), default=0),
                  history=history,
                  checkpointSHA256={p.name: sha(p) for p in [directory / 'best.pt', directory / 'last.pt'] if p.is_file()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--replicates', type=int, default=500)
    args = parser.parse_args()
    check(args.replicates >= 1, '--replicates must be positive for paired confidence intervals')
    root = args.root
    protocol, selection = read(root / 'protocol.json'), read(root / 'selection.json')
    policy, old_policy = read(root / 'recognition-manifest.json'), read(root / 'baseline-recognition-manifest.json')
    labels_path, old_labels_path = root / 'training-labels.json', root / 'baseline-labels.json'
    labels, old_labels = read(labels_path), read(old_labels_path)
    manifest_sha, labels_sha = sha(root / 'data/manifest.jsonl'), sha(labels_path)
    validate_contract(policy, labels, labels_path.read_bytes(), (root / 'selected.pt').read_bytes())
    check(manifest_sha == protocol['manifestSHA256'] == selection['manifest_sha256'] == policy['trainingManifestSHA256'], 'Frozen data SHA mismatch')
    check(labels_sha == protocol['labelsSHA256'], 'Frozen labels SHA mismatch')
    check(policy['checkpointSHA256'] == selection['checkpoint_sha256'], 'Selected checkpoint SHA mismatch')
    check(all(policy[key] == selection[key] for key in ('confidenceThreshold', 'logitMargin')), 'Frozen candidate policy changed')
    check(sha(old_labels_path) == old_policy['labelsSHA256'], 'Original labels SHA mismatch')
    check(sha(root / 'baseline-1.2.pt') == old_policy['checkpointSHA256'] == protocol['baselineCheckpointSHA256'], 'Original release checkpoint SHA mismatch')
    check([(p['id'], p['name']) for p in labels] == [(p['id'], p['name']) for p in old_labels], 'Baseline/candidate head identity or order differs')
    check(set(old_policy['confirmedEntryIDs']) == {p['id'] for p in old_labels if p.get('confirmed', True)}, 'Original eligibility changed')
    manifest = metrics.load_rows(root / 'data/manifest.jsonl')
    expected = {}
    for row in manifest:
        if row['use'] and row['split'] in SPLITS:
            previous = expected.setdefault(row['sha256'], row)
            check(all(previous[k] == row[k] for k in ('target_id', 'group', 'split')), 'Conflicting frozen duplicate')
    candidate, cm = guarded_predictions(root / 'predictions/selected-test.jsonl', False, policy['checkpointSHA256'], expected,
                                        labels, manifest_sha, labels_sha, policy['inputSize'], selection['arch'])
    baseline, bm = guarded_predictions(root / 'predictions/baseline-test.jsonl', True, old_policy['checkpointSHA256'], expected,
                                       labels, manifest_sha, labels_sha, old_policy['inputSize'], selection['arch'])
    provenance = dict(campaign=protocol['campaign'], manifestSHA256=manifest_sha, labelsSHA256=labels_sha,
                      baselineLabelsSHA256=sha(old_labels_path), candidateCheckpointSHA256=policy['checkpointSHA256'],
                      baselineCheckpointSHA256=old_policy['checkpointSHA256'],
                      candidatePredictionSHA256=cm['predictions_sha256'], baselinePredictionSHA256=bm['predictions_sha256'])
    common = dict(confidence=policy['confidenceThreshold'], margin=policy['logitMargin'])
    reports = {}

    def subset(rows, splits):
        return [row for row in rows if row['split'] in splits]

    def summarize(rows, scope, *, bootstrap=True):
        return dict(scope=scope, provenance=provenance, domainCounts=counts_by(rows, 'domain'),
                    splitCounts=counts_by(rows, 'split'), caveats=CAVEATS,
                    metrics=metrics.metrics(rows, labels, bootstrap_replicates=args.replicates if bootstrap else 0, **common) if rows else None)

    scopes = {'test-multidomain': ('test_multidomain',), 'test-reused-public': ('test_public',),
              'test-reused-forms-reference': ('test_forms',), 'test-reused-natural-negatives': ('ood_test_public',)}
    for name, splits in scopes.items():
        part = subset(candidate, splits)
        scope = dict(name=name, splits=list(splits), origin='fresh_source_groups' if name == 'test-multidomain' else 'reused_holdout')
        reports[name] = summarize(part, scope)
        for domain in sorted({r['domain'] for r in part}):
            check(all(c.isalnum() or c in '_-' for c in domain), 'Unsafe domain filename')
            reports[f'domains/{name}--{domain}'] = summarize([r for r in part if r['domain'] == domain], dict(scope, domain=domain))
    alternate_scopes = {'test-alternate-forms-fresh': ('test_multidomain',),
                        'test-alternate-forms-reused': ('test_public', 'test_forms')}
    for name, splits in alternate_scopes.items():
        part = [r for r in subset(candidate, splits) if r['target_id'] is not None and r['target_id'] > 1025]
        reports[name] = summarize(part, dict(name=name, splits=list(splits), targetFilter='target_id > 1025',
            origin='fresh_source_groups' if name.endswith('-fresh') else 'reused_holdouts_combined_with_per_split_counts'))
    forms_path = Path('iDex/Resources/pokemon-forms.json')
    categories = {p['id']: p.get('formCategory') for p in read(forms_path)}
    regional = dict(provenance=provenance, catalogSHA256=sha(forms_path), caveats=CAVEATS, scopes={})
    for name, splits in list(scopes.items())[:3]:
        regional['scopes'][name] = {
            category: summarize([r for r in subset(candidate, splits) if categories.get(r['target_id']) == category],
                                dict(name=name, splits=list(splits), formCategory=category))
            for category in ('regional', 'fusion')}
    reports['test-regional-fusion'] = regional
    for name, splits in [('paired-fresh-groups', ('test_multidomain',)), ('paired-reused-public', ('test_public', 'test_forms', 'ood_test_public'))]:
        part = subset(candidate, splits)
        reports[name] = dict(scope=dict(name=name, splits=list(splits)), provenance=provenance,
                             domainCounts=counts_by(part, 'domain'), splitCounts=counts_by(part, 'split'), caveats=CAVEATS,
                             comparison=metrics.compare_models(subset(baseline, splits), part, labels,
                                 baseline_labels=old_labels, baseline_confidence=old_policy['confidenceThreshold'],
                                 baseline_margin=old_policy['logitMargin'], replicates=args.replicates, **common))
    stages = [stage_receipt(root, stage, manifest_sha) for stage in protocol['stages']]
    runtime = dict(provenance=provenance, stages=stages, observedEpochs=sum(s['observedEpochs'] for s in stages),
                   epochWorkSeconds=sum(s['epochWorkSeconds'] for s in stages),
                   timingDefinition='Sum of actual history epoch seconds across all stages; excludes initialization and idle time. Last-session elapsed values are not summed after resumes.',
                   warmupProvenanceNote=protocol.get('warmupProvenanceNote'), reportingScriptSHA256=sha(Path(__file__)))
    reports['runtime'] = runtime
    reports['training-summary'] = dict(provenance=provenance, classCount=len(labels), eligibleClasses=len(policy['confirmedEntryIDs']),
        baselineEligibleClasses=len(old_policy['confirmedEntryIDs']), selectedFrom=selection['selectedFrom'],
        validationScore=selection['validationScore'], observedEpochs=runtime['observedEpochs'], epochWorkSeconds=runtime['epochWorkSeconds'],
        stages=[{key: s[key] for key in ('name', 'plannedEpochs', 'status', 'observedEpochs', 'epochWorkSeconds', 'checkpointSHA256')} for s in stages],
        testCounts={name: reports[name]['metrics']['counts'] if reports[name]['metrics'] else None for name in [*scopes, *alternate_scopes]},
        sourceReceipts={'protocolSHA256': sha(root / 'protocol.json'), 'splitLockSHA256': sha(root / 'data/split_lock.json'),
                        **{f'{name}ReferencesSHA256': sha(root / f'{name}-references.json') for name in ('mixed', 'game', 'card', 'plush')}},
        caveats=CAVEATS, reportFiles=sorted([f'{name}.json' for name in reports] + ['training-summary.json']))
    for name, report in reports.items():
        write(root / 'reports' / f'{name}.json', report)
    print(json.dumps(dict(reports=len(reports), output=str(root / 'reports'), observedEpochs=runtime['observedEpochs'],
        epochWorkSeconds=runtime['epochWorkSeconds'], freshTop1=reports['test-multidomain']['metrics']['top1'],
        reusedPublicTop1=reports['test-reused-public']['metrics']['top1'], classCount=len(labels), eligibleClasses=len(policy['confirmedEntryIDs']))))


if __name__ == '__main__':
    main()

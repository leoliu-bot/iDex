"""Publish deterministic metadata receipts, never training images or logits."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


ROOT = Path('artifacts/multidomain')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=Path('TrainingResources/source-receipts.tar.gz'))
    args = parser.parse_args()
    protocol = json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
    manifest = ROOT/'data/manifest.jsonl'
    assert digest(manifest.read_bytes()) == protocol['manifestSHA256']
    assert digest((ROOT/'training-labels.json').read_bytes()) == protocol['labelsSHA256']
    members = {}
    files = [ROOT/f'{name}-references.json' for name in ['mixed', 'game', 'card', 'plush']]
    files += [ROOT/'protocol.json', ROOT/'data/split_lock.json', ROOT/'coverage.json',
              ROOT/'quarantine.json', ROOT/'review/card-form-review.json',
              ROOT/'review/card-form-audit.json', ROOT/'review/domain-review.json']
    for file in files:
        value = json.loads(file.read_text(encoding='utf-8'))
        # Training paths are relative, but readers only need source identities.
        if file.name.endswith('-references.json'):
            value = [{k: v for k, v in row.items() if k != 'path'} for row in value]
        members[file.relative_to(ROOT).as_posix()] = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    keys = ['sha256', 'pixel_sha256', 'source_sha256', 'target_id', 'source_entry_id',
            'group', 'source_group', 'source', 'domain', 'split', 'use', 'origin',
            'source_url', 'member', 'locked_split', 'old_group']
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines()]
    members['manifest-receipts.jsonl'] = ''.join(
        json.dumps({k: row[k] for k in keys if k in row}, ensure_ascii=False, separators=(',', ':'))+'\n'
        for row in rows).encode('utf-8')
    index = dict(format=1, rawManifestSHA256=protocol['manifestSHA256'], rows=len(rows),
                 usableRows=sum(row['use'] for row in rows),
                 content='Metadata and source/hash receipts only; no images, audio, weights or predictions.',
                 members={name: dict(bytes=len(raw), sha256=digest(raw)) for name, raw in sorted(members.items())})
    members['index.json'] = (json.dumps(index, indent=2)+'\n').encode('utf-8')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_suffix(args.out.suffix+'.partial')
    with temporary.open('wb') as raw_stream, gzip.GzipFile(filename='', fileobj=raw_stream, mode='wb', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, raw in sorted(members.items()):
                entry = tarfile.TarInfo(name)
                entry.size = len(raw)
                entry.mode = 0o644
                archive.addfile(entry, io.BytesIO(raw))
    # Verify the exact emitted archive, not just its input dictionary.
    with tarfile.open(temporary, mode='r:gz') as archive:
        assert set(archive.getnames()) == set(members)
        for name, raw in members.items():
            assert digest(archive.extractfile(name).read()) == digest(raw)
    temporary.replace(args.out)
    receipt = dict(file=args.out.name, bytes=args.out.stat().st_size,
                   sha256=digest(args.out.read_bytes()), **index)
    args.out.with_suffix('.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'members'}))


if __name__ == '__main__':
    main()

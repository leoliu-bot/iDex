"""Acquire a hash-pinned additional mixed-domain species corpus.

Multi-appearance species are excluded here: a species-only label is not proof of
the ordinary form. Manufacturer and card metadata provide more precise labels.
"""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.request
import zipfile
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/multidomain'
SOURCE = 'keremberke/pokemon-classification'
REVISION = 'a0b014ffa0bf56b0a490676d298b3d73ca52b8d6'
FILES = {
    'train.zip': '6359730e9a6c620313401857e79aab8ca2571f65b34d621fd33cb88365811353',
    'valid.zip': 'aec4f0c7e9d318fc4e1af1a69387d0250f570177de4bf661c1a7042abf48910e',
    'test.zip': '38a98970a0b5c8cecab8be18f09cb16037a71a9819f56c5e57052deb4806239d',
}


def normalize(value):
    return re.sub('[^a-z0-9]', '', value.lower().replace('♀', 'f').replace('♂', 'm'))


def main():
    OUT.mkdir(exist_ok=True)
    raw_dir = OUT / 'sources/keremberke'
    raw_dir.mkdir(parents=True, exist_ok=True)
    def get(item):
        name, digest = item
        path = raw_dir / name
        if not path.exists():
            url = f'https://huggingface.co/datasets/{SOURCE}/resolve/{REVISION}/data/{name}'
            for attempt in range(5):
                try:
                    with urllib.request.urlopen(url, timeout=120) as response:
                        raw = response.read()
                    assert hashlib.sha256(raw).hexdigest() == digest
                    path.write_bytes(raw)
                    break
                except Exception:
                    if attempt == 4: raise
                    time.sleep(2 + attempt)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        return path
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        archives = list(pool.map(get, FILES.items()))
    base = json.loads((ROOT / 'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    aliases = json.loads((ROOT / 'artifacts/forms/aliases.json').read_text())
    forms = json.loads((ROOT / 'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    ambiguous = {p['speciesID'] for p in forms if aliases[str(p['id'])] != aliases[str(p['speciesID'])]}
    index = {normalize(p['englishName']): p['id'] for p in base}
    records = []
    skipped = 0
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not name.lower().endswith(('.jpg', '.jpeg', '.png')): continue
                parts = Path(name).parts
                matches = [index[normalize(part)] for part in parts[:-1] if normalize(part) in index]
                if len(set(matches)) != 1: continue
                number = matches[0]
                if number in ambiguous:
                    skipped += 1
                    continue
                raw = z.read(name)
                digest = hashlib.sha256(raw).hexdigest()
                destination = raw_dir / 'images' / f'{digest}.png'
                destination.parent.mkdir(exist_ok=True)
                with Image.open(io.BytesIO(raw)) as original:
                    image = ImageOps.exif_transpose(original).convert('RGB')
                    image.thumbnail((640, 640))
                    image.save(destination)
                # Roboflow exports can contain augmented copies of one original.
                source_pose = re.split(r'\.rf\.|_rf\.', Path(name).name)[0]
                records.append(dict(entry_id=number, path=destination.relative_to(ROOT).as_posix(),
                    sha256=hashlib.sha256(destination.read_bytes()).hexdigest(), originalSHA256=digest,
                    source='keremberke-pinned', domain='mixed_public_photo_art',
                    source_group=f'keremberke:{number}:{source_pose}', source_path=name,
                    source_revision=REVISION))
    (OUT / 'mixed-references.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(records=len(records), ambiguousSpeciesRowsExcluded=skipped, files=FILES)), flush=True)


if __name__ == '__main__': main()

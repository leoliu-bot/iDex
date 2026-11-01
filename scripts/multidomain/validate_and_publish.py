"""Mac-only FP32 numerical gate before changing the app's selected model."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coremltools as ct
import numpy as np
from PIL import Image
import torch
from model import load_checkpoint
from release_contract import validate as validate_contract


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish_verified(selected, labels, contract_path, destination, rollback):
    """Stage the complete bundle, retaining a unique, restorable prior bundle."""
    workspace = Path.cwd().resolve()
    allowed = workspace / 'iDex/Recognition'
    if destination.resolve().parent != allowed or rollback.resolve() != workspace / 'artifacts/multidomain/rollback':
        raise ValueError('Publication paths must stay within the expected workspace directories')
    allowed.mkdir(parents=True, exist_ok=True)
    # Save can fail; it must finish before any existing app resource is moved.
    with tempfile.TemporaryDirectory(prefix='.national-release-', dir=allowed) as temporary:
        staged = Path(temporary)
        selected.save(str(staged / destination.name))
        shutil.copy2(labels, staged / 'pokemon_labels.json')
        shutil.copy2(contract_path, staged / 'recognition-manifest.json')
        backup = rollback / uuid.uuid4().hex
        backup.mkdir(parents=True)
        originals = [destination, allowed / 'KantoClassifier.mlpackage',
                     allowed / 'pokemon_labels.json', allowed / 'recognition-manifest.json']
        moved, installed = [], []
        try:
            for original in originals:
                if original.exists():
                    original.replace(backup / original.name)
                    moved.append(original)
            for name in [destination.name, 'pokemon_labels.json', 'recognition-manifest.json']:
                target = allowed / name
                (staged / name).replace(target)
                installed.append(target)
        except BaseException:
            for target in reversed(installed):
                target.replace(staged / target.name)
            for original in reversed(moved):
                (backup / original.name).replace(original)
            raise
    return backup


def main():
    resources = Path('TrainingResources')
    checkpoint = resources / 'national-best.pt'
    labels = resources / 'training-labels.json'
    contract = json.loads((resources / 'recognition-manifest.json').read_text())
    decoded_labels = json.loads(labels.read_text(encoding='utf-8'))
    validate_contract(contract, decoded_labels, labels.read_bytes(), checkpoint.read_bytes())
    reference, state = load_checkpoint(checkpoint)
    if state['manifest_sha256'] != contract['trainingManifestSHA256'] or state['labels'] != decoded_labels:
        raise ValueError('Publication checkpoint differs from the frozen release contract')
    reference.eval()
    torch.set_num_threads(4)
    size = contract['inputSize']
    catalog = json.loads(Path('iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    catalog += json.loads(Path('iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    entries = {entry['id']: entry for entry in catalog}
    assert all(label['id'] in entries for label in decoded_labels)
    assert set(contract.get('confirmedEntryIDs', [])) == {label['id'] for label in decoded_labels if label.get('confirmed', True)}
    examples = ['ninetales-alola', 'kyurem-white', 'kyurem-black', 'necrozma-dusk', 'necrozma-dawn',
                'calyrex-ice', 'calyrex-shadow', 'articuno-galar', 'zoroark-hisui', 'tauros-paldea-aqua-breed']
    numbers = [1, 6, 7, 25, 151, 152, 248, 384, 445, 658, 700, 778, 906, 1000, 1025]
    numbers += [entry['id'] for entry in catalog if entry.get('formIdentifier') in examples]
    fixtures = []
    for number in numbers:
        entry = entries[number]
        asset = entry.get('spriteAsset', f'pokemon-{number:03d}')
        file = Path('iDex/Resources/PokemonSprites.xcassets') / (asset + '.imageset/sprite.png')
        with Image.open(file) as image:
            rgba = image.convert('RGBA')
            rgb = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
            fixtures.append((str(number), rgb.resize((size, size), Image.Resampling.BILINEAR)))
    for value in [0, 127, 255]:
        fixtures.append((f'solid-{value}', Image.new('RGB', (size, size), (value, value, value))))
    rng = np.random.default_rng(20261101)
    fixtures.append(('noise', Image.fromarray(rng.integers(0, 256, (size, size, 3), dtype=np.uint8))))
    package = Path('artifacts/multidomain/export/NationalCandidate-fp32.mlpackage')
    results = []
    for units in [ct.ComputeUnit.CPU_ONLY, ct.ComputeUnit.ALL]:
        converted = ct.models.MLModel(str(package), compute_units=units)
        metadata = converted.user_defined_metadata
        expected_metadata = {'checkpoint_sha256': contract['checkpointSHA256'],
                             'manifest_sha256': contract['trainingManifestSHA256'],
                             'app_labels_sha256': contract['labelsSHA256'],
                             'class_count': str(contract['classCount']),
                             'eligible_count': str(len(contract['confirmedEntryIDs']))}
        if any(metadata.get(key) != value for key, value in expected_metadata.items()):
            raise ValueError('Exported Core ML metadata does not match the frozen release')
        for name, image in fixtures:
            pixels = np.asarray(image).copy()
            tensor = torch.from_numpy(pixels).permute(2, 0, 1).unsqueeze(0).float() / 255
            with torch.inference_mode():
                expected = reference(tensor).numpy().reshape(-1)
            actual = np.asarray(converted.predict({'image': image})['logits']).reshape(-1)
            passed = actual.shape == expected.shape and np.isfinite(actual).all() and np.allclose(actual, expected, atol=.001, rtol=.0001) and actual.argmax() == expected.argmax()
            result = {'fixture': name, 'computeUnits': units.name, 'passed': bool(passed),
                      'maximumAbsoluteError': float(np.max(np.abs(actual - expected))) if actual.shape == expected.shape else None,
                      'topEntryID': decoded_labels[int(actual.argmax())]['id'] if actual.shape == expected.shape and np.isfinite(actual).all() else None}
            results.append(result)
            if not passed:
                raise ValueError(f'Core ML parity failed; app model was not replaced: {result}')
    output = Path('artifacts/multidomain/reports')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'coreml-parity.json').write_text(json.dumps({'passed': True, 'fixturesPerPolicy': len(fixtures), 'checks': results,
        'checkpointSHA256': contract['checkpointSHA256'], 'labelsSHA256': contract['labelsSHA256'],
        'trainingManifestSHA256': contract['trainingManifestSHA256'],
        'physicalIPhone': 'Not measured by this Mac numerical test.'}, indent=2) + '\n')
    selected = ct.models.MLModel(str(package), skip_model_load=True)
    selected.short_description = f'Pokédex offline National species and form classifier ({len(decoded_labels)} classes)'
    selected.user_defined_metadata['checkpoint_sha256'] = contract['checkpointSHA256']
    selected.user_defined_metadata['app_labels_sha256'] = contract['labelsSHA256']
    destination = Path('iDex/Recognition/NationalClassifier.mlpackage')
    rollback = Path('artifacts/multidomain/rollback')
    backup = publish_verified(selected, labels, resources / 'recognition-manifest.json', destination, rollback)
    (output / 'publication.json').write_text(json.dumps({'checkpointSHA256': contract['checkpointSHA256'],
        'labelsSHA256': contract['labelsSHA256'], 'rollback': str(backup)}, indent=2) + '\n')
    print(f'Published numerically verified FP32 model with {len(decoded_labels)} labels.', flush=True)


if __name__ == '__main__':
    main()

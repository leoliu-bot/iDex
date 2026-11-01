"""Verify the released unsigned IPA against the selected form campaign."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ipa', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    expected_labels = Path('TrainingResources/training-labels.json').read_bytes()
    expected_contract = json.loads(Path('TrainingResources/recognition-manifest.json').read_text())
    assert sha(expected_labels) == expected_contract['labelsSHA256']
    with zipfile.ZipFile(args.ipa) as package:
        assert package.testzip() is None, 'IPA CRC failure'
        names = set(package.namelist())
        app = next(n[:-len('Info.plist')] for n in names if n.startswith('Payload/') and n.count('/') == 2 and n.endswith('.app/Info.plist'))
        info = plistlib.loads(package.read(app + 'Info.plist'))
        assert info['CFBundleDisplayName'] == 'Pok\u00e9dex'
        assert info['CFBundleIdentifier'] == 'zihanghuang.iDex'
        assert info['CFBundleShortVersionString'] == '1.2' and info['CFBundleVersion'] == '3'
        for language in ['en', 'zh-Hans', 'ja']:
            localized = plistlib.loads(package.read(app + language + '.lproj/InfoPlist.strings'))
            assert localized['CFBundleDisplayName'] == 'Pok\u00e9dex'
        assert package.read(app + 'pokemon_labels.json') == expected_labels
        contract = json.loads(package.read(app + 'recognition-manifest.json'))
        assert contract == expected_contract
        base = json.loads(package.read(app + 'pokemon-national.json'))
        forms = json.loads(package.read(app + 'pokemon-forms.json'))
        assert len(base) == 1025 and len(forms) == 554
        assert forms == json.loads(Path('iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
        assert len({p['id'] for p in base + forms}) == 1579
        assert len(json.loads(expected_labels)) == 1498
        assert len(contract['confirmedEntryIDs']) == 1492
        compiled = {n[len(app):].split('/')[0] for n in names if n.startswith(app) and '.mlmodelc/' in n}
        assert compiled == {'NationalClassifier.mlmodelc'}
        sources = json.loads(package.read(app + 'cry-sources.json'))
        assert len(sources) == 1351
        assert {r['id'] for r in sources} == {r.get('cryID', r['id']) for r in base + forms}
        for source in sources:
            raw = package.read(app + source['file'])
            assert sha(raw) == source['sha256']
            assert raw[:4] == b'RIFF' and raw[8:12] == b'WAVE'
        assert app + 'Assets.car' in names
        assert not any(n.endswith('.mlpackage') or '/.catalog-cache/' in n for n in names)
    result = dict(file=args.ipa.name, bytes=args.ipa.stat().st_size, sha256=sha(args.ipa.read_bytes()),
                  displayName=info['CFBundleDisplayName'], bundleIdentifier=info['CFBundleIdentifier'],
                  version=info['CFBundleShortVersionString'], build=info['CFBundleVersion'],
                  species=1025, additionalForms=554, appearanceClasses=1498, dataEligibleClasses=1492,
                  verifiedCryResources=1351, compiledModel='NationalClassifier.mlmodelc',
                  checkpointSHA256=contract['checkpointSHA256'], passed=True,
                  signing='Unsigned artifact; use the established Windows signing procedure.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=True, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()

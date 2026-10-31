#!/usr/bin/env python3
"""Portable asset and localization checks; complements the iOS bundle tests."""
import collections
import hashlib
import json
from pathlib import Path
import wave
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / 'iDex/Resources'


def main():
    entries = json.loads((RESOURCES / 'pokemon-national.json').read_text(encoding='utf-8'))
    original = json.loads((RESOURCES / 'pokemon-kanto.json').read_text(encoding='utf-8'))
    assert [p['id'] for p in entries] == list(range(1, 1026))
    assert [{k: v for k, v in p.items() if k != 'generation'} for p in entries[:151]] == original
    for pokemon in entries:
        assert 1 <= pokemon['generation'] <= 9
        assert pokemon['height'] > 0 and pokemon['weight'] > 0
        assert len(pokemon['stats']) == 6 and all(0 < s['value'] <= 255 for s in pokemon['stats'])
        assert 1 <= len(pokemon['types']) <= 2
        for language in ['english', 'chinese', 'japanese']:
            for field in ['Name', 'Genus', 'Description']:
                assert pokemon[language + field].strip(), (pokemon['id'], language, field)
        asset = RESOURCES / f'PokemonSprites.xcassets/pokemon-{pokemon["id"]:03d}.imageset'
        with Image.open(asset / 'sprite.png') as image:
            image.verify()
        with Image.open(asset / 'sprite.png') as image:
            assert image.size == (96, 96)
            assert image.convert('RGBA').getbbox() is not None
        assert json.loads((asset / 'Contents.json').read_text())['images'][0]['filename'] == 'sprite.png'
    sources = json.loads((RESOURCES / 'Cries/cry-sources.json').read_text(encoding='utf-8'))
    assert [s['id'] for s in sources] == list(range(1, 1026))
    for source in sources:
        file = RESOURCES / 'Cries' / source['file']
        assert hashlib.sha256(file.read_bytes()).hexdigest() == source['sha256']
        with wave.open(str(file)) as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (1, 2, 22050, source['frames'])
    output = ROOT / 'artifacts/national/reports'
    output.mkdir(parents=True, exist_ok=True)
    ids = [1, 25, 151, 152, 196, 248, 252, 384, 387, 445, 493, 494, 571, 649,
           650, 658, 700, 721, 722, 778, 809, 810, 887, 898, 899, 905, 906, 925, 963, 964, 1000, 1025]
    sheet = Image.new('RGB', (8 * 144, 4 * 160), '#c4cba3')
    draw = ImageDraw.Draw(sheet)
    for index, number in enumerate(ids):
        x, y = index % 8 * 144, index // 8 * 160
        with Image.open(RESOURCES / f'PokemonSprites.xcassets/pokemon-{number:03d}.imageset/sprite.png') as sprite:
            sprite = sprite.convert('RGBA')
            sheet.paste(sprite, (x + 24, y + 12), sprite)
        draw.text((x + 10, y + 122), f'#{number:03d}', fill='#293322')
        draw.text((x + 10, y + 137), entries[number-1]['englishName'], fill='#293322')
    sheet.save(output / 'pixel-style-review.png')
    report = {'species': len(entries), 'sprites': len(entries), 'verifiedCries': len(sources),
              'generationCounts': dict(collections.Counter(p['generation'] for p in entries)),
              'kantoRecordsPreserved': True, 'languages': ['en', 'zh-Hans', 'ja']}
    (output / 'catalog-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

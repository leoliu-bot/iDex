#!/usr/bin/env python3
"""Build the offline National Dex, retaining the original Kanto entries and art."""
import concurrent.futures
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import struct
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.catalog-cache'
RESOURCES = ROOT / 'iDex' / 'Resources'
LANGUAGES = {'english': 9, 'chinese': 12, 'japanese': 11}
FILES = ['pokemon.csv', 'pokemon_species.csv', 'pokemon_species_names.csv',
         'pokemon_species_flavor_text.csv', 'pokemon_types.csv', 'types.csv',
         'pokemon_stats.csv', 'stats.csv']


def download(url, path):
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Pokedex-catalog/2.0'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if '.pokemon.cn/' in url else urllib.request.build_opener()
            with opener.open(request, timeout=60) as response:
                data = response.read()
            temporary = path.with_suffix(path.suffix + '.partial')
            temporary.write_bytes(data)
            temporary.replace(path)
            return data
        except Exception:
            if attempt == 4:
                raise
            time.sleep(attempt + 1)


def main():
    CACHE.mkdir(exist_ok=True)
    lock_path = ROOT / 'scripts/catalog/upstream-lock.json'
    if lock_path.exists():
        revisions = json.loads(lock_path.read_text(encoding='utf-8'))
    else:
        revisions = {}
        for key, repo in [('data', 'pokeapi'), ('sprites', 'sprites')]:
            metadata = json.loads(download(f'https://api.github.com/repos/PokeAPI/{repo}/commits/master', CACHE / f'{key}-revision.json'))
            revisions[key] = metadata['sha']
        lock_path.write_text(json.dumps(revisions, indent=2) + '\n', encoding='utf-8', newline='\n')
    base = f'https://raw.githubusercontent.com/PokeAPI/pokeapi/{revisions["data"]}/data/v2/csv/'
    def rows(name):
        return list(csv.DictReader(io.StringIO(download(base + name, CACHE / revisions['data'] / name).decode('utf-8'))))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tables = dict(zip(FILES, pool.map(rows, FILES)))
    names = {(int(r['pokemon_species_id']), int(r['local_language_id'])): r for r in tables['pokemon_species_names.csv']}
    types = {r['id']: r['identifier'] for r in tables['types.csv']}
    stats = {r['id']: r['identifier'] for r in tables['stats.csv']}
    defaults = {int(r['species_id']): r for r in tables['pokemon.csv'] if r['is_default'] == '1'}
    flavor = {}
    for row in sorted(tables['pokemon_species_flavor_text.csv'], key=lambda r: int(r['version_id'])):
        language = int(row['language_id'])
        if language in LANGUAGES.values():
            text = ' '.join(row['flavor_text'].replace('\f', ' ').split())
            flavor[int(row['species_id']), language] = text.replace(' ', '') if language == 12 else text
    original = {p['id']: p for p in json.loads((RESOURCES / 'pokemon-kanto.json').read_text(encoding='utf-8'))}
    # PokéAPI lacks some Chinese entries and Gen 9 Japanese text. Use short
    # official localized field notes, never English placeholders or invented facts.
    missing = [(int(p['id']), language, code) for p in tables['pokemon_species.csv']
               for language, code in LANGUAGES.items() if int(p['id']) > 151
               and ((int(p['id']), code) not in flavor or not names[int(p['id']), code]['genus'])]
    def official(item):
        number, language, code = item
        if language == 'chinese':
            url = f'https://dex.pokemon.cn/play/pokedex/{number:04d}'
            page = download(url, CACHE / 'official-zh' / f'{number:04d}.html').decode('utf-8')
            texts = re.findall(r'<p[^>]*class="pokemon-story__body[^\"]*"[^>]*>(.*?)</p>', page, re.S)
            genus = re.search(r'class="pokemon-info__category"[^>]*>.*?class="pokemon-info__value[^\"]*"[^>]*>(.*?)</span></div>', page, re.S)
        elif language == 'japanese':
            url = f'https://zukan.pokemon.co.jp/detail/{number:04d}'
            page = download(url, CACHE / 'official-ja' / f'{number:04d}.html').decode('utf-8')
            texts = re.findall(r'<div class="[01]"><p>(.*?)</p>', page, re.S)
            genus = re.search(r'<dd class="[^\"]*js-classification[^\"]*">(.*?)</dd>', page, re.S)
        else:
            raise ValueError(f'Missing English data for {number}')
        clean = lambda value: ' '.join(html.unescape(re.sub('<[^>]+>', '', value)).split())
        if not texts or genus is None:
            raise ValueError(f'Official localized field note missing: {url}')
        description = clean(texts[0])
        description = re.sub(r'\s*（『.*?』より）\s*$', '', description)
        if code == 12:
            description = description.replace(' ', '')
        return number, code, description, clean(genus[1]), url, hashlib.sha256(page.encode('utf-8')).hexdigest()
    text_sources = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for count, (number, code, description, genus, url, page_hash) in enumerate(pool.map(official, missing), 1):
            flavor.setdefault((number, code), description)
            if not names[number, code]['genus']:
                names[number, code]['genus'] = genus
            text_sources.append({'id': number, 'languageID': code, 'source': url, 'cachedPageSHA256': page_hash})
            if count % 50 == 0:
                print(f'Completed {count}/{len(missing)} official localized field notes', flush=True)
    entries = []
    for species in sorted(tables['pokemon_species.csv'], key=lambda r: int(r['id'])):
        number = int(species['id'])
        p = defaults[number]
        pokemon_id = int(p['id'])
        entry = dict(original[number]) if number in original else {
            'id': number,
            'types': [types[t['type_id']] for t in sorted(tables['pokemon_types.csv'], key=lambda r: int(r['slot'])) if int(t['pokemon_id']) == pokemon_id],
            'height': int(p['height']) / 10,
            'weight': int(p['weight']) / 10,
            'stats': [{'name': stats[s['stat_id']], 'value': int(s['base_stat'])} for s in tables['pokemon_stats.csv'] if int(s['pokemon_id']) == pokemon_id]
        }
        if number not in original:
            for language, code in LANGUAGES.items():
                localized = names[number, code]
                entry[language + 'Name'] = localized['name']
                entry[language + 'Genus'] = localized['genus']
                entry[language + 'Description'] = flavor[number, code]
        entry['generation'] = int(species['generation_id'])
        entries.append(entry)
    assert len(entries) > 151
    assert [p['id'] for p in entries] == list(range(1, len(entries) + 1))
    assert all(all(p[lang + field] for lang in LANGUAGES for field in ['Name', 'Genus', 'Description']) and len(p['stats']) == 6 for p in entries)
    (RESOURCES / 'pokemon-national.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (RESOURCES / 'text-sources.json').write_text(json.dumps(text_sources, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    sources = json.loads((RESOURCES / 'sprite-sources.json').read_text(encoding='utf-8'))
    def sprite(entry):
        number = entry['id']
        asset = RESOURCES / 'PokemonSprites.xcassets' / f'pokemon-{number:03d}.imageset'
        path = asset / 'sprite.png'
        source = sources.get(str(number)) if number <= 151 else f'https://raw.githubusercontent.com/PokeAPI/sprites/{revisions["sprites"]}/sprites/pokemon/{number}.png'
        data = download(source, path)
        if data[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', data[16:24]) != (96, 96):
            raise ValueError(f'{number}: expected a 96x96 pixel sprite, not artwork or a placeholder')
        if not (asset / 'Contents.json').exists():
            (asset / 'Contents.json').write_text(json.dumps({'images': [{'filename': 'sprite.png', 'idiom': 'universal'}], 'info': {'author': 'xcode', 'version': 1}}, indent=2) + '\n', encoding='utf-8', newline='\n')
        return str(number), source
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for count, (number, source) in enumerate(pool.map(sprite, entries), 1):
            sources[number] = source
            if count % 100 == 0:
                print(f'Verified {count}/{len(entries)} pixel sprites', flush=True)
    (RESOURCES / 'sprite-sources.json').write_text(json.dumps(sources, indent=2) + '\n', encoding='utf-8', newline='\n')
    receipt = {'species': len(entries), 'generations': max(p['generation'] for p in entries), 'upstream': revisions,
               'catalogSHA256': hashlib.sha256((RESOURCES / 'pokemon-national.json').read_bytes()).hexdigest(),
               'spriteStyle': '96x96 Gen 5 pixel art; original 151 preserved; newer species use credited community Gen 5 sprites'}
    (RESOURCES / 'catalog-manifest.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()

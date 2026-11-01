"""Acquire pinned, explicitly form-labelled reference images, never synthetic labels."""
import concurrent.futures
import asyncio
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
import aiohttp

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'catalog'))
from build_national_catalog import ROOT, CACHE, download

OUT = ROOT / 'artifacts/forms'
LOCK = json.loads((ROOT / 'scripts/catalog/upstream-lock.json').read_text())
BASE = f'https://raw.githubusercontent.com/PokeAPI/sprites/{LOCK["sprites"]}/sprites/pokemon/'

async def prefetch(requests):
    unique = {relative: row for _,relative,row in requests}
    pending = [(relative,row) for relative,row in unique.items() if not (OUT/'sources/pokeapi'/relative).exists()]
    print(f'Fetching {len(pending)} uncached files with persistent connections',flush=True)
    semaphore = asyncio.Semaphore(20)
    count = 0
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=60), connector=aiohttp.TCPConnector(limit=20)) as session:
        async def one(relative, row):
            nonlocal count
            async with semaphore:
                for attempt in range(5):
                    try:
                        async with session.get(BASE+relative) as response:
                            response.raise_for_status(); raw = await response.read()
                        if hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != row['sha']:
                            raise ValueError(('Source blob mismatch',relative))
                        destination=OUT/'sources/pokeapi'/relative
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        temporary=destination.with_suffix(destination.suffix+'.partial')
                        temporary.write_bytes(raw);temporary.replace(destination)
                        break
                    except Exception:
                        if attempt==4: raise
                        await asyncio.sleep(attempt+1)
                count += 1
                if count%1000==0:print(f'Fetched {count}/{len(pending)} uncached files',flush=True)
        await asyncio.gather(*(one(relative,row) for relative,row in pending))

def tree(sha, name, recursive=False):
    path = CACHE / f'forms-tree-{name}.json'
    if not path.exists():
        download(f'https://api.github.com/repos/PokeAPI/sprites/git/trees/{sha}' + ('?recursive=1' if recursive else ''), path)
    value = json.loads(path.read_text())
    if value.get('truncated'): raise ValueError(('Truncated source listing', name))
    return value['tree']

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    entries = json.loads((ROOT / 'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    entries += json.loads((ROOT / 'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    forms = list(csv.DictReader((CACHE / LOCK['data'] / 'pokemon_forms.csv').open()))
    pokemon = {p['id']: p for p in csv.DictReader((CACHE / LOCK['data'] / 'pokemon.csv').open())}
    metadata = json.loads((ROOT / 'iDex/Resources/base-form-metadata.json').read_text())
    by_form = {f['id']: f for f in forms}
    listing = json.loads((CACHE / 'pokemon-tree.json').read_text())['tree']
    files = {r['path']: r for r in listing if r['type']=='blob'}
    for folder in ['back', 'other']:
        sha = next(r['sha'] for r in listing if r['path']==folder)
        for row in tree(sha, folder, recursive=folder=='other'):
            if row['type']=='blob': files[folder+'/'+row['path']] = row
    version_sha = next(r['sha'] for r in listing if r['path']=='versions')
    generations = tree(version_sha, 'versions')
    # Older games supply independently drawn poses. Animation frames from a
    # single game asset are kept in one source group later, never split apart.
    def generation(row):
        return row['path'], tree(row['sha'], row['path'], recursive=True)
    wanted = [r for r in generations if r['type']=='tree' and r['path'] in ['generation-ii','generation-iii','generation-iv','generation-v','generation-vi','generation-vii']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name, items in pool.map(generation, wanted):
            for row in items:
                if row['type']=='blob': files['versions/'+name+'/'+row['path']] = row
    by_name = {}
    for path, row in files.items(): by_name.setdefault(Path(path).name, []).append((path,row))
    requests = []
    coverage = {}
    for entry in entries:
        fid = entry.get('sourceFormID') or metadata[str(entry['id'])]['sourceFormID']
        form = by_form[str(fid)]
        p = pokemon[form['pokemon_id']]
        pid, token = p['id'], form['form_identifier']
        stem = pid if form['is_default']=='1' or p['is_default']!='1' else pid+'-'+token
        choices = []
        for name in [stem+'.png']:
            for path,row in by_name.get(name,[]):
                if '/shiny/' in '/'+path or '/female/' in '/'+path or path.startswith('shiny/'): continue
                if not (path.startswith(('other/home/','other/official-artwork/','other/showdown/','versions/','back/')) or '/' not in path): continue
                if row.get('size',0)>3_000_000: continue
                choices.append((path,row))
        def priority(item):
            path = item[0]
            return (0 if '/' not in path else 1 if path.startswith('other/official-artwork/') else 2 if path.startswith('other/home/') else 3 if path.startswith('back/') else 4, path)
        selected, seen_blobs, seen_games = [], set(), set()
        for path,row in sorted(choices,key=priority):
            if row['sha'] in seen_blobs: continue
            if path.startswith('versions/'):
                parts=path.split('/')
                group=(parts[1], 'back' in parts)
                if group in seen_games: continue
                seen_games.add(group)
            seen_blobs.add(row['sha']); selected.append((path,row))
        choices = selected[:16]
        # One front/back pose per game directory; duplicate files are audited
        # after decoding. Source files remain byte-identical in this cache.
        for path,row in choices:
            requests.append((entry['id'], path, row))
        coverage[entry['id']] = len(choices)
    print(f'Acquiring {len(requests)} references for {len(entries)} entries',flush=True)
    asyncio.run(prefetch(requests))
    def fetch(item):
        entry_id, relative, row = item
        destination = OUT / 'sources/pokeapi' / relative
        raw = download(BASE+relative, destination)
        blob = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        if blob != row['sha']: raise ValueError(('Source blob mismatch',relative))
        with Image.open(io.BytesIO(raw)) as image:
            image.seek(0)
            if image.width*image.height > 20_000_000: raise ValueError(relative)
            if not image.convert('RGBA').getbbox(): return None
        return {'entry_id':entry_id,'path':str(destination.relative_to(ROOT)).replace('\\','/'),
                'source_path':relative,'url':BASE+relative,'git_blob':blob,'sha256':hashlib.sha256(raw).hexdigest()}
    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for i,record in enumerate(pool.map(fetch, requests),1):
            if record: records.append(record)
            if i%500==0: print(f'References {i}/{len(requests)}',flush=True)
    (OUT/'references.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'source-coverage.json').write_text(json.dumps(coverage,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Acquired {len(records)} verified references',flush=True)

if __name__ == '__main__': main()

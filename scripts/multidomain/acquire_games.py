"""Pinned game animation frames. All frames of one asset stay in one group."""
import asyncio
import csv
import hashlib
import io
import json
from pathlib import Path
import aiohttp
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/multidomain'
CACHE = ROOT / '.catalog-cache'


async def main():
    lock = json.loads((ROOT/'scripts/catalog/upstream-lock.json').read_text())
    entries = json.loads((ROOT/'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    entries += json.loads((ROOT/'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    metadata = json.loads((ROOT/'iDex/Resources/base-form-metadata.json').read_text())
    forms = {p['id']:p for p in csv.DictReader((CACHE/lock['data']/'pokemon_forms.csv').open())}
    pokemon = {p['id']:p for p in csv.DictReader((CACHE/lock['data']/'pokemon.csv').open())}
    files = []
    for file, prefix in [('forms-tree-other.json','other/'), ('forms-tree-generation-v.json','versions/generation-v/')]:
        for row in json.loads((CACHE/file).read_text())['tree']:
            path = prefix+row['path']
            if row['type']=='blob' and path.endswith('.gif') and '/shiny/' not in path and '/female/' not in path:
                if path.startswith('other/showdown/') or '/black-white/animated/' in path:
                    files.append((path,row))
    by_name = {}
    for path,row in files: by_name.setdefault(Path(path).name,[]).append((path,row))
    requests = []
    for p in entries:
        fid = str(p.get('sourceFormID') or metadata[str(p['id'])]['sourceFormID'])
        f = forms[fid]; source = pokemon[f['pokemon_id']]
        stem = source['id'] if f['is_default']=='1' or source['is_default']!='1' else source['id']+'-'+f['form_identifier']
        for path,row in by_name.get(stem+'.gif',[])[:2]: requests.append((p['id'],path,row))
    print(f'Acquiring {len(requests)} game animation assets',flush=True)
    semaphore = asyncio.Semaphore(12)
    records, failures = [], []
    async with aiohttp.ClientSession(trust_env=True,timeout=aiohttp.ClientTimeout(total=80)) as session:
        async def one(item):
            number,path,row=item
            destination=OUT/'sources/games'/path;destination.parent.mkdir(parents=True,exist_ok=True)
            url=f'https://raw.githubusercontent.com/PokeAPI/sprites/{lock["sprites"]}/sprites/pokemon/'+path
            async with semaphore:
                if not destination.exists():
                    for attempt in range(4):
                        try:
                            async with session.get(url) as response:response.raise_for_status();raw=await response.read()
                            assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==row['sha']
                            destination.write_bytes(raw);break
                        except Exception as error:
                            if attempt==3:failures.append({'url':url,'error':str(error)});return
                            await asyncio.sleep(attempt+2)
                raw=destination.read_bytes()
                assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==row['sha']
                with Image.open(io.BytesIO(raw)) as animation:
                    n=animation.n_frames
                    for frame in sorted({0,n//4,n//2,3*n//4}):
                        animation.seek(frame); image=animation.convert('RGBA')
                        if not image.getbbox():continue
                        image=Image.alpha_composite(Image.new('RGBA',image.size,'white'),image).convert('RGB')
                        target=destination.with_name(destination.stem+f'-frame-{frame}.png');image.save(target)
                        records.append(dict(entry_id=number,path=target.relative_to(ROOT).as_posix(),
                            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),originalSHA256=hashlib.sha256(raw).hexdigest(),
                            source='PokeAPI-game-animation-pinned',domain='game_render_animation',
                            source_group='game-animation:'+path,source_path=path+f'#frame={frame}',url=url,
                            source_revision=lock['sprites'],git_blob=row['sha']))
        await asyncio.gather(*(one(item) for item in requests))
    records.sort(key=lambda r:(r['entry_id'],r['source_path']))
    (OUT/'game-references.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'game-unavailable.json').write_text(json.dumps(failures,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'frames':len(records),'assets':len({r['source_group'] for r in records}),'failed':len(failures)}),flush=True)


if __name__=='__main__':asyncio.run(main())

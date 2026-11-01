"""Supplement explicitly named forms with cropped historical TCG illustrations.

No card names or HP/header text enter training. Multi-Pokémon cards and
ambiguous Mega names are excluded. Raw cards remain in the ignored artifact root.
"""
import asyncio
import collections
import hashlib
import io
import json
from pathlib import Path
import random
import re
import zipfile

import aiohttp
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/forms'

def key(name):return re.sub('[^a-z0-9]','',name.lower())

async def main():
    forms=json.loads((ROOT/'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    index=collections.defaultdict(list)
    for p in forms:index[key(p['englishName'])].append(p)
    extra={'ashgreninja':'greninja-ash','duskmane necrozma':'necrozma-dusk','dawnwings necrozma':'necrozma-dawn',
           'icerider calyrex':'calyrex-ice','shadowrider calyrex':'calyrex-shadow'}
    for name,identifier in extra.items():
        p=next(p for p in forms if p['formIdentifier']==identifier);index[key(name)]=[p]
    base=json.loads((ROOT/'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    index['centiskorch']=[next(p for p in base if p['id']==851)]
    revision=json.loads((ROOT/'.catalog-cache/tcg-revision.json').read_text())['sha']
    candidates=collections.defaultdict(list)
    with zipfile.ZipFile(ROOT/'.catalog-cache/pokemon-tcg-data.zip') as archive:
        for path in archive.namelist():
            if '/cards/en/' not in path or not path.endswith('.json'):continue
            for card in json.loads(archive.read(path)):
                original=card.get('name','')
                if any(x in original for x in ['&',' and ',' / ']):continue
                name=re.sub(r'(?:[- ](?:GX|EX|ex|VMAX|VSTAR|V|BREAK))$','',original)
                if name.startswith('M '):name='Mega '+name[2:]
                options=index.get(key(name),[])
                if original.endswith('VMAX') and name=='Centiskorch':
                    options=[next(p for p in forms if p['formIdentifier']=='centiskorch-gmax')]
                if len(options)!=1 or 'small' not in card.get('images',{}):continue
                p=options[0]
                if card.get('nationalPokedexNumbers') and p.get('speciesID',p['id']) not in card['nationalPokedexNumbers']:continue
                candidates[p['id']].append((p,card))
    chosen=[];rng=random.Random(20261101)
    for entry_id,values in sorted(candidates.items()):
        rng.shuffle(values)
        # Prefer distinct artists before selecting alternate printings.
        values.sort(key=lambda item:item[1].get('artist',''))
        by_artist=collections.defaultdict(list)
        for item in values:by_artist[item[1].get('artist','')].append(item)
        ordered=[v.pop(0) for v in by_artist.values()]
        ordered += [item for v in by_artist.values() for item in v]
        chosen.extend(ordered[:8])
    print(f'Acquiring {len(chosen)} explicitly labelled card illustrations for {len(candidates)} appearance records',flush=True)
    semaphore=asyncio.Semaphore(12)
    records=[]
    unavailable=[]
    async with aiohttp.ClientSession(trust_env=True,timeout=aiohttp.ClientTimeout(total=60)) as session:
        async def one(item):
            p,card=item;url=card['images']['small'];card_id=card['id']
            source=OUT/'sources/tcg'/f'{card_id}.png';source.parent.mkdir(parents=True,exist_ok=True)
            async with semaphore:
                if not source.exists():
                    for attempt in range(5):
                        try:
                            async with session.get(url) as response:response.raise_for_status();raw=await response.read()
                            source.write_bytes(raw);break
                        except aiohttp.ClientResponseError as error:
                            if error.status in [404,410]:
                                unavailable.append({'cardID':card_id,'url':url,'status':error.status});return
                            if attempt==4:raise
                            await asyncio.sleep(attempt+1)
                        except Exception:
                            if attempt==4:raise
                            await asyncio.sleep(attempt+1)
                raw=source.read_bytes()
                with Image.open(io.BytesIO(raw)) as image:
                    image=image.convert('RGB');w,h=image.size
                    crop=image.crop((round(w*.08),round(h*.20),round(w*.92),round(h*.50)))
                    side=max(crop.size);square=Image.new('RGB',(side,side),'white')
                    square.paste(crop,((side-crop.width)//2,(side-crop.height)//2))
                    destination=OUT/'sources/tcg-art'/f'{card_id}.png';destination.parent.mkdir(parents=True,exist_ok=True);square.save(destination)
                records.append({'entry_id':p['id'],'path':destination.relative_to(ROOT).as_posix(),'source_path':'tcg-art/'+card_id,
                                'url':url,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'originalSHA256':hashlib.sha256(raw).hexdigest(),
                                'cardID':card_id,'cardName':card['name'],'artist':card.get('artist'),'metadataRevision':revision,
                                'crop':[.08,.20,.92,.50]})
        await asyncio.gather(*(one(item) for item in chosen))
    records.sort(key=lambda r:(r['entry_id'],r['cardID']))
    (OUT/'card-references.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'unavailable-card-images.json').write_text(json.dumps(unavailable,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Acquired {len(records)} card-art references',flush=True)

if __name__=='__main__':asyncio.run(main())

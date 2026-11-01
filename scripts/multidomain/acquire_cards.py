"""Supplement explicitly named forms with cropped historical TCG illustrations.

Header/name regions are cropped away; some full-art scans retain text, an explicit limitation. Multi-Pokémon cards and
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
OUT=ROOT/'artifacts/multidomain'

def key(name):return re.sub('[^a-z0-9]','',name.lower().replace('♀','f').replace('♂','m'))

async def main():
    forms=json.loads((ROOT/'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    index=collections.defaultdict(list)
    for p in forms:index[key(p['englishName'])].append(p)
    extra={'ashgreninja':'greninja-ash','duskmane necrozma':'necrozma-dusk','dawnwings necrozma':'necrozma-dawn',
           'icerider calyrex':'calyrex-ice','shadowrider calyrex':'calyrex-shadow'}
    for name,identifier in extra.items():
        p=next(p for p in forms if p['formIdentifier']==identifier);index[key(name)]=[p]
    base=json.loads((ROOT/'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    review_species={25,386,479,487,492,718}
    for form in forms:
        species=next(p for p in base if p['id']==form['speciesID'])
        name=form.get('englishFormName','')
        if key(species['englishName']) in key(name):
            values=index.setdefault(key(name),[])
            if not any(p['id']==form['id'] for p in values):values.append(form)
    aliases=json.loads((ROOT/'artifacts/forms/aliases.json').read_text())
    families=collections.defaultdict(list)
    for form in forms:
        if aliases[str(form['id'])]!=aliases[str(form['speciesID'])]: families[form['speciesID']].append(form)
    for pokemon in base:
        # Region, Mega, fusion and Gigantamax cards use explicit names/modifiers.
        # Unnamed alternate appearances (Deoxys, Arceus, etc.) stay excluded.
        family=families[pokemon['id']]
        if not family or all(form['formCategory'] in ['regional','mega','gigantamax','fusion'] for form in family):
            index[key(pokemon['englishName'])]=[pokemon]
    # Explicit regional/fusion card aliases are separate from ordinary names.
    for pokemon in base:
        if pokemon['id'] in review_species:index[key(pokemon['englishName'])]=[pokemon]
    for form in forms:
        region=next((r for r in ['alola','galar','hisui','paldea'] if '-'+r in form['formIdentifier']),None)
        if region:
            prefix={'alola':'Alolan','galar':'Galarian','hisui':'Hisuian','paldea':'Paldean'}[region]
            species=next(p for p in base if p['id']==form['speciesID'])
            candidate=key(prefix+' '+species['englishName'])
            if len([f for f in forms if f['speciesID']==form['speciesID'] and '-'+region in f['formIdentifier']])==1:
                index[candidate]=[form]
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
                if original.endswith('VMAX'):
                    ordinary=next((p for p in base if key(p['englishName'])==key(name)),None)
                    if ordinary:
                        gmax=[p for p in forms if p['speciesID']==ordinary['id'] and p['formCategory']=='gigantamax']
                        if len(gmax)==1: options=gmax
                        elif len(gmax)>1: options=[]
                if name.startswith('Mega '):
                    ordinary=next((p for p in base if key(p['englishName'])==key(name[5:])),None)
                    if ordinary:
                        megas=[p for p in forms if p['speciesID']==ordinary['id'] and p['formIdentifier'].endswith('-mega')]
                        if len(megas)==1:options=megas
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
        chosen.extend(ordered[:24])
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
                records.append({'entry_id':p['id'],'path':destination.relative_to(ROOT).as_posix(),'source_path':'tcg-art/'+card_id,'source_group':'tcg-art:'+card_id,'source':'PokemonTCG-pinned-expanded','domain':'tcg_card_art',
                                'formReviewRequired':p['id'] in review_species,
                                'url':url,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'originalSHA256':hashlib.sha256(raw).hexdigest(),
                                'cardID':card_id,'cardName':card['name'],'artist':card.get('artist'),'metadataRevision':revision,
                                'crop':[.08,.20,.92,.50]})
        await asyncio.gather(*(one(item) for item in chosen))
    previous=json.loads((OUT/'card-references.json').read_text()) if (OUT/'card-references.json').exists() else []
    merged={(r['cardID'],r['entry_id']):r for r in previous}
    merged.update({(r['cardID'],r['entry_id']):r for r in records})
    records=sorted(merged.values(),key=lambda r:(r['entry_id'],r['cardID']))
    (OUT/'card-references.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'unavailable-card-images.json').write_text(json.dumps(unavailable,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Acquired {len(records)} card-art references',flush=True)

if __name__=='__main__':asyncio.run(main())

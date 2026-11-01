"""Cross-platform form identity, pixel asset, cry and frozen split checks."""
import collections
import hashlib
import json
from pathlib import Path
import wave

from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
RESOURCES=ROOT/'iDex/Resources'

def main():
    base=json.loads((RESOURCES/'pokemon-national.json').read_text(encoding='utf-8'))
    forms=json.loads((RESOURCES/'pokemon-forms.json').read_text(encoding='utf-8'))
    original=json.loads((RESOURCES/'pokemon-kanto.json').read_text(encoding='utf-8'))
    assert [{k:v for k,v in p.items() if k!='generation'} for p in base[:151]]==original
    assert [p['id'] for p in base]==list(range(1,1026))
    assert len(forms)==554
    entries=base+forms;by_id={p['id']:p for p in entries};assert len(by_id)==len(entries)
    assets=set();missing_style=[]
    for p in entries:
        if 'speciesID' in p: assert p['id']==100000+p['sourceFormID'] and p['speciesID'] in range(1,1026)
        for language in ['english','chinese','japanese']:
            for field in ['Name','Genus','Description']:assert p[language+field].strip(),(p['id'],language,field)
        assert len(p['stats'])==6 and all(0<s['value']<=255 for s in p['stats'])
        assert p['height']>0 or p.get('heightUnavailable')
        assert p['weight']>0 or p.get('weightUnavailable')
        asset=p.get('spriteAsset',f'pokemon-{p["id"]:03d}');assets.add(asset)
        path=RESOURCES/f'PokemonSprites.xcassets/{asset}.imageset/sprite.png'
        with Image.open(path) as image:
            assert image.size==(96,96) and image.convert('RGBA').getbbox(),p['id']
        if p.get('spriteReferenceOnly'):missing_style.append(p['formIdentifier'])
    cries=json.loads((RESOURCES/'Cries/cry-sources.json').read_text(encoding='utf-8'))
    cry_ids={p['id'] for p in cries}
    assert {p.get('cryID',p['id']) for p in entries}==cry_ids
    for cry in cries:
        path=RESOURCES/'Cries'/cry['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==cry['sha256']
        with wave.open(str(path)) as audio:
            assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getnframes())==(1,2,22050,cry['frames'])
    artifacts=ROOT/'artifacts/forms';coverage=json.loads((artifacts/'coverage.json').read_text(encoding='utf-8'))
    labels=json.loads((artifacts/'training-labels.json').read_text(encoding='utf-8'))
    rows=[json.loads(line) for line in (artifacts/'data/manifest.jsonl').open(encoding='utf-8') if line.strip()]
    used=[r for r in rows if r['use']]
    assert set(p['id'] for p in labels)<=by_id.keys()
    assert {p['id'] for p in labels}=={r['target_id'] for r in used if r['split']=='train'}
    groups={}
    for r in used:
        previous=groups.setdefault(r['group'],r['split']);assert previous==r['split']
    assert hashlib.sha256((artifacts/'data/manifest.jsonl').read_bytes()).hexdigest()==coverage['summary']['manifest_sha256']
    wanted=['ninetales-alola','kyurem-white','kyurem-black','necrozma-dusk','necrozma-dawn','calyrex-ice','calyrex-shadow',
            'zoroark-hisui','articuno-galar','tauros-paldea-aqua-breed','charizard-mega-x','gengar-gmax']
    chosen=[next(p for p in forms if p['formIdentifier']==identifier) for identifier in wanted]
    sheet=Image.new('RGB',(6*160,2*164),'#c4cba3');draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(chosen):
        x=i%6*160;y=i//6*164
        with Image.open(RESOURCES/f'PokemonSprites.xcassets/{p["spriteAsset"]}.imageset/sprite.png') as image:
            sprite=image.convert('RGBA');sheet.paste(sprite,(x+32,y+8),sprite)
        draw.text((x+6,y+116),f'#{p["speciesID"]:03d}',fill='#293322')
        draw.text((x+6,y+134),p['formIdentifier'][:24],fill='#293322')
    reports=artifacts/'reports';reports.mkdir(exist_ok=True)
    sheet.save(reports/'forms-pixel-review.png')
    report={'species':len(base),'additionalForms':len(forms),'catalogEntries':len(entries),'uniquePixelAssets':len(assets),
            'verifiedCryResources':len(cries),'additionalFormCategories':dict(collections.Counter(p['formCategory'] for p in forms)),
            'referenceOnlyImages':missing_style,'trainedAppearanceClasses':len(labels),'groupSplitOverlap':0,
            'confirmableClasses':sum(p['confirmed'] for p in labels),'kantoPreserved':True}
    (reports/'catalog-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()

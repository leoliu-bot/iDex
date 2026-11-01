"""Freeze form-aware, color-preserving groups before any new training.

Species-only photographs of multi-form species are excluded rather than guessed
to be the ordinary form. Visually identical mechanical variants share a target.
Every output class has real training images; sparse classes cannot auto-confirm.
"""
import collections
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import random

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/forms'
DATA = OUT / 'data'
spec = importlib.util.spec_from_file_location('national_group_helpers', ROOT/'scripts/national/data.py')
helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)

def digest(raw): return hashlib.sha256(raw).hexdigest()

def main():
    if (DATA/'split_lock.json').exists(): raise SystemExit('Form split is already frozen.')
    DATA.mkdir(parents=True,exist_ok=True); (DATA/'images').mkdir(exist_ok=True)
    base = json.loads((ROOT/'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    alternate = json.loads((ROOT/'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    catalog = {p['id']:p for p in base+alternate}
    metadata = json.loads((ROOT/'iDex/Resources/base-form-metadata.json').read_text())
    by_identifier = {v['formIdentifier']:int(k) for k,v in metadata.items()}
    by_identifier.update({p['formIdentifier']:p['id'] for p in alternate})
    canonical = {i:i for i in catalog}
    for p in alternate:
        if p.get('visualAliasOf'): canonical[p['id']] = p['visualAliasOf']
        name=p['formIdentifier']
        equivalent = name.replace('-totem-alola','-alola').replace('-totem-busted','-busted').replace('-totem-disguised','-disguised').replace('-totem','')
        if equivalent!=name and equivalent in by_identifier: canonical[p['id']]=by_identifier[equivalent]
        if name in ['rockruff-own-tempo','greninja-battle-bond','pikachu-starter','eevee-starter','zygarde-50-power-construct','sinistea-antique','polteageist-antique']:
            canonical[p['id']]=p['speciesID']
        if name=='zygarde-10-power-construct': canonical[p['id']]=by_identifier['zygarde-10']
    # The Zero Form of Palafin and Finizen cannot be identified independently
    # from their shared visible appearance. Keep this class unconfirmed.
    canonical[964]=963
    shared_gmax = by_identifier['flapple-gmax']
    canonical[by_identifier['appletun-gmax']] = shared_gmax
    root_pixels={}
    for p in base+alternate:
        if p.get('spriteReferenceOnly'): continue
        asset=p.get('spriteAsset',f'pokemon-{p["id"]:03d}')
        with Image.open(ROOT/f'iDex/Resources/PokemonSprites.xcassets/{asset}.imageset/sprite.png') as image:
            rgba=image.convert('RGBA'); bbox=rgba.getbbox()
            if not bbox: raise ValueError(('Empty sprite',p['id']))
            pixels=rgba.crop(bbox).resize((128,128),Image.Resampling.NEAREST).tobytes()
        key=(p.get('speciesID',p['id']),digest(pixels))
        if key in root_pixels: canonical[p['id']]=root_pixels[key]
        else: root_pixels[key]=canonical[p['id']]
    def target(i):
        seen=set()
        while canonical[i]!=i:
            if i in seen: raise ValueError('Alias cycle')
            seen.add(i);i=canonical[i]
        return i
    canonical={i:target(i) for i in canonical}
    families=collections.defaultdict(set)
    for p in catalog.values(): families[p.get('speciesID',p['id'])].add(canonical[p['id']])
    multi={i for i,forms in families.items() if len(forms)>1}
    original=[json.loads(line) for line in (ROOT/'artifacts/national/data/manifest.jsonl').open(encoding='utf-8')]
    rows=[]; excluded=0
    for old in original:
        if not old.get('use'): continue
        if old['target_id'] is not None and old['target_id'] in multi:
            excluded+=1;continue
        row=dict(old);row['old_group']=row['group'];row['locked_split']=row['split'];row['origin']='species_public'
        if row['target_id'] is not None: row['target_id']=canonical[row['target_id']]
        rows.append(row)
    references=json.loads((OUT/'references.json').read_text())
    if (OUT/'card-references.json').exists():
        references += json.loads((OUT/'card-references.json').read_text())
    unique={r['sha256']:r for r in references}
    def decode(item):
        sh,r=item
        raw=(ROOT/r['path']).read_bytes();im=helpers.rgb_image(raw)
        if min(im.size)<8: return sh,None
        path=DATA/'images'/f'{sh}.png'
        if not path.exists():im.save(path,optimize=False,compress_level=1)
        return sh,dict(sha256=sh,pixel_sha256=digest(f'{im.width}x{im.height}:'.encode()+im.tobytes()),
                       path=path.relative_to(ROOT).as_posix(),width=im.width,height=im.height,
                       phash=f'{helpers.phash(im):016x}',phash_mirror=f'{helpers.phash(ImageOps.mirror(im)):016x}')
    decoded={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for count,(sh,value) in enumerate(pool.map(decode,unique.items()),1):
            decoded[sh]=value
            if count%1000==0:print(f'Decoded {count}/{len(unique)} references',flush=True)
    for r in references:
        value=decoded[r['sha256']]
        if value is None: continue
        p=catalog[r['entry_id']]
        rows.append(dict(value,target_id=canonical[p['id']],source='PokemonTCG-pinned' if 'cardID' in r else 'PokeAPI-pinned-forms',domain='public_card_art' if 'cardID' in r else 'public_game_art_reference',
                         source_group=r['source_path'],member=r['source_path'],source_url=r['url'],
                         source_entry_id=p['id'],national_dex_id=p.get('speciesID',p['id']),
                         origin='form_reference',form=p.get('formIdentifier','default'),locked_split=None))
    groups=helpers.Groups(len(rows)); exact={}; by_class=collections.defaultdict(list); old_groups={}
    for i,r in enumerate(rows):
        key=r['pixel_sha256']
        if key in exact: groups.union(i,exact[key])
        else: exact[key]=i
        if 'old_group' in r:
            oldkey=(r['target_id'],r['old_group'])
            if oldkey in old_groups:groups.union(i,old_groups[oldkey])
            else:old_groups[oldkey]=i
        if r['target_id'] is not None:by_class[r['target_id']].append(i)
    # Compare poses only within a form label. Grayscale similarity across
    # different color/pattern forms is not evidence of duplicate labelling.
    for tid,indices in by_class.items():
        for at,i in enumerate(indices):
            a=rows[i]; ah=int(a['phash'],16); am=int(a['phash_mirror'],16)
            for j in indices[:at]:
                b=rows[j];bh=int(b['phash'],16)
                if min((ah^bh).bit_count(),(am^bh).bit_count())<=4:groups.union(i,j)
    clustered=collections.defaultdict(list)
    for i in range(len(rows)):clustered[groups.root(i)].append(i)
    class_groups=collections.defaultdict(list);quarantine=[]
    for indices in clustered.values():
        targets={rows[i]['target_id'] for i in indices}
        locked={rows[i]['locked_split'] for i in indices if rows[i].get('locked_split')}
        gid=digest('|'.join(sorted({rows[i]['sha256'] for i in indices})).encode())[:24]
        conflicting=len(targets)>1 or (len({s for s in locked if not s.startswith('ood')})>1)
        for i in indices:rows[i].update(group=gid,use=not conflicting,split='quarantine' if conflicting else None)
        if conflicting:
            quarantine.append({'group':gid,'targets':sorted(t for t in targets if t is not None),'reason':'Conflicting labels or previously locked splits'});continue
        tid=next(iter(targets))
        if tid is None:
            for i in indices:rows[i]['split']=rows[i]['locked_split']
        else:
            class_groups[tid].append({'id':gid,'indices':indices,'locked':next(iter(locked)) if locked else None,
                                      'paths':[rows[i].get('member','') for i in indices]})
    rng=random.Random(20261101); coverage=[];labels=[];confirmed=[]
    for tid in sorted(set(canonical.values())):
        gs=class_groups.get(tid,[]);rng.shuffle(gs)
        splits={g['id']:g['locked'] for g in gs if g['locked']}
        fresh=[g for g in gs if not g['locked']]
        roots=[g for g in fresh if any('/' not in path for path in g['paths'])]
        if not any(v=='train' for v in splits.values()) and fresh:
            chosen=roots[0] if roots else fresh[0];splits[chosen['id']]='train';fresh.remove(chosen)
        # Fresh reference holdouts are selected once, before training. Keep
        # ordinary pixel portraits in training for the app's sample path.
        if not any(v=='val' for v in splits.values()) and fresh:
            chosen=next((g for g in fresh if any('other/home/' in p for p in g['paths'])),fresh[0]);splits[chosen['id']]='val';fresh.remove(chosen)
        if not any(v and v.startswith('test') for v in splits.values()) and fresh:
            chosen=next((g for g in fresh if any('official-artwork/' in p for p in g['paths'])),fresh[0]);splits[chosen['id']]='test_forms';fresh.remove(chosen)
        for g in fresh:splits[g['id']]='train'
        for g in gs:
            for i in g['indices']:rows[i]['split']=splits[g['id']]
        ntrain=sum(s=='train' for s in splits.values());nval=sum(s=='val' for s in splits.values());ntest=sum(bool(s and s.startswith('test')) for s in splits.values())
        validated=bool(ntrain and nval and ntest and tid not in [963,shared_gmax])
        aliases=sorted(i for i,c in canonical.items() if c==tid and i!=tid)
        record={'id':tid,'name':catalog[tid]['englishName'],'nationalID':catalog[tid].get('speciesID',tid),
                'independentGroups':len(gs),'trainGroups':ntrain,'validationGroups':nval,'testGroups':ntest,
                'confirmed':validated,'aliases':aliases}
        coverage.append(record)
        if ntrain:
            labels.append({k:record[k] for k in ['id','name','nationalID','confirmed','aliases']})
            if validated:confirmed.append(tid)
        else:
            for g in gs:
                for i in g['indices']:rows[i]['use']=False
    label_ids={p['id'] for p in labels}
    for r in rows:
        if not (r.get('use') and r['split'] and (r['target_id'] is None or r['target_id'] in label_ids)):r['use']=False
    usable=[r for r in rows if r['use']]
    # Split boundaries apply to groups, not files or augmented copies.
    split_sets={s:{r['group'] for r in usable if r['split']==s} for s in {r['split'] for r in usable}}
    for s,ids in split_sets.items():
        for t,other in split_sets.items():
            if s!=t:assert not ids&other,(s,t)
    manifest=DATA/'manifest.jsonl'
    with manifest.open('w',encoding='utf-8',newline='\n') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    (OUT/'training-labels.json').write_text(json.dumps(labels,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'aliases.json').write_text(json.dumps(canonical,indent=2)+'\n',encoding='utf-8',newline='\n')
    (ROOT/'iDex/Resources/appearance-aliases.json').write_text(json.dumps({i:c for i,c in canonical.items() if i!=c},indent=2)+'\n',encoding='utf-8',newline='\n')
    report={'catalogEntries':len(catalog),'trainedAppearanceClasses':len(labels),'confirmableClasses':len(confirmed),
            'speciesOnlyImagesExcludedForAmbiguousForms':excluded,'rows':len(rows),'usableRows':len(usable),
            'splits':dict(collections.Counter(r['split'] for r in usable)),'quarantinedGroups':len(quarantine),
            'manifest_sha256':digest(manifest.read_bytes()),'seed':20261101,
            'caveat':'Public artwork/reference groups. Previous species public holdouts are reused diagnostics, not a new independent camera benchmark. Sparse appearance classes may be trained but cannot auto-confirm.'}
    (OUT/'coverage.json').write_text(json.dumps({'summary':report,'classes':coverage,'missingEntryIDs':sorted(i for i,c in canonical.items() if c not in label_ids)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (DATA/'split_lock.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()

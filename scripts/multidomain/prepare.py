"""Freeze expanded source groups while retaining the prior campaign boundaries."""
import collections
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
import random
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'artifacts/multidomain'
DATA = OUT/'data'
spec = importlib.util.spec_from_file_location('group_helpers', ROOT/'scripts/national/data.py')
helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def main():
    if (DATA/'split_lock.json').exists(): raise ValueError('Expanded split is already frozen')
    DATA.mkdir(exist_ok=True); (DATA/'images').mkdir(exist_ok=True)
    labels = json.loads((OUT/'training-labels.json').read_text(encoding='utf-8'))
    label_ids = {p['id'] for p in labels}
    aliases = {int(k):v for k,v in json.loads((ROOT/'artifacts/forms/aliases.json').read_text()).items()}
    rows = []
    for old in map(json.loads, (ROOT/'artifacts/forms/data/manifest.jsonl').read_text(encoding='utf-8').splitlines()):
        if not old['use']: continue
        row = dict(old, old_group=old['group'], locked_split=old['split'], origin='prior_form_campaign')
        rows.append(row)
    references = []
    for name in ['mixed','game','card','plush']:
        references += json.loads((OUT/f'{name}-references.json').read_text(encoding='utf-8'))
    review_path = OUT/'review/domain-review.json'
    reviewed = json.loads(review_path.read_text()) if review_path.exists() else {}
    unique = {p['sha256']:p for p in references if aliases.get(p['entry_id'],p['entry_id']) in label_ids}
    def decode(item):
        source_sha, ref = item
        with Image.open(ROOT/ref['path']) as original:
            rgba = ImageOps.exif_transpose(original).convert('RGBA')
            rgb = Image.alpha_composite(Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
            rgb.thumbnail((640,640))
            side = max(rgb.size)
            image = Image.new('RGB',(side,side),'white')
            image.paste(rgb,((side-rgb.width)//2,(side-rgb.height)//2))
        destination = DATA/'images'/f'{source_sha}.png'
        image.save(destination,compress_level=1)
        return source_sha,dict(path=destination.relative_to(ROOT).as_posix(),sha256=digest(destination.read_bytes()),
            pixel_sha256=digest(f'{image.width}x{image.height}:'.encode()+image.tobytes()),
            width=image.width,height=image.height,phash=f'{helpers.phash(image):016x}',
            phash_mirror=f'{helpers.phash(ImageOps.mirror(image)):016x}')
    decoded = {}
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        for count,(key,value) in enumerate(pool.map(decode,unique.items()),1):
            decoded[key] = value
            if count%2000==0: print(f'Decoded {count}/{len(unique)} extra images',flush=True)
    for ref in references:
        target = aliases.get(ref['entry_id'],ref['entry_id'])
        if target not in label_ids: continue
        value = decoded[ref['sha256']]
        domain = reviewed.get(ref['sha256'],{}).get('domain',ref.get('domain','tcg_card_art'))
        rows.append(dict(value,target_id=target,source=ref.get('source','PokemonTCG-pinned-expanded'),domain=domain,
            source_group=ref.get('source_group','tcg-art:'+ref.get('cardID','unknown')),
            source_entry_id=ref['entry_id'],member=ref['source_path'],source_sha256=ref['sha256'],
            source_url=ref.get('url'),origin='expanded_sources',locked_split=None,
            form=next(p['name'] for p in labels if p['id']==target)))
    groups = helpers.Groups(len(rows)); exact = {}; old_groups = {}; source_groups = {}; classes = collections.defaultdict(list)
    for i,row in enumerate(rows):
        if row['pixel_sha256'] in exact: groups.union(i,exact[row['pixel_sha256']])
        else: exact[row['pixel_sha256']] = i
        if 'old_group' in row:
            if row['old_group'] in old_groups: groups.union(i,old_groups[row['old_group']])
            else: old_groups[row['old_group']] = i
        else:
            source_key = (row['source'],row['source_group'])
            if source_key in source_groups: groups.union(i,source_groups[source_key])
            else: source_groups[source_key] = i
        if row['target_id'] is not None: classes[row['target_id']].append(i)
    for tid,indices in classes.items():
        for at,i in enumerate(indices):
            a=rows[i]; ah=int(a['phash'],16); am=int(a['phash_mirror'],16)
            for j in indices[:at]:
                b=rows[j]; threshold=6 if 'card' in a['domain'] and 'card' in b['domain'] else 4
                if min((ah^int(b['phash'],16)).bit_count(),(am^int(b['phash'],16)).bit_count())<=threshold:
                    groups.union(i,j)
    clustered=collections.defaultdict(list)
    for i in range(len(rows)): clustered[groups.root(i)].append(i)
    unlocked=collections.defaultdict(list); quarantined=[]
    for indices in clustered.values():
        targets={rows[i]['target_id'] for i in indices}
        locked={rows[i]['locked_split'] for i in indices if rows[i].get('locked_split')}
        gid=digest('|'.join(sorted({rows[i]['sha256'] for i in indices})).encode())[:24]
        bad=len(targets)>1 or len(locked)>1
        if bad: quarantined.append({'group':gid,'targets':sorted(str(t) for t in targets),'lockedSplits':sorted(locked)})
        split='quarantine' if bad else next(iter(locked)) if locked else None
        for i in indices:rows[i].update(group=gid,use=not bad,split=split)
        if not bad and split is None:unlocked[next(iter(targets))].append((gid,indices))
    rng=random.Random(20261119)
    for tid,items in sorted(unlocked.items()):
        rng.shuffle(items);n=len(items)
        ntest=max(1,round(n*.15)) if n>=2 else 0
        nval=max(1,round(n*.15)) if n>=3 else 0
        for at,(_,indices) in enumerate(items):
            split='test_multidomain' if at<ntest else 'val' if at<ntest+nval else 'train'
            for i in indices:rows[i]['split']=split
    usable=[r for r in rows if r['use']]
    assert {r['target_id'] for r in usable if r['split']=='train'}==label_ids
    seen={}
    for row in usable:
        previous=seen.setdefault(row['group'],row['split']);assert previous==row['split']
    manifest=DATA/'manifest.jsonl'
    manifest.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8',newline='\n')
    report={'manifest_sha256':digest(manifest.read_bytes()),'seed':20261119,'classes':len(labels),
        'rows':len(rows),'usableRows':len(usable),'quarantinedGroups':len(quarantined),'groupSplitOverlap':0,
        'splits':dict(collections.Counter(r['split'] for r in usable)),
        'domainsBySplit':{s:dict(collections.Counter(r['domain'] for r in usable if r['split']==s)) for s in sorted({r['split'] for r in usable})},
        'limits':'Public images and manufacturer product shots. Prior holdouts are retained/reused diagnostics. Anime episode/capture-session provenance is incomplete; source/perceptual groups do not certify independent camera accuracy.'}
    (DATA/'split_lock.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'quarantine.json').write_text(json.dumps(quarantined,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__': main()

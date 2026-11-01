"""Cache exact official form pages for editorial, paraphrased field notes."""
import concurrent.futures
import hashlib
import html
import json
from pathlib import Path
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT/'.catalog-cache/regional-notes'
OUT = ROOT/'artifacts/multidomain/regional-notes-research.json'
HOST = 'https://dex.pokemon.cn'


def clean(text):
    return re.sub(r'\s+', '', html.unescape(re.sub('<[^>]*>', '', text)))


def get(path):
    cache = CACHE/(path.rsplit('/',1)[-1]+'.html')
    if cache.exists(): return cache.read_bytes()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(HOST+path,timeout=45) as response:raw=response.read()
            cache.write_bytes(raw)
            time.sleep(.1)
            return raw
        except Exception:
            if attempt==3:raise
            time.sleep(attempt+1)


def parse(path):
    raw=get(path);page=raw.decode('utf-8')
    title=re.search(r'class="pokemon-slider__main-subname[^\"]*"[^>]*>(.*?)</p>',page,re.S)
    name=re.search(r'class="pokemon-slider__main-name[^\"]*"[^>]*>(.*?)</p>',page,re.S)
    stories=re.findall(r'<p[^>]*class="pokemon-story__body[^\"]*"[^>]*>(.*?)</p>',page,re.S)
    return dict(url=HOST+path,formLabel=clean(title[1]) if title else '',name=clean(name[1]) if name else '',
                stories=list(dict.fromkeys(clean(s) for s in stories)),pageSHA256=hashlib.sha256(raw).hexdigest())


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    forms=json.loads((ROOT/'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    wanted=[p for p in forms if p['formCategory'] in ['regional','fusion']]
    all_paths=set()
    for sid in sorted({p['speciesID'] for p in wanted}):
        path=f'/play/pokedex/{sid:04d}'
        page=get(path).decode('utf-8')
        paths=set(re.findall(r'href="(/play/pokedex/'+f'{sid:04d}'+r'(?:_\d+)?)"',page))
        all_paths.update(paths or [path])
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        pages=list(pool.map(parse,sorted(all_paths)))
    result=[]
    for p in wanted:
        candidates=[s for s in pages if re.search('/'+f'{p["speciesID"]:04d}'+r'(?:_\d+)?$',s['url'])]
        name=p['formIdentifier']
        if p['formCategory']=='regional':
            marker=next(local for token,local in [('alola','阿罗拉'),('galar','伽勒尔'),('hisui','洗翠'),('paldea','帕底亚')] if token in name)
            candidates=[s for s in candidates if marker in s['formLabel']]
            if p['speciesID']==555:
                candidates=[s for s in candidates if ('达摩' in s['formLabel'])==name.endswith('-zen')]
            if p['speciesID']==128:
                marker=next(m for token,m in [('combat','斗战'),('blaze','火炽'),('aqua','水澜')] if token in name)
                candidates=[s for s in candidates if marker in s['formLabel']]
        else:
            marker={'kyurem-white':'焰白','kyurem-black':'暗黑','necrozma-dusk':'黄昏','necrozma-dawn':'拂晓','calyrex-ice':'白马','calyrex-shadow':'黑马'}[name]
            candidates=[s for s in candidates if marker in s['formLabel']]
        result.append(dict(identifier=name,entryID=p['id'],candidates=candidates))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'records':len(result),'matched':sum(len(p['candidates'])==1 for p in result),
                      'unresolved':[p['identifier'] for p in result if len(p['candidates'])!=1]}),flush=True)


if __name__=='__main__':main()

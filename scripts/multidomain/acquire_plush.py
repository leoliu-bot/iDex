"""Actual manufacturer plush photographs, grouped by product/JAN, not by view."""
import asyncio
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
import aiohttp
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/multidomain'
BASE = 'https://www.san-ei-boeki.co.jp'


def clean(value):
    return html.unescape(re.sub('<[^>]+>', '', value)).strip()


def key(value):
    return re.sub(r'[\s()（）・･－\-：:]', '', unicodedata.normalize('NFKC', value))


async def main():
    cache = OUT / 'sources/sanei'
    cache.mkdir(parents=True, exist_ok=True)
    base = json.loads((ROOT / 'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    forms = json.loads((ROOT / 'iDex/Resources/pokemon-forms.json').read_text(encoding='utf-8'))
    index = {}
    for p in base + forms:
        index.setdefault(key(p['japaneseName']), set()).add(p['id'])
        if p.get('japaneseFormName'):
            species = next(b for b in base if b['id'] == p['speciesID'])
            index.setdefault(key(species['japaneseName'] + p['japaneseFormName']), set()).add(p['id'])
    semaphore = asyncio.Semaphore(3)
    failures = []
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=70),
                                    headers={'User-Agent': 'PokedexDatasetResearch/1.3 (personal offline research)'}) as session:
        async def get(url):
            path = cache / (hashlib.sha256(url.encode()).hexdigest() + ('.jpg' if '/uploads/' in url else '.html'))
            if path.exists(): return path.read_bytes()
            async with semaphore:
                for attempt in range(4):
                    try:
                        async with session.get(url) as response:
                            response.raise_for_status()
                            raw = await response.read()
                        path.write_bytes(raw)
                        await asyncio.sleep(.15)
                        return raw
                    except Exception as error:
                        if attempt == 3:
                            failures.append({'url': url, 'error': str(error)})
                            return None
                        await asyncio.sleep(attempt + 2)
        page = (await get(BASE + '/character/pap/')).decode('utf-8')
        urls = set(re.findall(r'https://www\.san-ei-boeki\.co\.jp/character/pap/pap\d+/\d+/', page))
        # Follow category pagination when present; a cached page is a frozen receipt.
        for number in range(2, 6):
            if f'/character/pap/page/{number}/' not in page: break
            raw = await get(BASE + f'/character/pap/page/{number}/')
            if raw:
                page = raw.decode('utf-8')
                urls.update(re.findall(r'https://www\.san-ei-boeki\.co\.jp/character/pap/pap\d+/\d+/', page))
        print(f'Inspecting {len(urls)} manufacturer product pages', flush=True)
        records, unmapped = [], []
        async def one(url):
            raw = await get(url)
            if not raw: return
            text = raw.decode('utf-8')
            title = re.search(r'<th[^>]*>\s*商品名\s*</th>\s*<td[^>]*>(.*?)</td>', text, re.S)
            jan = re.search(r'<th[^>]*>\s*JAN\s*</th>\s*<td[^>]*>(.*?)</td>', text, re.S)
            if not title or not jan: return
            title = clean(title[1]); jan = clean(jan[1])
            stripped = re.sub(r'^[A-Z]+\d+(?:-\d+)?\s*', '', unicodedata.normalize('NFKC', title))
            stripped = re.sub(r'\s*\((?:S|M|L|LL|SS|大|小)\)\s*$', '', stripped)
            options = index.get(key(stripped), set())
            if len(options) != 1:
                unmapped.append({'url': url, 'title': title, 'normalized': stripped})
                return
            number = next(iter(options))
            images = list(dict.fromkeys(html.unescape(u) for u in re.findall(r'<img[^>]+src="([^"]+/uploads/[^\"]+\.(?:jpg|jpeg|png))"', text, re.I)))
            images = [u for u in images if jan and jan in u][:5]
            for image_url in images:
                data = await get(image_url)
                if not data: continue
                source_sha = hashlib.sha256(data).hexdigest()
                destination = cache / 'images' / f'{source_sha}.png'
                destination.parent.mkdir(exist_ok=True)
                import io
                with Image.open(io.BytesIO(data)) as original:
                    image = ImageOps.exif_transpose(original).convert('RGBA')
                    image = Image.alpha_composite(Image.new('RGBA', image.size, 'white'), image).convert('RGB')
                    image.thumbnail((640, 640)); image.save(destination)
                records.append(dict(entry_id=number, path=destination.relative_to(ROOT).as_posix(),
                    sha256=hashlib.sha256(destination.read_bytes()).hexdigest(), originalSHA256=source_sha,
                    source='sanei-manufacturer', domain='real_plush_product_photo', source_group='sanei:'+jan,
                    source_path=image_url, url=image_url, productURL=url, productName=title,
                    productPageSHA256=hashlib.sha256(raw).hexdigest()))
        await asyncio.gather(*(one(u) for u in sorted(urls)))
    records.sort(key=lambda r:(r['entry_id'], r['source_path']))
    for name, value in [('plush-references',records), ('plush-unmapped',unmapped), ('plush-unavailable',failures)]:
        (OUT / (name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'images':len(records),'products':len({r['source_group'] for r in records}),
                      'entries':len({r['entry_id'] for r in records}),'unmappedProducts':len(unmapped),'failed':len(failures)}), flush=True)


if __name__ == '__main__': asyncio.run(main())

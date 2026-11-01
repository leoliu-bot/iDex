"""Download official open TTS weights to the ignored PC-only generation cache."""
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/voices'
MODELS = {'design': 'Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign', 'base': 'Qwen/Qwen3-TTS-12Hz-0.6B-Base'}


def get_json(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=90) as response: return json.load(response)
        except Exception:
            if attempt == 4: raise
            time.sleep(2 + attempt)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1_024 * 1_024), b''): digest.update(block)
    return digest.hexdigest()


def download_large(lock):
    """Bounded parallel ranges avoid very slow single-stream model transfers."""
    chunk_size = 16 * 1_024 * 1_024
    unique = {}
    aliases = []
    for key, model in lock.items():
        for file in model['files']:
            if file['size'] < 100_000_000: continue
            destination = OUT/'models'/key/file['name']
            if file['sha256'] in unique:
                aliases.append((destination, unique[file['sha256']][0])); continue
            unique[file['sha256']] = (destination, model, file)
    tasks = []
    for digest, (destination, model, file) in unique.items():
        if destination.exists() and destination.stat().st_size == file['size'] and sha(destination) == digest: continue
        chunks = OUT/'range-cache'/digest
        chunks.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name+'.partial')
        if partial.exists():
            with partial.open('rb') as stream:
                for index in range(partial.stat().st_size//chunk_size):
                    target = chunks/f'{index:05d}.part'
                    data = stream.read(chunk_size)
                    if not target.exists(): target.write_bytes(data)
        for index, start in enumerate(range(0, file['size'], chunk_size)):
            end = min(file['size'],start+chunk_size)-1
            target = chunks/f'{index:05d}.part'
            if target.exists() and target.stat().st_size==end-start+1: continue
            tasks.append((target, model, file, start, end))
    print(f'Fetching {len(tasks)} verified model ranges with 16 connections',flush=True)
    def fetch(item):
        target, model, file, start, end = item
        for attempt in range(6):
            try:
                url=f'https://huggingface.co/{model["repo"]}/resolve/{model["revision"]}/{file["name"]}?download=true&request={time.time_ns()}'
                request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=160) as response:
                    assert response.status==206, 'Model server did not honor bounded range'
                    raw=response.read(end-start+2)
                assert len(raw)==end-start+1
                target.write_bytes(raw)
                return
            except Exception:
                if attempt==5: raise
                time.sleep(2+attempt)
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        for count,_ in enumerate(pool.map(fetch,tasks),1):
            if count%16==0: print(f'Model ranges {count}/{len(tasks)}',flush=True)
    for digest,(destination,model,file) in unique.items():
        if destination.exists() and destination.stat().st_size==file['size'] and sha(destination)==digest: continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        combined=destination.with_name(destination.name+'.assembled')
        with combined.open('wb') as stream:
            for index in range((file['size']+chunk_size-1)//chunk_size):stream.write((OUT/'range-cache'/digest/f'{index:05d}.part').read_bytes())
        assert combined.stat().st_size==file['size'] and sha(combined)==digest
        combined.replace(destination)
        print(json.dumps({'verifiedModel':str(destination.relative_to(OUT)),'bytes':file['size']}),flush=True)
    for destination,original in aliases:
        if destination.exists(): continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.hardlink_to(original)


def main():
    lock_path = OUT / 'model-sources.json'
    if lock_path.exists(): lock = json.loads(lock_path.read_text())
    else:
        lock = {}
        for key, repo in MODELS.items():
            info = get_json('https://huggingface.co/api/models/' + repo)
            revision = info['sha']
            tree = get_json(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true')
            files = []
            for row in tree:
                if row['type'] != 'file': continue
                name = row['path']
                if not name.endswith(('.json', '.safetensors', '.onnx', '.txt', '.model')) and name != 'LICENSE': continue
                if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts: raise ValueError(name)
                files.append({'name': name, 'size': row['size'], 'sha256': row.get('lfs', {}).get('oid')})
            lock[key] = {'repo': repo, 'revision': revision, 'files': files}
        lock_path.write_text(json.dumps(lock, indent=2)+'\n', encoding='utf-8', newline='\n')
    download_large(lock)
    pending = [(key, model, file) for key, model in lock.items() for file in model['files'] if file['size'] < 100_000_000]
    def fetch(item):
        key, model, file = item
        destination = OUT / 'models' / key / file['name']
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size == file['size']:
            if not file['sha256'] or sha(destination) == file['sha256']: return
        partial = destination.with_name(destination.name + '.partial')
        base_url = f'https://huggingface.co/{model["repo"]}/resolve/{model["revision"]}/{file["name"]}'
        for attempt in range(6):
            try:
                # Avoid cached, expired signed redirects from large-file CDNs.
                url = base_url + f'?download=true&request={time.time_ns()}'
                offset = partial.stat().st_size if partial.exists() else 0
                request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
                with urllib.request.urlopen(request, timeout=180) as response:
                    append = offset > 0 and response.status == 206
                    with partial.open('ab' if append else 'wb') as stream:
                        while block := response.read(2 * 1_024 * 1_024): stream.write(block)
                assert partial.stat().st_size == file['size'], file['name']
                if file['sha256']: assert sha(partial) == file['sha256'], file['name']
                partial.replace(destination)
                print(json.dumps({'model': key, 'file': file['name'], 'bytes': file['size']}), flush=True)
                return
            except Exception as error:
                print(json.dumps({'file':file['name'],'attempt':attempt,'error':str(error)[:180]}),flush=True)
                if attempt == 5: raise
                time.sleep(attempt + 3)
    with concurrent.futures.ThreadPoolExecutor(4) as pool: list(pool.map(fetch, pending))
    print('Official TTS weights verified and ready for local generation.', flush=True)


if __name__ == '__main__': main()

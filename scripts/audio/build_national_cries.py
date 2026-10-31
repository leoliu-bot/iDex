#!/usr/bin/env python3
"""Extend the original PCM WAV cry collection; preserve verified Kanto files."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import wave
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'catalog'))
from build_national_catalog import download

ROOT = Path(__file__).resolve().parents[2]
REVISION = 'b3a9044bb839b5e3152aaa536c7b463a0fcf0140'
BASE = f'https://raw.githubusercontent.com/PokeAPI/cries/{REVISION}'
OUTPUT = ROOT / 'iDex/Resources/Cries'
CACHE = ROOT / '.catalog-cache/cries' / REVISION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    args = parser.parse_args()
    if not args.ffmpeg:
        raise SystemExit('Pass --ffmpeg to the development-only ffmpeg executable.')
    entries = json.loads((ROOT / 'iDex/Resources/pokemon-national.json').read_text(encoding='utf-8'))
    existing = {p['id']: p for p in json.loads((OUTPUT / 'cry-sources.json').read_text(encoding='utf-8'))}
    def build(entry):
        number = entry['id']
        destination = OUTPUT / f'pokemon-cry-{number:03d}.wav'
        previous = existing.get(number)
        if previous and destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == previous['sha256']:
            return previous
        relative = f'cries/pokemon/latest/{number}.ogg'
        source = CACHE / relative
        data = download(f'{BASE}/{relative}', source)
        subprocess.run([args.ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', str(source),
                        '-map_metadata', '-1', '-ac', '1', '-ar', '22050', '-c:a', 'pcm_s16le',
                        '-fflags', '+bitexact', '-flags:a', '+bitexact', str(destination)], check=True)
        with wave.open(str(destination)) as audio:
            assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
            assert audio.getframerate() == 22050 and audio.getnframes() > 0
            frames = audio.getnframes()
        return {'id': number, 'name': entry['englishName'], 'file': destination.name,
                'source': f'{BASE}/{relative}', 'sourceSHA256': hashlib.sha256(data).hexdigest(),
                'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'frames': frames, 'sampleRate': 22050}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        manifest = []
        for count, record in enumerate(pool.map(build, entries), 1):
            manifest.append(record)
            if count % 100 == 0:
                print(f'Verified {count}/{len(entries)} cries', flush=True)
    (OUTPUT / 'cry-sources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'Bundled {len(manifest)} verified PCM WAV cries.', flush=True)


if __name__ == '__main__':
    main()

"""Add only real, pinned variant cries; otherwise reuse the species cry."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import wave

import imageio_ffmpeg

sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_national_cries import ROOT, REVISION, BASE, OUTPUT, CACHE, download

def main():
    forms_path=ROOT/'iDex/Resources/pokemon-forms.json'
    forms=json.loads(forms_path.read_text(encoding='utf-8'))
    tree=json.loads((ROOT/'.catalog-cache/cries-tree.json').read_text())
    if tree.get('truncated'):raise ValueError('Incomplete cry source listing')
    available={r['path']:r for r in tree['tree'] if r['type']=='blob'}
    existing={p['id']:p for p in json.loads((OUTPUT/'cry-sources.json').read_text(encoding='utf-8'))}
    wanted={}
    for p in forms:
        pid=p['sourcePokemonID']
        relative=f'cries/pokemon/latest/{pid}.ogg'
        if pid>1025 and relative in available:
            p['cryID']=pid;wanted.setdefault(pid,p)
        else:p['cryID']=p['speciesID']
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    def build(item):
        pid,p=item;destination=OUTPUT/f'pokemon-cry-{pid:03d}.wav'
        if pid in existing and destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()==existing[pid]['sha256']:
            return existing[pid]
        relative=f'cries/pokemon/latest/{pid}.ogg';source=CACHE/relative
        raw=download(BASE+'/'+relative,source)
        assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==available[relative]['sha']
        subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',str(source),'-map_metadata','-1','-ac','1','-ar','22050','-c:a','pcm_s16le','-fflags','+bitexact','-flags:a','+bitexact',str(destination)],check=True)
        with wave.open(str(destination)) as audio:
            assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(1,2,22050)
            frames=audio.getnframes();assert frames>0
        return {'id':pid,'name':p['englishName'],'file':destination.name,'source':BASE+'/'+relative,
                'sourceSHA256':hashlib.sha256(raw).hexdigest(),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'frames':frames,'sampleRate':22050}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for record in pool.map(build,wanted.items()):existing[record['id']]=record
    (OUTPUT/'cry-sources.json').write_text(json.dumps([existing[i] for i in sorted(existing)],ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    forms_path.write_text(json.dumps(forms,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Added/verified {len(wanted)} variant cries; {len(existing)} total unique cry resources',flush=True)

if __name__=='__main__':main()

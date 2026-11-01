"""Bounded, checkpointed RTX training and inference on a frozen grouped manifest."""
import argparse
import collections
import hashlib
import json
import os
import random
import shutil
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import PIL
from PIL import Image
import psutil
import torch
import torchvision
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms as T
from model import LABELS, make_model, load_checkpoint, same_head


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


class Images(Dataset):
    def __init__(self,rows,size,training=False):
        self.rows=rows
        self.target_indices={label['id']: index for index,label in enumerate(json.loads(LABELS.read_text(encoding='utf-8')))}
        # App import centers a square then scales. PIL approximates CoreGraphics;
        # Apple golden-pixel harness is the final preprocessing parity gate.
        if training:
            clean=T.Compose([T.RandomResizedCrop(size,scale=(.8,1),ratio=(.9,1.1)),T.RandomHorizontalFlip(),T.ColorJitter(.12,.12,.08,.01),T.ToTensor()])
            camera=T.Compose([T.RandomResizedCrop(size,scale=(.55,1),ratio=(.8,1.2)),T.RandomHorizontalFlip(),T.RandomPerspective(distortion_scale=.18,p=.4,fill=255),T.RandomRotation(14,fill=255),T.ColorJitter(.3,.25,.15,.015),T.RandomApply([T.GaussianBlur(3,sigma=(.15,1.1))],p=.15),T.ToTensor(),T.RandomErasing(p=.1,scale=(.01,.06),ratio=(.5,2),value='random')])
            self.transform=T.RandomChoice([clean,camera],p=[.35,.65])
        else: self.transform=T.Compose([T.CenterCrop(size=1),T.ToTensor()])
        self.size=size; self.training=training
        self.card_transform=T.Compose([T.RandomResizedCrop(size,scale=(.85,1),ratio=(.9,1.1)),
            T.RandomPerspective(distortion_scale=.14,p=.45,fill=245),T.RandomRotation(10,fill=245),
            T.ColorJitter(.25,.2,.12,.01),T.RandomApply([T.GaussianBlur(3,sigma=(.2,.8))],p=.1),T.ToTensor()])
    def __len__(self): return len(self.rows)
    def __getitem__(self,i):
        row=self.rows[i]
        with Image.open(row['path']) as src:
            im=src.convert('RGB')
            if self.training: x=(self.card_transform if row['domain']=='tcg_masked_card_scan' else self.transform)(im)
            else:
                side=min(im.size); left=(im.width-side)//2; top=(im.height-side)//2
                im=im.crop((left,top,left+side,top+side)).resize((self.size,self.size),Image.Resampling.BILINEAR)
                x=T.functional.to_tensor(im)
        target=self.target_indices[row['target_id']] if row['target_id'] is not None else -1
        return x,target,i


def rows_from(manifest,split):
    return [r for r in (json.loads(s) for s in manifest.read_text(encoding='utf-8').splitlines()) if r['use'] and r['split'] in split.split(',')]


def loader(rows,args,training=False):
    sampler = None
    if training:
        counts = {label['id']: 0 for label in json.loads(LABELS.read_text(encoding='utf-8'))}
        domain_counts = {}
        group_counts = collections.Counter(row['group'] for row in rows)
        for row in rows:
            counts[row['target_id']] += 1
            key = (row['target_id'],row['domain'])
            domain_counts[key] = domain_counts.get(key,0) + 1
        weights = [1.0 / (counts[row['target_id']] ** args.class_balance
                   * domain_counts[(row['target_id'],row['domain'])] ** args.domain_balance
                   * group_counts[row['group']] ** args.group_balance) for row in rows]
        sampler = WeightedRandomSampler(weights, len(rows), replacement=True)
    return DataLoader(Images(rows,args.size,training),batch_size=args.batch,shuffle=False,sampler=sampler,num_workers=args.workers,pin_memory=True,persistent_workers=False)


@torch.inference_mode()
def validation(model, batches):
    model.eval(); total=correct=0; loss=0.
    class_counts=collections.defaultdict(lambda:[0,0])
    domain_counts=collections.defaultdict(lambda:[0,0])
    grouped=collections.defaultdict(lambda:[0,0])
    for x,y,indices in batches:
        x=x.cuda(non_blocking=True); y=y.cuda(non_blocking=True)
        out=model(x); loss+=torch.nn.functional.cross_entropy(out,y,reduction='sum').item()
        for prediction,target,index in zip(out.argmax(1).cpu().tolist(),y.cpu().tolist(),indices.tolist()):
            row=batches.dataset.rows[index];domain=row['domain']
            family=('toys' if 'plush' in domain or 'figure' in domain else
                    'cards' if 'card' in domain else 'anime' if 'anime' in domain else
                    'game' if 'game' in domain or 'sprite' in domain else 'mixed')
            hit=int(prediction==target);correct+=hit;total+=1
            for counter in [class_counts[target],domain_counts[family],grouped[(family,row['group'])]]:
                counter[0]+=hit;counter[1]+=1
    macro=float(np.mean([c/n for c,n in class_counts.values()]))
    domains={}
    for family,(c,n) in domain_counts.items():
        scores=[c/n for (d,g),(c,n) in grouped.items() if d==family]
        domains[family]=dict(top1=c/n,images=n,groups=len(scores),group_top1=float(np.mean(scores)))
    eligible=[d['group_top1'] for d in domains.values() if d['images']>=30 and d['groups']>=5]
    balanced=float(np.mean(eligible)) if eligible else correct/total
    return dict(top1=correct/total,macro_recall=macro,domain_group_mean=balanced,
                selection_score=.5*macro+.5*balanced,domains=domains,loss=loss/total,n=total)


def deduplicate(rows):
    unique={}
    for row in rows:
        previous=unique.setdefault(row['sha256'],row)
        if any(previous[key]!=row[key] for key in ['target_id','group','split']):
            raise ValueError('Conflicting duplicate source image')
    return list(unique.values())


def run_train(args):
    if args.out.exists() and not args.resume: raise ValueError('Run already exists; resume explicitly or use a fresh path')
    args.out.mkdir(parents=True,exist_ok=True)
    lock=args.manifest.parent/'split_lock.json'
    assert lock.exists(),'Freeze data first'
    manifest_sha=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    assert json.loads(lock.read_text())['manifest_sha256']==manifest_sha
    tr=deduplicate(rows_from(args.manifest,'train')); va=deduplicate(rows_from(args.manifest,'val'))
    assert set(r['target_id'] for r in tr)==set(x["id"] for x in json.loads(LABELS.read_text(encoding="utf-8")))
    assert not {r['group'] for r in tr}&{r['group'] for r in va}
    model=make_model(args.arch,pretrained=True).cuda().to(memory_format=torch.channels_last)
    if args.init_checkpoint:
        initial=torch.load(args.init_checkpoint,map_location='cpu',weights_only=True)
        current_labels=json.loads(LABELS.read_text(encoding='utf-8'))
        labels_match=initial['labels']==current_labels or (args.transfer and same_head(initial['labels'],current_labels))
        if (initial['manifest_sha256']!=manifest_sha and not args.transfer) or not labels_match or initial['config']['arch']!=args.arch or initial['config']['size']!=args.size:
            raise ValueError('Explicit continuation checkpoint contract mismatch')
        model.load_state_dict(initial['model'],strict=True)
    optimizer=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=.01)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs)
    start=0; best=-1.; labels=json.loads(LABELS.read_text(encoding='utf-8'))
    if args.resume:
        state=torch.load(args.out/'last.pt',map_location='cpu',weights_only=True)
        if state['manifest_sha256']!=manifest_sha: raise ValueError('resume manifest mismatch')
        if state['config']['arch']!=args.arch or state['config']['size']!=args.size: raise ValueError('resume model config mismatch')
        for key in ['seed','epochs','lr','batch','workers','class_balance','domain_balance','group_balance']:
            if state['config'][key]!=getattr(args,key): raise ValueError(f'resume {key} mismatch; create a new explicit continuation run')
        model.load_state_dict(state['model']); optimizer.load_state_dict(state['optimizer']); scheduler.load_state_dict(state['scheduler'])
        start=state['epoch']; best=state['best_val']
    train_loader=loader(tr,args,True); val_loader=loader(va,args)
    config={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
    if args.init_checkpoint: config['init_checkpoint_sha256']=hashlib.sha256(args.init_checkpoint.read_bytes()).hexdigest()
    code_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in Path('scripts/multidomain').glob('*.py')}
    (args.out/'source').mkdir(exist_ok=True)
    for file in Path('scripts/multidomain').glob('*.py'): shutil.copy2(file,args.out/'source'/file.name)
    env=dict(python=os.sys.version,torch=str(torch.__version__),torchvision=str(torchvision.__version__),PIL=PIL.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),seed=args.seed,parameters=sum(p.numel() for p in model.parameters()),config=config,manifest_sha256=manifest_sha,code_hashes=code_hashes)
    (args.out/'environment.json').write_text(json.dumps(env,indent=2))
    began=time.time(); interrupted=False; last_epoch=start
    torch.cuda.reset_peak_memory_stats()
    for epoch in range(start,args.epochs):
        if time.time()-began>args.max_minutes*60: interrupted=True; break
        # Seed per epoch makes epoch-boundary recovery reproducible (worker count fixed).
        seed_everything(args.seed+epoch); tick=time.time(); model.train(); loss_sum=0.; total=0
        for x,y,_ in train_loader:
            x=x.cuda(non_blocking=True).contiguous(memory_format=torch.channels_last); y=y.cuda(non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                logits=model(x); loss=torch.nn.functional.cross_entropy(logits,y,label_smoothing=.05)
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),5.); optimizer.step()
            loss_sum+=loss.item()*len(y); total+=len(y)
        scores=validation(model,val_loader); scheduler.step()
        last_epoch=epoch+1
        improved=scores['selection_score']>best; best=max(best,scores['selection_score'])
        # State dict only: no remote class or pickled module needed to restore.
        checkpoint=dict(model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),epoch=epoch+1,best_val=best,validation=scores,config=config,labels=labels,manifest_sha256=manifest_sha)
        temp=args.out/'last.partial'; torch.save(checkpoint,temp); temp.replace(args.out/'last.pt')
        if improved:
            torch.save(dict(model=checkpoint['model'],epoch=epoch+1,best_val=best,validation=scores,config=config,labels=labels,manifest_sha256=manifest_sha),args.out/'best.pt')
        row=dict(epoch=epoch+1,train_loss=loss_sum/total,val=scores,seconds=time.time()-tick,elapsed_seconds=time.time()-began,gpu_peak_bytes=torch.cuda.max_memory_allocated(),rss_bytes=psutil.Process().memory_info().rss)
        with (args.out/'history.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    (args.out/'run_status.json').write_text(json.dumps(dict(status='budget_checkpointed' if interrupted else 'completed',elapsed_seconds=time.time()-began,best_val=best,last_epoch=last_epoch),indent=2))


@torch.inference_mode()
def predict(args):
    if args.arch=='baseline' and args.size!=224: raise ValueError('Shipped baseline contract requires 224px input')
    manifest_sha=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    lock=json.loads((args.manifest.parent/'split_lock.json').read_text())
    if lock['manifest_sha256']!=manifest_sha: raise ValueError('evaluation split lock mismatch')
    if args.split.find('test')>=0 and not args.final:
        raise ValueError('Test is locked: select on validation first and pass --final with selection record')
    if args.reference:
        protocol=json.loads(Path('artifacts/multidomain/protocol.json').read_text())
        if hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()!=protocol['baselineCheckpointSHA256']:
            raise ValueError('Reference evaluation must use the predeclared previous release')
    if args.final:
        selection=json.loads(Path('artifacts/multidomain/selection.json').read_text())
        if selection['manifest_sha256']!=manifest_sha: raise ValueError('selection manifest mismatch')
        if args.arch!='baseline' and not args.reference:
            if selection['checkpoint_sha256']!=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest() or selection['size']!=args.size or selection['arch']!=args.arch:
                raise ValueError('final checkpoint does not match frozen selection')
    source_rows=rows_from(args.manifest,args.split)
    # Alias records may reference exactly the same source bytes. Keep the frozen
    # grouped manifest intact, but count each image once in evaluation.
    unique={}
    for row in source_rows:
        previous=unique.get(row['sha256'])
        if previous is not None:
            if any(previous[key]!=row[key] for key in ['target_id','group','split']):
                raise ValueError('Conflicting duplicate in evaluation manifest')
        else:
            unique[row['sha256']]=row
    rows=list(unique.values())
    model=make_model('baseline') if args.arch=='baseline' else load_checkpoint(args.checkpoint,allow_metadata_update=args.reference)[0]
    if args.checkpoint and args.arch!='baseline':
        state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
        if state['config']['size']!=args.size: raise ValueError('checkpoint resolution mismatch')
        if state['config']['arch']!=args.arch: raise ValueError('checkpoint architecture mismatch')
        if state['manifest_sha256']!=manifest_sha and not args.reference: raise ValueError('checkpoint evaluation manifest mismatch')
    model=model.eval().cuda(); labels=json.loads(LABELS.read_text(encoding='utf-8')); args.out.parent.mkdir(parents=True,exist_ok=True)
    began=time.time()
    with args.out.open('w',encoding='utf-8') as f:
        for x,_,ix in loader(rows,args):
            out=model(x.cuda()).float().cpu().tolist()
            for i,logits in zip(ix.tolist(),out):
                r=rows[i]
                output={k:r[k] for k in ['sha256','group','target_id','source','domain','split']}
                output.update({k:r[k] for k in ['form','shiny','generation','national_dex_id','baseline_exposure'] if k in r})
                output.update(logits=logits,label_ids=[l['id'] for l in labels]); f.write(json.dumps(output)+'\n')
    metadata=dict(rows=len(rows),duplicateAliasRowsOmitted=len(source_rows)-len(rows),seconds=time.time()-began,arch=args.arch,checkpoint=str(args.checkpoint),checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest() if args.checkpoint else None,predictions_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),labels_sha256=hashlib.sha256(LABELS.read_bytes()).hexdigest(),reference=args.reference,size=args.size,manifest_sha256=manifest_sha,preprocess='PIL EXIF decoded in ingest, white alpha, center square, RGB bilinear resize; approximation of app CoreGraphics pending Apple pixel parity')
    args.out.with_suffix('.metadata.json').write_text(json.dumps(metadata,indent=2)); print(json.dumps(metadata),flush=True)


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['train','predict'])
    p.add_argument('--arch',choices=['baseline','mobilenet_v3_large','efficientnet_b0'],default='efficientnet_b0')
    p.add_argument('--manifest',type=Path,default=Path('artifacts/multidomain/data/manifest.jsonl'))
    p.add_argument('--checkpoint',type=Path); p.add_argument('--init-checkpoint',type=Path); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--size',type=int,default=224); p.add_argument('--epochs',type=int,default=8)
    p.add_argument('--class-balance',type=float,default=.5); p.add_argument('--domain-balance',type=float,default=0.)
    p.add_argument('--group-balance',type=float,default=0.)
    p.add_argument('--reference',action='store_true',help='Evaluate only the hash-locked previous release for comparison')
    p.add_argument('--batch',type=int,default=64); p.add_argument('--workers',type=int,default=4)
    p.add_argument('--seed',type=int,default=20261027); p.add_argument('--lr',type=float,default=.0003)
    p.add_argument('--transfer',action='store_true',help='Explicit same-label transfer to a newly frozen grouped manifest'); p.add_argument('--max-minutes',type=float,default=35); p.add_argument('--resume',action='store_true')
    p.add_argument('--split',default='val'); p.add_argument('--final',action='store_true')
    a=p.parse_args(); assert torch.cuda.is_available(),'CUDA GPU required'
    torch.set_num_threads(6); seed_everything(a.seed)
    # No torch.compile or downloads; GPU benchmark determinism depends on platform.
    torch.backends.cudnn.benchmark=False
    if a.action=='train': run_train(a)
    else: predict(a)


if __name__=='__main__': main()

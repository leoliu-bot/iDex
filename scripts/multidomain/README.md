# Expanded-source recognition campaign (1.3)

The app uses installed iOS speech voices; no third-party TTS engine or neural
voice pack is shipped. This directory concerns image recognition only.

The 1,498-column EfficientNet-B0 head is retained. A 24-epoch robustness warmup
completed on the previous training split, with perspective, lighting, blur and
occlusion augmentation. The expanded campaign transfers those weights to a newly
frozen grouped manifest, then runs up to 60 epochs plus a 24-epoch lower-rate
continuation. Checkpoints are selected on validation, never final test results.

## Source controls

- Extra pinned Keremberke corpus: 4,321 species-labelled images across 93
  unambiguous species. Ambiguous species-only labels are excluded. A stratified
  186-image sample was visually checked; known anime, game, card and toy examples
  are tagged conservatively. Anime episode provenance is incomplete.
- Pinned game animations: 11,216 sampled frames from 2,807 assets. Frames from one
  asset always share a group; they are not independent images for splitting.
- Named TCG art: 14,245 records. 143 ambiguous Pikachu/Deoxys/Rotom/Giratina/
  Shaymin/Zygarde candidates received additional visual review: 140 accepted with
  explicit form assignments, three ambiguous compositions excluded. Each accepted
  card also supplies a full-card view with name and attack text blurred. Crop and
  full-card views always share one source group.
- Actual San-ei manufacturer plush photos: 1,298 views / 291 products / 269 entries.
  The product JAN groups its different views. These are studio product pictures,
  not a substitute for user-phone camera evaluation.
- The previous positive and 64/64 natural-negative split boundaries are preserved
  for surviving rows. Conflicting labels or newly linked old split groups are
  quarantined, never silently reassigned across the old boundary.

Manifest SHA-256:
`b5542585d0c29bd6858384de80584d6b16a809f03bf1b3a4c45f28128f771abe`.
72,058 rows / 71,859 usable, 21 quarantined groups. Before exact-image deduplication:
51,404 training; 9,799 validation; 6,502 fresh source-group test views; reused
public tests 3,232 + 794; natural-negative validation/test 64 each. No usable group,
file hash, pixel hash, or explicit source group crosses split boundaries. Automated
screening may miss related artwork or capture sessions; public diagnostics do not
establish independent physical-camera accuracy.

Small Pumpkaboo (110126) lost its only independent test group to quarantine.
It remains a trained class but cannot auto-confirm. Together with existing
ambiguous/sparse exclusions, 1,491 classes are eligible for score-gated discovery.

## Training and selection

Use CUDA and the pinned source caches under ignored `artifacts/`. Keep the frozen
manifest and label order unchanged. Sampler weights balance class count, domain
count within the class, and source-group size. A clean path is retained alongside
camera-like augmentation; full-card crops retain enough of the illustration.

```sh
python scripts/multidomain/prepare.py
python scripts/multidomain/train.py train --init-checkpoint artifacts/multidomain/runs/robust-warmup/best.pt --transfer --epochs 60 --lr .00012 --seed 20261121 --class-balance .65 --domain-balance .15 --group-balance .25 --max-minutes 180 --out artifacts/multidomain/runs/expanded
python scripts/multidomain/train.py train --init-checkpoint artifacts/multidomain/runs/expanded/best.pt --epochs 24 --lr .000035 --seed 20261122 --class-balance .65 --domain-balance .15 --group-balance .25 --max-minutes 70 --out artifacts/multidomain/runs/expanded-continued
python scripts/multidomain/select_model.py choose --checkpoint artifacts/multidomain/runs/expanded/best.pt --checkpoint artifacts/multidomain/runs/expanded-continued/best.pt
python scripts/multidomain/train.py predict --checkpoint artifacts/multidomain/selected.pt --split val,ood_val --out artifacts/multidomain/predictions/selected-val.jsonl
python scripts/multidomain/select_model.py calibrate --predictions artifacts/multidomain/predictions/selected-val.jsonl
python scripts/multidomain/train.py predict --checkpoint artifacts/multidomain/selected.pt --split test_public,test_forms,test_multidomain,ood_test_public --final --out artifacts/multidomain/predictions/selected-test.jsonl
```

The composite validation score is half class-macro recall, half an equal mean of
per-domain source-group accuracy. A domain needs 30 validation images and five
groups to enter that mean; the single tagged anime validation frame cannot support
an anime-specific improvement claim. Acceptance calibration retains the declared
97% accepted-accuracy / 5% natural-negative FAR validation gate, then maximizes
known coverage. Tensor, manifest, labels and prediction-file hashes are checked.
The complete metric report is computed before the policy freeze marker is written.

The previous release is a hash-locked reference, with its own eligibility flags
and thresholds. It may be evaluated on the new validation split; final test
comparison is allowed only after the new candidate and policy are frozen. Reused
old public tests and fresh source-group tests must be reported separately.

Only selected weights, aggregate reports and source/hash receipts enter Git.
Raw images, model-generation caches and prediction logits remain local. Respect
[model/data notices](../../iDex/Recognition/MODEL_NOTICE.md); publisher repository
licenses do not relicense Pokémon characters, card illustrations or product photos.

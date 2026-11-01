# Form-aware Pokédex training

This campaign replaces the species-only head with 1,498 visible-appearance classes
for a 1,579-record archive (1,025 species plus 554 additional forms). It starts
from the verified TorchVision ImageNet EfficientNet-B0 weights, not the previous
species checkpoint. Regional forms, fusions, Mega and Gigantamax forms are included.
The native app remains offline; source photographs never enter the repository.

## Frozen data and limits

- PokéAPI data revision: `6b8db7f3cb31cfaa37cb74e5c3edff124bcba5ce`.
- PokéAPI sprites revision: `1dd55c0436d2a5b6e324c0b780e1b1b416fbfb64`.
- Historical Pokémon TCG metadata revision:
  `39a26a144c8b6ef6c2fb17b2c29d0bb7121e3a11`.
  Only explicitly named, unambiguous forms are mapped. Up to eight card-art crops
  supplement each form. Crops reduce borders/text but some full-art cards retain
  text; these are public-art diagnostics, not a clean camera benchmark.
- Retained unambiguous JJMack species groups keep their previous train/validation/
  test boundaries. 4,473 species-only images from species with multiple visual
  forms are excluded, rather than guessed to be the ordinary form.
- Exact decoded pixels and source poses are grouped before the seeded split;
  mirrored/near-duplicate poses are grouped within a label. Conflicts are quarantined.
- Frozen manifest SHA-256:
  `575fa0c69fad2283aaa6abcde2e4fe826a3fb85fecf0511bfe07897e0891a671`.
  Train 19,525; validation 3,637; reused public test 2,705; new form test 744;
  natural-negative validation/test 64 each. No source group crosses split boundaries.
- Identical visible appearances share a class and retain manual form choices.
  Finizen/zero-form Palafin and Flapple/Appletun Gigantamax cannot automatically
  establish the underlying species from their shared appearance. Sparse classes
  lacking independent train/validation/test groups cannot auto-confirm either.
  There are 1,492 data-eligible classes; this does not guarantee reliable recognition
  of every camera image. Shiny identification is not trained as separate classes.

## Reproduce

Use an isolated CUDA environment. The existing pinned species manifest and cached
source corpus from `scripts/national` are inputs to the form audit. Keep them under
the ignored artifact directories. Do not rerun preparation over a frozen campaign.

```sh
python scripts/catalog/build_forms_catalog.py
python scripts/audio/build_forms_cries.py
python scripts/forms/acquire.py
python scripts/forms/acquire_cards.py
python scripts/forms/prepare.py
python scripts/catalog/verify_forms_catalog.py
python scripts/forms/train.py train --epochs 8 --seed 20261101 --out artifacts/forms/runs/form-aware
python scripts/forms/train.py train --init-checkpoint artifacts/forms/runs/form-aware/best.pt --epochs 12 --lr .0001 --seed 20261113 --max-minutes 25 --out artifacts/forms/runs/form-aware-continued
python scripts/forms/select_model.py choose --checkpoint artifacts/forms/runs/form-aware/best.pt --checkpoint artifacts/forms/runs/form-aware-continued/best.pt
python scripts/forms/train.py predict --checkpoint artifacts/forms/selected.pt --split val,ood_val --out artifacts/forms/predictions/selected-val.jsonl
python scripts/forms/select_model.py calibrate --predictions artifacts/forms/predictions/selected-val.jsonl
python scripts/forms/train.py predict --checkpoint artifacts/forms/selected.pt --split test_public,test_forms,ood_test_public --final --out artifacts/forms/predictions/selected-test.jsonl
```

Checkpoint choice uses positive validation accuracy. Acceptance requires validation
accepted accuracy ≥97% and natural-negative false acceptance ≤5%, then maximizes
known acceptance. Checkpoint, ordered labels and policy are hash-bound before test
access. No threshold tuning uses final test predictions. The discarded preliminary
8-epoch audit draft is not a candidate or a continuation initialization.

Only the selected tensor checkpoint, labels, contract and aggregate reports go in
`TrainingResources`. The Mac release workflow exports FP32, checks source/Core ML
numerical agreement on CPU-only and all-compute policies, runs iOS tests and builds
`Pokedex-Forms-unsigned.ipa`. Physical camera accuracy, voice audition, hinge behavior
and device performance remain separate device checks.

Keep [model/data notices](../../iDex/Recognition/MODEL_NOTICE.md). Pokémon artwork
rights remain separate from source-code licenses. Raw card/source images are not
redistributed with the model or application.

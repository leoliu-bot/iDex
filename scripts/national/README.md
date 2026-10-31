# National Pokédex training and release

This extension follows the upstream development guide, training/export contract,
grouped-source split procedure, bounded 8 + 12 epoch campaign, and Apple numerical
validation gate. It does not reuse the old 151-class tensor checkpoint.

## Scope

- Offline archive: National Dex 1–1025; all original 151 records and PNGs retained.
- Training source: `JJMack/pokemon-classification-gen1-9`, revision
  `959ff557b102fc3b4f912d0ca769273be5b9ca7f`; all three Parquet SHA-256 values
  are verified against the upstream campaign's pinned receipts.
- Public natural-object diagnostic: COCO128, 128 source images, divided into
  64 validation and 64 untouched test groups. This small slice does not certify
  rejection on arbitrary camera scenes.
- Exact/decoded-image, source-pose, foreground, mirror and perceptual grouping
  precede the seeded split. Conflicting labels remain quarantined.
- Current supported head: 1018 ordered National Dex IDs. IDs 955, 960, 963, 964,
  1011, 1019 and 1023 lack three nonconflicting independent groups after the
  audit; they remain fully available in the archive. The head has no synthetic
  empty classes and does not claim to distinguish visually identical forms.
- Architecture/input: TorchVision EfficientNet-B0, ImageNet initialization,
  fixed 224×224 RGB, ImageNet normalization embedded exactly once. FP32 export.

## Reproduce

Use a fresh isolated CUDA environment and a new `artifacts/national` root.
The data ingestion expects the three pinned Parquet files under
`sources/JJMack--pokemon-classification-gen1-9` and COCO128 under `sources/coco128`.
`artifacts/national/labels.json` contains the desired 1025 catalog species;
the audit writes the actual `training-labels.json` head separately.

```sh
python scripts/national/data.py --root artifacts/national
python scripts/national/refine_groups.py
python scripts/national/audit.py
python scripts/national/train.py train --epochs 8 --max-minutes 35 --out artifacts/national/runs/efficientnet224
python scripts/national/train.py train --init-checkpoint artifacts/national/runs/efficientnet224/best.pt --epochs 12 --lr .0001 --seed 20261035 --max-minutes 25 --out artifacts/national/runs/efficientnet224-continued
python scripts/national/select_model.py choose --checkpoint artifacts/national/runs/efficientnet224/best.pt --checkpoint artifacts/national/runs/efficientnet224-continued/best.pt
python scripts/national/train.py predict --checkpoint artifacts/national/selected.pt --split val,ood_val --out artifacts/national/predictions/selected-val.jsonl
python scripts/national/select_model.py calibrate --predictions artifacts/national/predictions/selected-val.jsonl
python scripts/national/train.py predict --checkpoint artifacts/national/selected.pt --split test_public,ood_test_public --final --out artifacts/national/predictions/selected-test.jsonl
```

The selected checkpoint and acceptance policy are hash-bound before final test
access. Metrics accept gapped IDs and check logit-column order. Keep complete
data, code snapshots, manifests, checkpoints and prediction files under the
ignored artifact root. Only the selected tensor checkpoint, ordered labels,
policy and aggregate reports belong in `TrainingResources`.

## Export and build

Run **Build Pokédex National IPA** on the `national-pokedex` branch. The workflow
uses Xcode 27.1 and Python 3.11 on Apple's platform, exports the checkpoint,
checks source/Core ML FP32 logits for CPU-only and all-compute policies, and then
runs affected iOS catalog, model, cry, layout and UI tests. Only a passing model
is selected and bundled. The generated model is committed to the development
branch after tests and a successful iPhone build. `Pokedex-IPA` is the unsigned
installation artifact; signing uses the same Windows procedure as before.

Physical iPhone camera accuracy, actual hinge behavior and physical performance
still require device evaluation following the upstream camera protocol. Public
validation/test accuracy and Mac conversion parity are reported separately.

## Rights

Dataset card: https://huggingface.co/datasets/JJMack/pokemon-classification-gen1-9
The publisher declares CC BY-NC-SA 4.0 and attributes images to Bulbapedia.
Keep attribution and noncommercial/share-alike terms with the selected weights;
underlying Pokémon artwork is not relicensed by this repository's MIT license.
Raw source images are not part of the upload. TorchVision retains its BSD notice.

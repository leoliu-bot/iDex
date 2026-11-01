# Pokédex form-aware image classifier

The app bundles `NationalClassifier.mlpackage`, a locally trained EfficientNet-B0
FP32 model with 1,498 appearance classes for 1,025 species and 554 additional forms.
1,492 classes have independent train/validation/test groups and may auto-confirm
when the validation-frozen score/margin policy also passes. Shared appearances
retain manual choices; sparse or ambiguous records do not auto-confirm.

The selected tensor checkpoint, ordered labels and policy are hash-bound by
[recognition-manifest.json](recognition-manifest.json). The form campaign starts
from ImageNet, not the previous species checkpoint. See [form training](../../scripts/forms/README.md),
[aggregate training report](../../TrainingResources/training-summary.json) and
[Apple validation](../../TrainingResources/apple-validation.json).

Release 1.2 passed 58 FP32 source/Core ML checks (CPU-only and all-compute),
52 simulator tests / 94 runs, and the iPhone Release build. Maximum absolute
logit error was 0.000246287. These checks do not measure physical-camera accuracy,
voice audition, hinge behavior or physical-device performance.

Mixed public-image Top-1 is 92.02%; strict alternate-form Top-1 is 73.10% (91.09%
accuracy among accepted form inputs, 487 inputs). Regional/fusion Top-1 is 81.54%
(65 inputs). The broader new-reference split includes ordinary appearances;
reused species holdouts are also reported separately.
Natural-negative test false accepts: 4/64. These are public-art diagnostics, not
physical-camera accuracy. Shiny identification is not separately trained.
The app's regional/fusion opaque sprite fixtures and original Farfetch'd fixture
are checked separately as known-input integration checks, not a generalization test.

## Historical Kanto reference

The following records the upstream 151-class artifact and its physical timings.
`KantoClassifier.mlpackage` is retained in Git history, rather than bundled with
the National edition. These measurements do not describe the National model.

### iDex trained image classifier

iDex bundles a locally trained **EfficientNet-B0 FP32 Core ML model** for the **151 Kanto species**. The complete package is tracked in Git at `KantoClassifier.mlpackage`; a normal clone or GitHub source ZIP includes it. The app performs inference offline and does not download weights or upload photos at runtime.

## Artifact and contract

- Version: `local-efficientnet-b0-fp32-b24cf5301ad9`.
- Training checkpoint SHA-256: `b24cf5301ad97bd1f1f721bffa3c40ec0242bf1efac68435a3752850f624fa6f`.
- Packaged weights SHA-256: `732f3b550cb44c7927d0914086df7b1237371a7d9a902942fd03ab5274d92756`.
- Model spec SHA-256: `c084e36a3006f6a2e33d50b0c95dff33c9a828ad0458be610006c72a554a37f2`.
- Package: 16,854,510 bytes across three files. Largest file: 16,730,496 bytes. Regular Git storage is used, with binary attributes and no LFS filter.
- Implementation/initialization: TorchVision EfficientNet-B0, initialized from its ImageNet-1K weights and fine-tuned locally. This is trained for iDex, not a claim that the architecture or every input asset originated here. See [model and dataset notices](MODEL_NOTICE.md).
- Input: `image`, fixed 224×224 RGB. ImageType scales by `1/255`; channelwise ImageNet normalization is embedded exactly once (mean `.485,.456,.406`, std `.229,.224,.225`).
- Output: `logits`, FP32 `[1,151]` raw finite scores, in exact `pokemon_labels.json` order. No temperature or softmax is embedded.
- Label-file SHA-256: `13bd2345fa10f8a7d04363772bb6ef7871c0a6c0635d8c907a77e6cb93f78725`; IDs1…151, unchanged ordering.

The machine-readable record is [model-manifest.json](../../scripts/replacement/model-manifest.json). Verify a downloaded model from the repository root:

```sh
shasum -a 256 iDex/Recognition/KantoClassifier.mlpackage/Data/com.apple.CoreML/weights/weight.bin
```

## Runtime behavior

Photo import corrects orientation, composites alpha onto white, bounds thumbnail area to approximately4.2 megapixels, and produces a centered square no larger than1200px. The classifier creates a BGRA-backed image feature with RGB model semantics and `scaleFill` at224px. Camera processing rotates the retained frame and takes a centered square. Normalization is not repeated in Swift.

`PokemonClassifier` serializes loading and inference in an actor. Physical devices use `.all`; Simulator uses `.cpuOnly`. The app computes ordinary softmax at temperature1, offers the top three results, and accepts an automatic discovery/narration only when the first score is at least.25 and the first/second raw-logit margin is at least.5. Other results remain best guesses. These heuristics are not a trained unknown detector or calibrated probability. There is no background class; unrelated objects and non-Kanto species can still be accepted.

## Validation and limits

The FP32 artifact passed171 source-logit fixtures under all four compute-unit policies on both an M1 Max Mac and physical `iPhone19,4` running iOS27.1. Physical checks used unchanged top1 and `abs(error) <= .001 + .0001*abs(reference)`. Apple-prepared RGB bytes matched the canonical inputs. The fixtures are validation artwork/unlabelled natural-image cases, not an independent camera-accuracy test.

The stricter public diagnostic reported96.20% top1, but data exposure/duplicate grouping limits remain and broader public results were approximately tied. The151 labelled numerical fixtures gave146 correct; that small selected set is not a generalization estimate. Real-camera superiority, calibrated unknown rejection, actual operator/backend placement and energy consumption have not been established.

On the physical phone, the selected `.all` route measured warm encoded-bytes-to-result p50/p95 **9.91/11.87ms** and30-second sustained p50/p95 **15.56/17.21ms**. This includes preparation, prediction/logit reading and softmax, and excludes sensor capture, UI, file I/O and loading. The pilot had fixed order and different warm/sustained fixture cycles; it is not a blanket speedup claim. See [performance](../../docs/performance.md).

## Build and reproduce

Xcode27.1 and the existing iDex scheme compile the model automatically. No API key, server, model-hosting service, or separate weight download is required. The model-format minimum iOS18 is compatible with the app's iOS27+ floor; no additional older-phone support is implied.

Training/acquisition, tensor-only checkpoint loading, export and numerical validation tools are in [scripts/replacement](../../scripts/replacement/README.md). Training uses grouped public-data splits, a bounded experiment budget and a fixed151-label head. The trained tensor checkpoint, raw training images, private device reports and local rollback copies are not distributed in this Git commit. Re-exporting requires a matching locally retained or newly trained checkpoint; a clone already contains everything needed to build/run inference.

```sh
python scripts/replacement/export.py --checkpoint /path/to/your/checkpoint.pt \
  --out artifacts/replacement/export --deployment iOS18
xcrun coremlc compile iDex/Recognition/KantoClassifier.mlpackage /tmp/idex-model-compiled
```

Export writes fresh FP32 and FP16 diagnostic packages and never overwrites the app package. Only the verified FP32 package is selected for the app. FP16/mixed diagnostics had policy-dependent numerical failures and are not shipped as alternatives.

Local rollback snapshots and historical audit evidence remain in ignored `artifacts/model-rollback/` and Git history. They are not app resources or uploaded training artifacts. Installing a rebuilt app on a phone is separate from obtaining the source/model; preserve existing app data when deploying.

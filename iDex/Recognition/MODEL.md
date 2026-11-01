# Pokédex 1.3 form-aware image classifier

The app bundles `NationalClassifier.mlpackage`, a locally trained EfficientNet-B0
FP32 model with 1,498 appearance classes for 1,025 species and 554 additional forms.
**1,491 classes** are eligible for automatic discovery when the validation-frozen
score/margin policy also passes. Small Pumpkaboo (entry 110126) remains trained
and available as a candidate, but its only independent test group was quarantined,
so it cannot auto-confirm. Shared appearances retain manual choices; sparse or
ambiguous records do not auto-confirm. Shiny colors are not separately trained.

The selected tensor checkpoint, ordered labels and policy are hash-bound by
[recognition-manifest.json](recognition-manifest.json). The 1.3 checkpoint SHA-256 is
`9c7691e009db118c1d9a2ae01a975a66ce78e0f01c23e51799f900740180d0d0`.
The expanded manifest SHA-256 is
`b5542585d0c29bd6858384de80584d6b16a809f03bf1b3a4c45f28128f771abe`.
The ordered 1,498-column head is retained. Input is 224×224 RGB with ImageNet
normalization embedded once; the FP32 output contains raw logits. Swift applies
softmax and the frozen acceptance gates; it does not repeat normalization.

The original form campaign started from ImageNet. The 1.3 campaign continued that
model through **24 + 60 + 24 = 108 completed epochs** on a local RTX 4080 SUPER:
robustness warmup on the previous training split, expanded-source training,
and lower-rate continuation. Extra data covers game animation frames, card
illustrations and masked full-card views, mixed public images, and manufacturer
plush photos. Animation frames and different views of the same card or product
stay in one source group. Duplicate screening and quarantine protect split
boundaries; public-source grouping can still miss related artwork or sessions.
The recorded epoch work totals 7,692.101 seconds (approximately 128.2 minutes),
excluding acquisition, final evaluation and cloud builds.

Checkpoint selection uses validation class-macro recall and per-domain
source-group accuracy. The acceptance policy is also chosen on validation only;
the checkpoint and policy are frozen before final test predictions. Fresh
source-group tests and reused prior public holdouts are reported separately.
The 1.3 acceptance gates are a top softmax score of at least 0.35 and a first/second
raw-logit margin of at least 0.5, together with class eligibility. They do not
provide a calibrated probability or a trained unknown-object detector.

On the **same fresh 6,448 images / 3,031 source groups**, the frozen 1.2 baseline
has 33.28% per-image Top-1 versus **88.20% for 1.3**. New-model Top-3 is 94.43%,
with **96.99% accepted-known accuracy at 78.32% coverage**. These inputs include
ordinary species and additional forms. The large gain applies to this expanded
public-source distribution; it is not a measured gain on physical-phone photos.
[Fresh test metrics](../../TrainingResources/test-multidomain.json) ·
[Paired same-input comparison](../../TrainingResources/paired-fresh-groups.json)

The following domain rows are subsets of that fresh holdout, measured with 1.3.
Card crops and masked full-card views can share a source group; row counts must
not be added as independent groups.

| Fresh source subset | Images / groups | Top-1 | Accepted-known accuracy | Coverage |
| --- | ---: | ---: | ---: | ---: |
| TCG illustration crops | 2,085 / 2,021 | 87.15% | 98.16% | 73.05% |
| Masked full-card views | 2,087 / 2,021 | 83.71% | 97.18% | 69.62% |
| Manufacturer plush product photos | 226 / 50 | 89.82% | 96.27% | 71.24% |
| Game animation frames | 1,424 / 350 | 91.78% | 94.64% | 91.71% |

The [strict fresh **non-base-form** subset](../../TrainingResources/test-alternate-forms-fresh.json)
contains 776 images / 208 groups:
Top-1 is **82.09%**, with **89.95% accepted accuracy at 80.80% coverage**. Form
confusion therefore remains even among automatically accepted results. The
separate [reused non-base-form subset](../../TrainingResources/test-alternate-forms-reused.json)
has 535 images / 468 groups: Top-1 is
86.54%, with 96.90% accepted accuracy at 72.34% coverage. These subsets must
not be conflated with the broader mixed-species holdouts.

[Reused public and form-reference tests](../../TrainingResources/paired-reused-public.json)
contain **4,009 known images**: Top-1 is
92.14% for the frozen 1.2 model and 96.43% for 1.3 on that same set. Those counts
differ from the historical release's original test report. The separate 64 reused
natural negatives produce **4 false accepts in both models** (6.25%). A validation
false-accept gate does not guarantee the same bound on final or real-world inputs.

There is only one explicitly tagged anime validation image and the fresh anime
test has **3 images / 3 groups**, insufficient for an anime-specific accuracy claim.
Public artwork and studio product photos do not establish physical-camera
accuracy. Known regional/fusion sprite fixtures and the original Farfetch'd
fixture are integration checks, not generalization tests.

See [expanded-source training](../../scripts/multidomain/README.md),
[training runtime](../../TrainingResources/training-runtime.json),
[aggregate training report](../../TrainingResources/training-summary.json) and
[1.3 update and limits](../../docs/multidomain-update.zh-CN.md).
[Historical 1.2 diagnostics](../../docs/forms-expansion.zh-CN.md) are retained as
previous-release evidence rather than 1.3 results.

GitHub Actions **Build Pokédex 1.3 IPA** exports the selected FP32 model, requires
source/Core ML parity, runs iOS tests and verifies the final package. Its
`Pokedex-IPA` artifact contains `Pokedex-1.3-unsigned.ipa`. Numerical comparison,
simulator and Release-build status are recorded separately in
[Apple validation](../../TrainingResources/apple-validation.json). They do not
measure physical-camera accuracy, phone voice audition, hinge behavior or
physical-device performance.

The app retains the original pixel shell and sprites, and the fixed notes/stats
panel. It adds persistent per-language selection from installed iOS voices, using
natural pitch and default rate for explicit choices. Automatic male/female
options remain; Chinese automatic selection prefers Taiwan Mandarin. The top
blue light gently follows speech progress, with steady brightness under Reduce
Motion. No third-party voice pack or cloud TTS is used. Revised English, Chinese
and Japanese field notes cover all 58 regional and 6 fusion records, with exact
official-form URLs and hashes in the
[editorial source receipt](../../scripts/catalog/form-description-overrides.json).

Release 1.3 passed 58 FP32 numerical checks, 59 simulator tests / 101 runs, the iPhone Release build and final IPA resource verification, with zero failures, skips or runtime warnings. [Cloud run](https://github.com/leoliu-bot/iDex/actions/runs/41313885202); [evidence](../../TrainingResources/apple-validation.json). Physical-camera accuracy remains unmeasured.

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

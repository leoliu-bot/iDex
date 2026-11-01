[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

A native, offline, pixel-style Pokédex for iPhone Duo. Version **1.3** expands
recognition training and adds a picker for installed iOS narration voices.

- **1,025 species, generations 1–9**: English, Simplified Chinese and Japanese
  names, field notes, types, dimensions, base stats, 96×96 pixel sprites and cries.
- Original red device shell, LCD palette, pixel fonts, scan animation and
  cover/expanded layouts retained. Original 151 records and sprites preserved.
- **554 additional forms**, including regional forms, fusions, Mega and Gigantamax;
  1,579 archive records and a retrained **1,498-class appearance model**.
  **1,491 classes** are eligible for score-gated discovery. Identical appearances
  share candidates; sparse forms require manual confirmation. Small Pumpkaboo
  remains a candidate because it has no independent test group.
- Fixed-size notes/stats display, plus revised field notes for **58 regional and
  6 fusion forms in all three languages**, with official form-specific sources.
- Choose from iOS voices already installed on the phone, with name, locale,
  quality and preview. Choices persist per language; explicit choices use the
  voice's natural pitch and default rate. Automatic male/female options remain,
  with Taiwan Mandarin preferred for Chinese. Existing Pokémon names stay.
- The top blue light pulses gently with narration progress and returns to rest
  afterward; Reduce Motion uses steady brightness.
- Camera and imported photos stay on the iPhone. Low-confidence matches remain
  candidates and are not automatically discovered or narrated.
- Search by any supported language, exact `#1025` numbers or localized types;
  browse continuously across the National Dex. Existing discovery keys and app
  installation identifier are retained.

## Training and validation

A local RTX 4080 SUPER completed **24 + 60 + 24 = 108 epochs**: a robustness
warmup on the previous training split, expanded-source training, and a lower-rate
continuation. The expanded data includes game animation frames, card illustrations
and masked full-card views, mixed public images, and manufacturer plush photos.
Frames from one animation, views of one card and views of one toy stay in the
same source group. Duplicates and split conflicts are screened and quarantined.
Recorded epoch work totals approximately **128.2 minutes**; acquisition, final
evaluation and cloud builds are separate.

The checkpoint and acceptance policy were frozen using validation only. On the
same **6,448 fresh source-group test images / 3,031 groups**, per-image Top-1 was
**33.28% for the frozen 1.2 baseline → 88.20% for 1.3**. New-model Top-3 was
**94.43%**; accepted-known accuracy was **96.99%** at **78.32%** acceptance coverage.
[Fresh test](TrainingResources/test-multidomain.json) ·
[Same-input comparison](TrainingResources/paired-fresh-groups.json)

Forms remain harder: the [fresh non-base-form subset](TrainingResources/test-alternate-forms-fresh.json)
(776 images / 208 groups)
had **82.09% Top-1** and **89.95% accepted accuracy**. Both versions falsely
accepted **4 of 64** reused natural negatives. Fresh and reused diagnostics are
kept separate in the [training report](TrainingResources/training-summary.json).
These public-source images and studio product photos do not establish
physical-camera accuracy. The explicitly tagged anime test has only **3 images /
3 groups**, insufficient for an anime-specific accuracy claim; shiny colors are
not separately trained. Numerical Core ML checks, iOS tests and the Release
build have their own [Apple validation record](TrainingResources/apple-validation.json).

[1.3 update and limits](docs/multidomain-update.zh-CN.md) ·
[Training runtime](TrainingResources/training-runtime.json) ·
[Expanded-source training](scripts/multidomain/README.md) ·
[Historical 1.2 diagnostics](docs/forms-expansion.zh-CN.md)

## Build

Use **Build Pokédex 1.3 IPA** in GitHub Actions on `national-pokedex`.
It exports the selected tensor checkpoint on Mac, requires FP32 numerical parity,
runs iOS tests, and checks the packaged app. Download the `Pokedex-IPA` artifact
and extract `Pokedex-1.3-unsigned.ipa`, then use the established Windows signing
and installation workflow. The app needs no server, API key or runtime downloads;
additional system voices can be downloaded in iPhone Settings before use.
After the generated Core ML model is committed, Xcode 27.1 can also build
`iDex.xcodeproj` with the `iDex` scheme (iOS 27+, hinge APIs on iOS 27.1+).

## Credits and licenses

Original application: **Zihang Huang / iDex**, [MIT](LICENSE).
Pokémon, Nintendo, Creatures, GAME FREAK and The Pokémon Company retain their
content and trademark rights; this remains an unofficial fan project.
Original pixel art: Pokémon Database. National Gen 5 art: PokéAPI / credited
Smogon contributors. Data: PokéAPI plus official localized Pokédex pages.
Cries: PokéAPI/cries. Fonts: Press Start 2P and Fusion Pixel, SIL OFL 1.1.
TorchVision: retained BSD notice. Model/data contributions retain their separate
noncommercial/share-alike terms.

[Asset attribution](iDex/Catalog/ATTRIBUTION.md) ·
[Model/data notice](iDex/Recognition/MODEL_NOTICE.md) · [License scope](NOTICE.md) ·
[Expanded-source training and validation](scripts/multidomain/README.md)

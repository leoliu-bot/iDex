[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

A native, offline, pixel-style Pokédex for iPhone Duo.

- **1,025 species, generations 1–9**: English, Simplified Chinese and Japanese
  names, field notes, types, dimensions, base stats, 96×96 pixel sprites and cries.
- Original red device shell, LCD palette, pixel fonts, scan animation and
  cover/expanded layouts retained. Original 151 records and sprites preserved.
- **A newly trained 1,018-class EfficientNet-B0**, with an ordered National Dex
  label map. Seven species with insufficient independent training groups remain
  archive-only; Settings lists them in the selected language.
- Camera and imported photos stay on the iPhone. Low-confidence matches remain
  candidates and are not automatically discovered or narrated.
- Search by any supported language, exact `#1025` numbers or localized types;
  browse continuously across the National Dex. Existing discovery keys and app
  installation identifier are retained.

## Measured public diagnostic

The selected checkpoint was trained for 8 + 12 epochs on a local RTX 4080 SUPER.
Untouched grouped public test: **92.53% Top-1**, **96.98% Top-3**, and **97.81%
accuracy among accepted known inputs**, with **86.85% known acceptance coverage**.
The small 64-image natural-negative test had 3 false accepts. These are public
artwork diagnostics, **not physical-camera accuracy**. Mac conversion and iOS
validation are separate release gates. The Mac release passed 38 numerical checks
and all 35 simulator tests (55 parameterized/ordinary runs), then produced the
unsigned iPhone IPA. See [Apple validation](TrainingResources/apple-validation.json)
and `TrainingResources/training-summary.json`.

[Detailed Chinese engineering notes](docs/national-expansion.zh-CN.md)

## Build

Use **Build Pokédex National IPA** in GitHub Actions on `national-pokedex`.
It exports the selected tensor checkpoint on Mac, requires FP32 numerical parity,
runs iOS tests, and creates `Pokedex-IPA`. The app needs no server, API key or runtime
downloads. After the generated Core ML model is committed, Xcode 27.1 can also build
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
[National training and validation](scripts/national/README.md)

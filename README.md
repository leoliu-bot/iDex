[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

A native, offline, pixel-style Pokédex for iPhone Duo.

- **1,025 species, generations 1–9**: English, Simplified Chinese and Japanese
  names, field notes, types, dimensions, base stats, 96×96 pixel sprites and cries.
- Original red device shell, LCD palette, pixel fonts, scan animation and
  cover/expanded layouts retained. Original 151 records and sprites preserved.
- **554 additional forms**, including regional forms, fusions, Mega and Gigantamax;
  1,579 archive records and a newly trained **1,498-class appearance model**.
  Identical appearances share candidates; sparse forms cannot auto-confirm.
- Fixed-size notes/stats display and persistent classic male/female narration;
  Chinese narration prefers installed Taiwan Mandarin voices. Existing names stay.
- Camera and imported photos stay on the iPhone. Low-confidence matches remain
  candidates and are not automatically discovered or narrated.
- Search by any supported language, exact `#1025` numbers or localized types;
  browse continuously across the National Dex. Existing discovery keys and app
  installation identifier are retained.

## Measured public diagnostic

The selected checkpoint was trained for 8 + 12 epochs on a local RTX 4080 SUPER.
Mixed public test: **92.02% Top-1**, **96.48% Top-3**, **97.53% accepted-known
accuracy**, and **88.52% acceptance coverage**. The strict alternate-form holdout is lower:
**73.10% Top-1**, **91.09% accepted accuracy** (487 inputs). Regional/fusion Top-1
is 81.54% (65 inputs). The broader new-reference split also includes ordinary
appearances and is reported separately. Reused prior species groups are
reported separately. The 64 natural negatives had 4 false accepts. These public
artwork diagnostics are **not physical-camera accuracy**. The Mac conversion,
iOS tests and release build are separate gates recorded in
[Apple validation](TrainingResources/apple-validation.json).

[Detailed Chinese form notes](docs/forms-expansion.zh-CN.md)

## Build

Use **Build Pokédex Forms IPA** in GitHub Actions on `national-pokedex`.
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
[Form training and validation](scripts/forms/README.md)

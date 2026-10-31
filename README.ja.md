[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

iPhone Duo 用、オフラインのピクセルスタイル全国ポケモン図鑑。

- 第1～9世代の **1025種**。英語・簡体字中国語・日本語の名前、分類、図鑑説明、
  タイプ、種族値、たかさ、おもさ、96×96スプライト、鳴き声を同梱。
- 赤い本体、LCDカラー、ピクセルフォント、スキャン演出、折りたたみレイアウトを維持。
- 新たに学習した **1018クラスの EfficientNet-B0**。独立した学習グループが不足する
  7種は図鑑閲覧のみで、設定画面に対応範囲を表示。
- 識別はデバイス内で実行。確信度の低い候補は自動的に発見済みになりません。
- 名前・タイプ・全国番号で検索。`#1025` の完全一致検索、全国図鑑の連続ページ送りに対応。

公開画像をグループ分割した未使用テストでは Top-1 **92.53%**、Top-3 **96.98%**。
これは実際のカメラ精度を証明するものではありません。Macでの数値検証と iOS テストは
リリース前に別途実行します。

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

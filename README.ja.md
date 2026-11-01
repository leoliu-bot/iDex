[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

iPhone Duo 用、オフラインのピクセルスタイル全国ポケモン図鑑。
**1.3** では認識用の学習データを拡充し、端末内の iOS 音声を選択できるようになりました。

- 第1～9世代の **1025種**。英語・簡体字中国語・日本語の名前、分類、図鑑説明、
  タイプ、種族値、たかさ、おもさ、96×96スプライト、鳴き声を同梱。
- 赤い本体、LCDカラー、ピクセルフォント、スキャン演出、折りたたみレイアウトを維持。
  最初の151件のデータとスプライトも保持。
- リージョン・合体・メガ・キョダイマックスなど **554件の追加のすがた**。
  全1579件、新たに学習した **1498外見クラスの EfficientNet-B0**。
  **1491クラス**がスコア条件付き自動確定の対象です。同じ外見は候補を共有し、
  資料の少ないすがたは手動確認。ちいさいサイズのバケッチャは独立したテスト群がなく、
  候補表示のみに留めます。
- 説明／種族値を切り替えても表示枠の大きさは固定。**リージョン58件・合体6件**の
  三言語の説明を、それぞれの公式資料に基づく自然な観察記録へ更新。
- インストール済み iOS 音声の名前・地域・音質を表示し、試聴と選択が可能。
  言語ごとに選択を保存し、手動選択では音声本来の高さと標準速度を使用します。
  自動の男性声／女性声も利用でき、中国語の自動選択は台湾の声を優先します。
- 上部の青いランプが読み上げの進行に合わせて穏やかに点滅し、終了後に戻ります。
  「視差効果を減らす」が有効な場合は明るさを一定に保ちます。
- 識別はデバイス内で実行。確信度の低い候補は自動的に発見済みになりません。
- 名前・タイプ・全国番号で検索。`#1025` の完全一致検索、全国図鑑の連続ページ送りに対応。

## 学習と検証

ローカルの RTX 4080 SUPER で **24 + 60 + 24 = 108エポック**を完了。
従来の学習用分割で頑健性を高める予備学習を行い、拡充したデータで本学習、
低い学習率で追加学習を実施しました。ゲームのアニメーション、カードのイラストと
文字を隠したカード全体像、混合公開画像、メーカーのぬいぐるみ写真を追加しました。
同一アニメーション・カード・商品の各画像は同じ出典グループにまとめ、重複や
分割境界の衝突を検査して隔離します。
記録されたエポック処理時間の合計は約 **128.2分**。収集・最終評価・クラウドビルドは別です。

チェックポイントと確定条件は検証用データだけで選び、固定後に最終テストを行います。
同じ **新規出典のテスト6448画像／3031グループ**で、画像単位のTop-1は
**固定した1.2モデルの33.28% → 1.3の88.20%**。新版のTop-3は **94.43%**、
自動確定した既知画像の正解率は **96.99%**、確定率は **78.32%** でした。
[新規出典テスト](TrainingResources/test-multidomain.json) ·
[同一入力での比較](TrainingResources/paired-fresh-groups.json)

追加のすがたには混同が残ります。[新規出典の通常以外のすがた](TrainingResources/test-alternate-forms-fresh.json)
だけの776画像／208グループは
Top-1 **82.09%**、確定した結果の正解率 **89.95%**。再利用した自然物の負例64画像は、
両モデルとも **4画像**を誤確定しました。新規出典と再利用テストは
[学習レポート](TrainingResources/training-summary.json)で分けて報告します。
公開画像やメーカーの商品写真は実際のスマートフォン撮影精度を証明しません。
アニメと明示されたテストは **3画像／3グループ**のみで、一般的なアニメ認識精度は
主張できません。色違いは別学習していません。
Core ML 数値比較、iOS テスト、Release ビルドは
[Apple検証記録](TrainingResources/apple-validation.json)を参照してください。

[1.3の更新と制約（中国語）](docs/multidomain-update.zh-CN.md) ·
[学習実行記録](TrainingResources/training-runtime.json) ·
[学習手順](scripts/multidomain/README.md) ·
[1.2の過去の診断（中国語）](docs/forms-expansion.zh-CN.md)

## ビルドとインストール

`national-pokedex` の GitHub Actions で **Build Pokédex 1.3 IPA** を実行します。
Mac上で選択済みチェックポイントを変換し、FP32数値比較・iOSテスト・パッケージ検査を
通過すると `Pokedex-IPA` アーティファクトが作成されます。ダウンロードして
`Pokedex-1.3-unsigned.ipa` を取り出し、従来のWindows署名・インストール手順を利用できます。
実行時のサーバー、APIキー、追加ダウンロードは不要です。音声を増やす場合は、
事前にiPhoneの設定でシステム音声をダウンロードしてください。

生成した Core ML モデルをコミットした後は、Xcode 27.1 で `iDex.xcodeproj` の
`iDex` scheme をビルドすることもできます。iOS 27以降、ヒンジAPIはiOS 27.1以降が必要です。

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

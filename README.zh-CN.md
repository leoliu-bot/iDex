[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

为 iPhone Duo 打造的离线像素风全国宝可梦图鉴。

- **1025 种、第 1～9 世代**：中英日三语名称、分类、说明、属性、身高、体重、
  六项能力值、96×96 像素图和叫声，全部随应用离线提供。
- 保留红色设备外壳、LCD 配色、像素字体、扫描动画和折叠布局；原有 151 条图文不变。
- **新增 554 条地区、合体、Mega、超极巨化等形态**，共 1579 条图鉴记录。
  重新训练的 EfficientNet-B0 覆盖 **1498 类外观**；相同外观共用候选，稀少形态不自动确认。
- 观察记录／基础能力切换时保持展示框大小；默认经典男声，提供女声与试听。
  中文播报优先台湾国语系统音色，保留现有中文名。
- 拍照或导入照片后在手机上识别，照片仅留在内存；低置信度候选不会自动发现或朗读。
- 支持三语名称、属性与全国编号搜索，`#1025` 可精确定位；翻页覆盖全国并循环首尾。
- 应用显示名称改为 **Pokédex**，保留安装标识与发现记录键，便于沿用之前的签名安装流程。

## 实际训练与测试

使用本机 RTX 4080 SUPER 完成 8 + 12 轮训练。先按来源、重复图片、前景和镜像分组，
再划分训练/验证/测试；只用验证集选择检查点和接受策略。

混合公开分组测试：Top-1 **92.02%**，Top-3 **96.48%**；
确认的已知结果准确率 **97.53%**，确认覆盖率 **88.52%**。
严格只统计额外形态的 487 张留出图：Top-1 **73.10%**，确认结果准确率 **91.09%**。
其中地区与合体形态 65 张图的 Top-1 为 **81.54%**。包含普通外观的新来源测试另行报告。
复用的旧物种测试组另行报告。64 张自然物体负样本中误确认 4 张。
这些公开图片诊断不代表真实相机准确率；Mac 数值比较、iOS 模拟器与 Release 构建
结果分别记录于 [Apple 验证](TrainingResources/apple-validation.json)。

[形态、显示与播报说明](docs/forms-expansion.zh-CN.md) ·
[训练报告](TrainingResources/training-summary.json) ·
[训练覆盖限制](TrainingResources/training-coverage.json)

## 构建与安装

在 `national-pokedex` 分支运行 GitHub Actions 的 **Build Pokédex Forms IPA**。
云端 Mac 会转换选定的训练检查点，通过 FP32 数值一致性和 iOS 测试后，生成
`Pokedex-IPA` 安装包。Windows 用户可沿用之前成功的签名安装流程；无需本地 Mac。
应用运行时不需要服务器、API 密钥或额外下载。

生成的 Core ML 模型提交到分支后，也可使用 Xcode 27.1 打开 `iDex.xcodeproj`，
选择 `iDex` scheme 构建。应用支持 iOS 27 及以上，折叠角度接口要求 iOS 27.1 及以上。

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

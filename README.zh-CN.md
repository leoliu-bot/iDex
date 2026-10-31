[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

为 iPhone Duo 打造的离线像素风全国宝可梦图鉴。

- **1025 种、第 1～9 世代**：中英日三语名称、分类、说明、属性、身高、体重、
  六项能力值、96×96 像素图和叫声，全部随应用离线提供。
- 保留红色设备外壳、LCD 配色、像素字体、扫描动画和折叠布局；原有 151 条图文不变。
- **重新训练的 1018 类 EfficientNet-B0**。独立训练分组不足的 7 种仍可完整浏览，
  设置中按当前语言列出，不会用空类别冒充识别能力。
- 拍照或导入照片后在手机上识别，照片仅留在内存；低置信度候选不会自动发现或朗读。
- 支持三语名称、属性与全国编号搜索，`#1025` 可精确定位；翻页覆盖全国并循环首尾。
- 应用显示名称改为 **Pokédex**，保留安装标识与发现记录键，便于沿用之前的签名安装流程。

## 实际训练与测试

使用本机 RTX 4080 SUPER 完成 8 + 12 轮训练。先按来源、重复图片、前景和镜像分组，
再划分训练/验证/测试；只用验证集选择检查点和接受策略。

留出的公开分组测试集：Top-1 **92.53%**，Top-3 **96.98%**；
被接受的已知输入准确率 **97.81%**，接受覆盖率 **86.85%**。
64 张自然物体负样本中误接受 3 张。该小规模公开图片诊断不代表真实相机准确率。
Core ML 数值一致性和 iOS 测试由 Mac 构建执行，结果与桌面训练分别记录。

[工程分析与扩展说明](docs/national-expansion.zh-CN.md) ·
[训练报告](TrainingResources/training-summary.json) ·
[训练覆盖限制](TrainingResources/training-coverage.json)

## 构建与安装

在 `national-pokedex` 分支运行 GitHub Actions 的 **Build Pokédex National IPA**。
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
[National training and validation](scripts/national/README.md)

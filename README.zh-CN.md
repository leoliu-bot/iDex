[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# Pokédex

为 iPhone Duo 打造的离线像素风全国宝可梦图鉴。**1.3** 扩充识别训练，
并加入 iPhone 本机系统音色选择。

- **1025 种、第 1～9 世代**：中英日三语名称、分类、说明、属性、身高、体重、
  六项能力值、96×96 像素图和叫声，全部随应用离线提供。
- 保留红色设备外壳、LCD 配色、像素字体、扫描动画和折叠布局；原有 151 条图文不变。
- **新增 554 条地区、合体、Mega、超极巨化等形态**，共 1579 条图鉴记录。
  重新训练的 EfficientNet-B0 覆盖 **1498 类外观**；其中 **1491 类**具备自动确认资格，
  仍须通过分数门槛。相同外观共用候选，稀少形态需人工核对。
  小尺寸南瓜精因没有独立测试组，保留候选但不自动确认。
- 观察记录／基础能力切换时保持展示框大小。**58 条地区形态与 6 条合体形态**的
  中英日说明改为自然的图鉴观察记录，并保留官方对应形态的来源。
- 直接选择手机已安装的 iOS 系统音色，显示名称、地区和音质，支持试听并按语言保存。
  手动选择使用音色原本的音高和默认语速；自动男声／女声选项仍保留，中文自动模式
  优先台湾国语。宝可梦现有中文名不变。
- 顶部蓝灯随朗读进度轻微闪动，播报结束后恢复；开启「减少动态效果」时保持稳定。
- 拍照或导入照片后在手机上识别，照片仅留在内存；低置信度候选不会自动发现或朗读。
- 支持三语名称、属性与全国编号搜索，`#1025` 可精确定位；翻页覆盖全国并循环首尾。
- 应用显示名称改为 **Pokédex**，保留安装标识与发现记录键，便于沿用之前的签名安装流程。

## 实际训练与测试

使用本机 RTX 4080 SUPER 完成 **24 + 60 + 24 = 108 轮**：先在旧训练划分上做成像扰动
热身，再使用扩充来源训练，最后以更低学习率续训。新增来源涵盖游戏动画帧、卡牌插画、
遮挡文字的卡面全图、混合公开图片和厂商玩偶照片。
同一动画、同一卡牌、同一玩偶的不同视图按来源分组，查重并隔离划分冲突。
累计轮次耗时约 **128.2 分钟**；数据采集、最终评估和云端构建另外计时。

检查点和接受策略只用验证集选择，冻结后才运行最终测试。同一批 **6448 张新来源留出图／
3031 个来源组**上，逐图 Top-1 为 **冻结的 1.2 基准 33.28% → 1.3 的 88.20%**。
新版 Top-3 为 **94.43%**；已确认的已知结果准确率 **96.99%**，确认覆盖率 **78.32%**。
[新来源测试](TrainingResources/test-multidomain.json) ·
[同批输入的新旧对照](TrainingResources/paired-fresh-groups.json)

额外形态仍更容易混淆：[严格的新来源非基础形态子集](TrainingResources/test-alternate-forms-fresh.json)
（776 张／208 组）Top-1 **82.09%**，
已确认结果准确率 **89.95%**。复用的 64 张自然负样本，两版都误确认 **4 张**。
新来源和复用测试分别记录于[训练报告](TrainingResources/training-summary.json)。
公开图片和厂商棚拍图不能证明真实手机拍照准确率；明确标注的动漫测试仅 **3 张／3 组**，
不足以概括动漫识别表现。异色未单独训练。
Mac 数值比较、iOS 模拟器和 Release 构建有独立的
[Apple 验证记录](TrainingResources/apple-validation.json)。

[1.3 更新与限制](docs/multidomain-update.zh-CN.md) ·
[实际训练运行记录](TrainingResources/training-runtime.json) ·
[训练报告](TrainingResources/training-summary.json) ·
[训练协议](TrainingResources/training-protocol.json) ·
[1.2 历史测试记录](docs/forms-expansion.zh-CN.md)

## 构建与安装

在 `national-pokedex` 分支运行 GitHub Actions 的 **Build Pokédex 1.3 IPA**。
云端 Mac 会转换选定的训练检查点，通过 FP32 数值一致性、iOS 测试和安装包检查后，
提供 `Pokedex-IPA` 工件。下载解压得到 `Pokedex-1.3-unsigned.ipa`，Windows 用户可沿用
之前成功的签名安装流程，无需本地 Mac。应用运行时不需要服务器、API 密钥或额外下载；
想增加系统音色时，可先到 iPhone 设置中下载。

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
[Expanded-source training and validation](scripts/multidomain/README.md)

import SwiftUI
import UniformTypeIdentifiers

struct CatalogSheet: View {
    @Bindable var store: DexStore
    @State private var query = ""
    @State private var seenOnly = false

    var body: some View {
        NavigationStack {
            let matches = results
            VStack(spacing: 0) {
                Toggle(store.text("Discovered only", "仅显示已发现", "発見済みのみ"), isOn: $seenOnly)
                    .font(.system(size: 13, design: .monospaced)).padding(.horizontal, 20).padding(.vertical, 10)
                ScrollView {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 125), spacing: 12)], spacing: 12) {
                        ForEach(matches) { pokemon in
                            Button {
                                store.browse(pokemon)
                            } label: {
                                VStack(spacing: 8) {
                                    HStack {
                                        Text("#\(pokemon.number)").font(DexTheme.pixel(7))
                                        Spacer()
                                        if store.seenIDs.contains(pokemon.id) { Image(systemName: "checkmark.seal.fill").font(.system(size: 11)) }
                                    }
                                    Image(pokemon.spriteName).resizable().interpolation(.none).scaledToFit().frame(height: 80).accessibilityHidden(true)
                                    Text(pokemon.name(in: store.language))
                                        .font(PixelFont.font(size: store.language == .en ? 8 : 16, language: store.language))
                                        .lineLimit(1).minimumScaleFactor(0.5)
                                }.padding(12).foregroundStyle(DexTheme.ink)
                                    .background(DexTheme.lcd, in: RoundedRectangle(cornerRadius: 5))
                            }.buttonStyle(.plain).accessibilityIdentifier("pokemon-\(pokemon.id)")
                        }
                    }.padding(20)
                    if matches.isEmpty {
                        ContentUnavailableView.search(text: query)
                    }
                }
            }
            .background(DexTheme.charcoal)
            .navigationTitle(store.text("National Pokédex", "全国图鉴", "全国図鑑"))
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: store.text("Name, number or type", "名称、编号或属性", "名前・番号・タイプ"))
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button(store.text("Done", "完成", "完了")) { store.showingCatalog = false }.accessibilityIdentifier("settings-done") } }
        }.preferredColorScheme(.dark)
            .environment(\.locale, Locale(identifier: store.language.localeIdentifier))
            .statusBarHidden()
            .persistentSystemOverlays(.hidden)
    }

    private var results: [Pokemon] {
        PokemonCatalog.shared.search(query, language: store.language).filter { !seenOnly || store.seenIDs.contains($0.id) }
    }
}

struct SettingsSheet: View {
    @Bindable var store: DexStore
    @State private var voiceLibrary = VoicePackLibrary.shared
    @State private var showingVoiceImporter = false
    @State private var importingVoice = false
    @State private var voiceImportError: String?
    var body: some View {
        @Bindable var audio = store.audio
        NavigationStack {
            Form {
                Section(store.text("Language / 语言", "语言 / Language", "言語 / Language")) {
                    ForEach(AppLanguage.allCases) { language in
                        Button {
                            store.language = language
                            store.audio.play(.button)
                        } label: {
                            HStack {
                                Text(language.title).foregroundStyle(.primary)
                                Spacer()
                                if store.language == language { Image(systemName: "checkmark").foregroundStyle(.green) }
                            }
                        }.accessibilityIdentifier("language-\(language.rawValue)")
                    }
                }
                Section(store.text("Sound", "声音", "サウンド")) {
                    Toggle(store.text("Device sounds & spoken entries", "设备音效与图鉴语音", "効果音と図鑑の読み上げ"), isOn: $audio.isSoundEnabled)
                        .accessibilityIdentifier("sound-toggle")
                    Picker(store.text("Narrator", "图鉴播报音色", "読み上げ音声"), selection: $audio.narratorVoice) {
                        ForEach(NarratorVoice.allCases) { voice in
                            if voice != .imported || !voiceLibrary.imported.isEmpty {
                                Text(voice.title(in: store.language)).tag(voice)
                            }
                        }
                    }.accessibilityIdentifier("narrator-picker")
                    if audio.narratorVoice == .system {
                        Picker(store.text("Installed voice", "已安装音色", "インストール済み音声"), selection: $audio.systemVoiceIdentifier) {
                            Text(store.text("Automatic", "自动选择", "自動")).tag("")
                            ForEach(VoicePackLibrary.systemVoices(locale: store.language.speechLocale), id: \.identifier) { voice in
                                Text("\(voice.name) · \(voice.language)").tag(voice.identifier)
                            }
                        }.accessibilityIdentifier("system-voice-picker")
                    }
                    if audio.narratorVoice == .imported {
                        Picker(store.text("Offline pack", "离线音色包", "音声パック"), selection: $audio.importedVoiceFilename) {
                            Text(store.text("Choose a pack", "选择音色包", "パックを選択")).tag("")
                            ForEach(voiceLibrary.imported) { pack in Text(pack.title).tag(pack.id) }
                        }
                    }
                    Button(store.text("Import offline voice pack", "导入离线音色包", "音声パックを読み込む")) {
                        showingVoiceImporter = true
                    }.disabled(importingVoice).accessibilityIdentifier("import-voice-pack")
                    if importingVoice { ProgressView(store.text("Checking voice pack…", "正在校验音色包…", "音声パックを確認中…")) }
                    Button(store.text("Preview narrator", "试听播报", "音声を試す")) {
                        audio.speak(store.text("Pokédex ready. Point at a Pokémon to begin identification.", "宝可梦图鉴，准备就绪。请将取景器对准宝可梦，开始识别。", "ポケモン図鑑、準備完了。ポケモンにカメラを向けてください。"), languageCode: store.language.speechLocale)
                    }.disabled(!audio.isSoundEnabled).accessibilityIdentifier("narrator-preview")
                    Text(store.text("Chinese readings prefer a Taiwan Mandarin voice of the selected gender. If it is not installed, the closest available Chinese voice is used. Additional system voices can be downloaded in iPhone Settings.", "中文播报优先使用所选性别的台湾国语音色。未安装时使用可用的中文音色；可在 iPhone 系统设置中下载更多声音。", "中国語は選択した性別の台湾華語音声を優先します。未インストールの場合は利用可能な音声を使用します。追加音声はiPhoneの設定からダウンロードできます。"))
                        .font(.footnote).foregroundStyle(.secondary)
                    Text(store.text("Neural voice packs play entirely offline. Retro mode adds gentle vintage broadcast filtering. Packs cover Chinese entries; other languages or missing recordings use an installed system voice.", "自然音色包在手机上完全离线播放；复古模式加入轻微的旧式播报音色处理。音色包用于中文图鉴，其他语言或缺少录音时使用已安装的系统音色。", "ニューラル音声パックは完全オフライン。レトロモードは放送風の音質に調整します。中国語以外や録音のない項目はシステム音声を使用します。"))
                        .font(.footnote).foregroundStyle(.secondary)
                    Button(store.text("Stop reading", "停止朗读", "読み上げを停止")) { audio.stopSpeaking() }
                }
                Section(store.text("Field guide", "使用指南", "使い方")) {
                    Label(store.text("Point at a Pokémon, then identify.", "将取景器对准宝可梦，轻点识别。", "ポケモンにカメラを向けて、スキャンします。"), systemImage: "viewfinder")
                    Label(store.text("Unfold to reveal the research panel.", "展开屏幕，查看内部研究面板。", "画面を開くと、リサーチパネルが表示されます。"), systemImage: "book")
                    Label(store.text("Photos and recognition stay on your iPhone.", "照片与识别过程均留在你的 iPhone 上。", "写真と識別処理は、すべて iPhone 内で完結します。"), systemImage: "lock.shield")
                    Text(store.text("The archive contains \(PokemonCatalog.shared.speciesEntries.count) species and \(PokemonCatalog.shared.additionalFormCount) additional forms. The model contains \(RecognitionScope.entryIDs.count) appearance records; \(RecognitionScope.confirmableEntryIDs.count) have independent grouped validation. Uncertain or unvalidated results are not automatically discovered.", "图鉴收录\(PokemonCatalog.shared.speciesEntries.count)种宝可梦及\(PokemonCatalog.shared.additionalFormCount)种额外形态。模型包含\(RecognitionScope.entryIDs.count)条外观记录，其中\(RecognitionScope.confirmableEntryIDs.count)条有独立分组验证。低置信度或未验证的结果不会自动计入已发现。", "図鑑は\(PokemonCatalog.shared.speciesEntries.count)種と\(PokemonCatalog.shared.additionalFormCount)種の追加のすがたを収録。モデルは\(RecognitionScope.entryIDs.count)件に対応し、\(RecognitionScope.confirmableEntryIDs.count)件に独立グループの検証があります。未検証や確信度の低い候補は自動的に発見済みになりません。"))
                        .font(.footnote).foregroundStyle(.secondary)
                    let archiveOnly = PokemonCatalog.shared.entries.filter { !RecognitionScope.entryIDs.contains($0.id) }
                    if !archiveOnly.isEmpty {
                        NavigationLink(store.text("Archive-only records (\(archiveOnly.count))", "仅支持浏览的记录（\(archiveOnly.count)）", "図鑑閲覧のみ（\(archiveOnly.count)件）")) {
                            List(archiveOnly) { pokemon in
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(pokemon.name(in: store.language))
                                    Text("No. \(pokemon.number)").font(.caption).foregroundStyle(.secondary)
                                }
                            }.navigationTitle(store.text("Archive only", "仅支持浏览", "図鑑閲覧のみ"))
                        }
                    }
                }
                Section(store.text("Credits", "制作信息", "クレジット")) {
                    Text("Pokédex · FIELD UNIT 001").font(DexTheme.pixel(8))
                    Text(store.text("An independent fan project. Pokémon and its characters belong to Nintendo, Creatures, and GAME FREAK. Not affiliated with or endorsed by them.", "独立粉丝项目。宝可梦及相关角色归任天堂、Creatures及GAME FREAK所有。本项目与其无关联，亦未获得其认可。", "個人によるファンプロジェクトです。ポケモンおよび関連キャラクターの権利は、任天堂・クリーチャーズ・ゲームフリークに帰属します。本プロジェクトは、各社との提携や公認を受けていません。"))
                        .font(.footnote).foregroundStyle(.secondary)
                    Link(store.text("Sprites · Pokémon Database", "像素图 · Pokémon Database", "スプライト · Pokémon Database"), destination: URL(string: "https://pokemondb.net/sprites")!)
                    Link(store.text("National pixel sprites · PokéAPI / Smogon", "全国像素图 · PokéAPI / Smogon", "全国スプライト · PokéAPI / Smogon"), destination: URL(string: "https://github.com/PokeAPI/sprites")!)
                    Link(store.text("Pokédex data · PokéAPI", "图鉴数据 · PokéAPI", "図鑑データ · PokéAPI"), destination: URL(string: "https://github.com/PokeAPI/pokeapi")!)
                    Text("Press Start 2P · Fusion Pixel · SIL OFL 1.1").font(.caption).foregroundStyle(.secondary)
                }
            }.navigationTitle(store.text("Device settings", "设备设置", "デバイス設定"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button(store.text("Done", "完成", "完了")) { store.showingSettings = false }.accessibilityIdentifier("settings-done") } }
        }.preferredColorScheme(.dark)
            .environment(\.locale, Locale(identifier: store.language.localeIdentifier))
            .statusBarHidden()
            .persistentSystemOverlays(.hidden)
            .fileImporter(isPresented: $showingVoiceImporter, allowedContentTypes: [UTType(filenameExtension: "pokedexvoice") ?? .data]) { result in
                guard case let .success(url) = result else { return }
                importingVoice = true
                Task {
                    defer { importingVoice = false }
                    do {
                        let filename = try await voiceLibrary.importFile(url)
                        audio.importedVoiceFilename = filename
                        audio.narratorVoice = .imported
                    } catch {
                        voiceImportError = store.text("The voice pack could not be verified. Select a complete .pokedexvoice file.", "音色包未通过校验，请选择完整的 .pokedexvoice 文件。", "音声パックを確認できませんでした。完全な .pokedexvoice ファイルを選択してください。")
                    }
                }
            }
            .alert(store.text("Voice pack", "离线音色包", "音声パック"), isPresented: Binding(get: { voiceImportError != nil }, set: { if !$0 { voiceImportError = nil } })) {
                Button(store.text("OK", "好", "OK"), role: .cancel) { voiceImportError = nil }
            } message: { Text(voiceImportError ?? "") }
    }
}

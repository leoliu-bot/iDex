import AVFoundation
import SwiftUI

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
    @Environment(\.scenePhase) private var scenePhase
    @State private var installedVoices: [NarratorVoiceSelection.Choice] = []

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
                    Picker(store.text("Narrator", "图鉴播报音色", "読み上げ音声"), selection: voiceSelection) {
                        ForEach(NarratorVoice.allCases) { voice in
                            Text(voice.title(in: store.language)).tag("automatic:\(voice.rawValue)")
                                .accessibilityIdentifier("automatic-voice-\(voice.rawValue)")
                        }
                        ForEach(installedVoices) { voice in
                            Text("\(voice.name) · \(voice.detail(in: store.language))")
                                .tag("voice:\(voice.identifier)")
                                .accessibilityIdentifier("installed-voice-\(voice.identifier)")
                        }
                        if let selected = unavailableSelection {
                            Text(store.text("\(selected.name) · currently unavailable", "\(selected.name) · 当前不可用", "\(selected.name)・現在利用不可"))
                                .tag("voice:\(selected.identifier)")
                        }
                    }.pickerStyle(.navigationLink).accessibilityIdentifier("narrator-picker")
                    if let selected = unavailableSelection {
                        Text(store.text("\(selected.name) is no longer available on this iPhone. An automatic voice is used until it is installed again or you choose another voice.", "本机暂时无法使用\(selected.name)，会临时使用自动音色。重新安装该音色或选择其他声音后即可切换。", "\(selected.name)はこのiPhoneで現在利用できないため、自動音声を使用します。再インストールするか、別の音声を選択してください。"))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    Button(store.text("Preview narrator", "试听播报", "音声を試す")) {
                        audio.speak(store.text("Pokédex ready. Point at a Pokémon to begin identification.", "宝可梦图鉴，准备就绪。请将取景器对准宝可梦，开始识别。", "ポケモン図鑑、準備完了。ポケモンにカメラを向けてください。"), languageCode: store.language.speechLocale)
                    }.disabled(!audio.isSoundEnabled).accessibilityIdentifier("narrator-preview")
                    Text(store.text("Choose from this iPhone’s available voices for the current language, with their region and quality shown. A specific voice uses its natural pitch and speaking rate. Automatic Chinese voices prefer Taiwan Mandarin. Download additional voices in iPhone Settings; this list refreshes when you return.", "这里列出本机当前语言可用的系统音色，并显示地区与品质。选择具体音色后，保留它自然的音高和语速；自动中文音色优先台湾国语。可在 iPhone 系统设置中下载更多声音，返回这里会自动刷新。", "現在の言語でこのiPhoneが利用できる音声を地域・品質とともに表示します。指定した音声は自然な音程と速度で読み上げます。中国語の自動選択は台湾華語を優先します。追加音声はiPhoneの設定でダウンロードでき、戻ると一覧が更新されます。"))
                        .font(.footnote).foregroundStyle(.secondary)
                    if installedVoices.isEmpty {
                        Text(store.text("No standard voice for this language is currently listed by iOS. Automatic reading uses the system default.", "iOS 目前未列出该语言的标准音色，自动朗读将使用系统默认声音。", "iOSにこの言語の標準音声が表示されていません。自動読み上げではシステムの既定音声を使用します。"))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
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
            .onAppear(perform: refreshVoices)
            .onChange(of: store.language) { _, _ in refreshVoices() }
            .onChange(of: scenePhase) { _, phase in if phase == .active { refreshVoices() } }
            .onReceive(NotificationCenter.default.publisher(for: AVSpeechSynthesizer.availableVoicesDidChangeNotification)) { _ in refreshVoices() }
    }

    private var unavailableSelection: NarratorVoiceSelection.Preference? {
        guard let selected = store.audio.selectedSystemVoice(languageCode: store.language.speechLocale),
              !installedVoices.contains(where: { $0.identifier == selected.identifier }) else { return nil }
        return selected
    }

    private var voiceSelection: Binding<String> {
        Binding(get: {
            if let selected = store.audio.selectedSystemVoice(languageCode: store.language.speechLocale) {
                return "voice:\(selected.identifier)"
            }
            return "automatic:\(store.audio.narratorVoice.rawValue)"
        }, set: { value in
            if value.hasPrefix("automatic:"), let voice = NarratorVoice(rawValue: String(value.dropFirst("automatic:".count))) {
                store.audio.useAutomaticVoice(voice, languageCode: store.language.speechLocale)
            } else if value.hasPrefix("voice:"),
                      let voice = installedVoices.first(where: { $0.identifier == String(value.dropFirst("voice:".count)) }) {
                store.audio.selectSystemVoice(voice, languageCode: store.language.speechLocale)
            }
        })
    }

    private func refreshVoices() {
        installedVoices = NarratorVoiceSelection.installedChoices(locale: store.language.speechLocale)
    }
}

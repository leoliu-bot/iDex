import AVFoundation
import Foundation
import Testing
@testable import iDex

@MainActor
struct NarratorVoiceTests {
    @Test func defaultsToMaleAndPersistsFemaleChoice() {
        let defaults = UserDefaults(suiteName: "voice-tests-\(UUID())")!
        let audio = DeviceAudio(defaults: defaults)
        #expect(audio.narratorVoice == .male)
        audio.narratorVoice = .female
        #expect(DeviceAudio(defaults: defaults).narratorVoice == .female)
    }

    @Test func prefersTaiwanVoiceOfTheRequestedGender() throws {
        typealias Choice = NarratorVoiceSelection.Choice
        let choices = [Choice(identifier: "tw-f", language: "zh-TW", gender: .female, quality: 3),
                       Choice(identifier: "cn-m", language: "zh-CN", gender: .male, quality: 3),
                       Choice(identifier: "tw-m", language: "zh-TW", gender: .male, quality: 1)]
        #expect(try #require(NarratorVoiceSelection.choose(choices, locale: "zh-CN", narrator: .male)).identifier == "tw-m")
        #expect(try #require(NarratorVoiceSelection.choose(choices, locale: "zh-CN", narrator: .female)).identifier == "tw-f")
        #expect(try #require(NarratorVoiceSelection.choose(Array(choices.prefix(2)), locale: "zh-CN", narrator: .male)).identifier == "cn-m")
        #expect(NarratorVoice.readingLocale("ja-JP") == "ja-JP")
    }

    @Test func explicitInstalledVoiceOverridesAutomaticGenderAndRemovedVoiceFallsBack() throws {
        typealias Choice = NarratorVoiceSelection.Choice
        let male = Choice(identifier: "tw-m", language: "zh-TW", gender: .male, quality: 1, name: "Taiwan male")
        let female = Choice(identifier: "cn-f", language: "zh-CN", gender: .female, quality: 3, name: "Mandarin female")
        let cantonese = Choice(identifier: "hk-f", language: "zh-HK", gender: .female, quality: 3)
        #expect(try #require(NarratorVoiceSelection.choose([male, female, cantonese], locale: "zh-CN",
            narrator: .male, preferredIdentifier: female.identifier)).identifier == female.identifier)
        #expect(try #require(NarratorVoiceSelection.choose([male, cantonese], locale: "zh-CN",
            narrator: .male, preferredIdentifier: female.identifier)).identifier == male.identifier)
        #expect(try #require(NarratorVoiceSelection.choose([male, cantonese], locale: "zh-CN",
            narrator: .male, preferredIdentifier: cantonese.identifier)).identifier == cantonese.identifier)
    }

    @Test func standardVoiceListExcludesPersonalNoveltyAndUnrelatedLanguages() {
        typealias Choice = NarratorVoiceSelection.Choice
        let choices = [Choice(identifier: "tw", language: "zh-TW", gender: .male, quality: 1),
            Choice(identifier: "personal", language: "zh-TW", gender: .male, quality: 3, isPersonal: true),
            Choice(identifier: "novelty", language: "zh-CN", gender: .male, quality: 3, isNovelty: true),
            Choice(identifier: "en", language: "en-US", gender: .male, quality: 3)]
        #expect(NarratorVoiceSelection.available(choices, locale: "zh-CN").map(\.identifier) == ["tw"])
        #expect(NarratorVoiceSelection.choose(choices, locale: "zh-CN", narrator: .male,
            preferredIdentifier: "personal")?.identifier == "tw")
    }

    @Test func explicitVoicesKeepNativeDeliveryAndPreferencesRemainSeparateByLanguage() throws {
        let natural = NarratorVoiceSelection.delivery(locale: "zh-TW", narrator: .male, explicitVoice: true)
        #expect(natural.pitch == 1)
        #expect(natural.rate == AVSpeechUtteranceDefaultSpeechRate)
        let suite = "voice-preference-tests-\(UUID())"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let audio = DeviceAudio(defaults: defaults)
        let chinese = NarratorVoiceSelection.Choice(identifier: "tw-choice", language: "zh-TW", gender: .female,
            quality: 2, name: "Downloaded Mandarin")
        let english = NarratorVoiceSelection.Choice(identifier: "en-choice", language: "en-GB", gender: .male,
            quality: 2, name: "Downloaded English")
        audio.selectSystemVoice(chinese, languageCode: "zh-CN")
        audio.selectSystemVoice(english, languageCode: "en-US")
        let restored = DeviceAudio(defaults: defaults)
        #expect(restored.selectedSystemVoice(languageCode: "zh-TW")?.identifier == chinese.identifier)
        #expect(restored.selectedSystemVoice(languageCode: "en-US")?.name == english.name)
        #expect(restored.selectedSystemVoice(languageCode: "ja-JP") == nil)
        restored.useAutomaticVoice(.female, languageCode: "zh-CN")
        let automatic = DeviceAudio(defaults: defaults)
        #expect(automatic.selectedSystemVoice(languageCode: "zh-TW") == nil)
        #expect(automatic.narratorVoice == .female)
        #expect(automatic.selectedSystemVoice(languageCode: "en-US")?.identifier == english.identifier)
    }

    @Test func voiceDiscoveryMergesNotificationsAndShowsOnlyTheLatestLanguage() async throws {
        let loader = VoiceListLoaderProbe()
        let catalog = InstalledNarratorVoices(loader: { await loader.load($0) })
        defer { catalog.cancel() }
        catalog.refresh(locale: "en-US")
        try #require(await waitForVoiceList { await loader.locales.count == 1 })
        for _ in 0..<10 { catalog.refresh(locale: "en-US") }
        catalog.refresh(locale: "ja-JP")
        let english = NarratorVoiceSelection.Choice(identifier: "english", language: "en-US", gender: .male, quality: 1)
        let japanese = NarratorVoiceSelection.Choice(identifier: "japanese", language: "ja-JP", gender: .female, quality: 1)
        await loader.finishNext(with: [english])
        try #require(await waitForVoiceList { await loader.locales.count == 2 })
        #expect(catalog.choices.isEmpty)
        await loader.finishNext(with: [japanese])
        try #require(await waitForVoiceList { !catalog.isRefreshing })
        #expect(catalog.choices == [japanese])
        #expect(await loader.locales == ["en-US", "ja-JP"])
    }

    @Test func cancelledVoiceDiscoveryCannotReplaceAReopenedCatalog() async throws {
        let loader = VoiceListLoaderProbe()
        let catalog = InstalledNarratorVoices(loader: { await loader.load($0) })
        defer { catalog.cancel() }
        catalog.refresh(locale: "en-US")
        try #require(await waitForVoiceList { await loader.locales.count == 1 })
        catalog.cancel()
        catalog.refresh(locale: "zh-TW")
        try #require(await waitForVoiceList { await loader.locales.count == 2 })
        let stale = NarratorVoiceSelection.Choice(identifier: "stale", language: "en-US", gender: .male, quality: 1)
        let current = NarratorVoiceSelection.Choice(identifier: "current", language: "zh-TW", gender: .male, quality: 1)
        await loader.finishNext(with: [stale])
        #expect(catalog.choices.isEmpty)
        #expect(catalog.isRefreshing)
        await loader.finishNext(with: [current])
        try #require(await waitForVoiceList { !catalog.isRefreshing })
        #expect(catalog.choices == [current])
    }

    private func waitForVoiceList(_ condition: () async -> Bool) async -> Bool {
        for _ in 0..<200 {
            if await condition() { return true }
            try? await Task.sleep(for: .milliseconds(5))
        }
        return false
    }
}

private actor VoiceListLoaderProbe {
    private(set) var locales: [String] = []
    private var pending: [CheckedContinuation<[NarratorVoiceSelection.Choice], Never>] = []

    func load(_ locale: String) async -> [NarratorVoiceSelection.Choice] {
        locales.append(locale)
        return await withCheckedContinuation { pending.append($0) }
    }

    func finishNext(with choices: [NarratorVoiceSelection.Choice]) {
        guard !pending.isEmpty else { return }
        pending.removeFirst().resume(returning: choices)
    }
}

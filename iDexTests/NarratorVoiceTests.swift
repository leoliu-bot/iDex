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
}

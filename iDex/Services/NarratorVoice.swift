import AVFoundation
import Foundation

nonisolated enum NarratorVoice: String, CaseIterable, Identifiable, Codable, Sendable {
    case male, female

    var id: String { rawValue }
    var gender: AVSpeechSynthesisVoiceGender { self == .male ? .male : .female }
    var pitch: Float { self == .male ? 0.82 : 1.02 }

    static func readingLocale(_ languageCode: String) -> String {
        languageCode.hasPrefix("zh") ? "zh-TW" : languageCode
    }

    @MainActor func title(in language: AppLanguage) -> String {
        self == .male
            ? language.text("Classic male", "经典男声", "クラシック男性声")
            : language.text("Classic female", "经典女声", "クラシック女性声")
    }
}

/// Uses the installed voice's real gender; lowering a female voice's pitch is
/// not a substitute for selecting a male narrator. No particular actor is used.
nonisolated enum NarratorVoiceSelection {
    struct Choice: Sendable {
        let identifier: String
        let language: String
        let gender: AVSpeechSynthesisVoiceGender
        let quality: Int
    }

    static func choose(_ choices: [Choice], locale: String, narrator: NarratorVoice) -> Choice? {
        let desired = NarratorVoice.readingLocale(locale)
        let family = desired.split(separator: "-").first
        return choices.filter {
            $0.language.split(separator: "-").first == family
                && (family != "zh" || !$0.language.hasPrefix("zh-HK"))
        }.sorted {
            func score(_ voice: Choice) -> Int {
                (voice.gender == narrator.gender ? 100 : 0)
                    + (voice.language == desired ? 20 : 0) + voice.quality
            }
            let left = score($0), right = score($1)
            return left == right ? $0.identifier < $1.identifier : left > right
        }.first
    }

    static func installed(locale: String, narrator: NarratorVoice) -> AVSpeechSynthesisVoice? {
        let voices = AVSpeechSynthesisVoice.speechVoices().filter {
            !$0.voiceTraits.contains(.isPersonalVoice) && !$0.voiceTraits.contains(.isNoveltyVoice)
        }
        let choices = voices.map { Choice(identifier: $0.identifier, language: $0.language,
                                          gender: $0.gender, quality: $0.quality.rawValue) }
        guard let chosen = choose(choices, locale: locale, narrator: narrator) else { return nil }
        return voices.first { $0.identifier == chosen.identifier }
    }
}

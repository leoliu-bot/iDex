import AVFoundation
import Foundation

nonisolated enum NarratorVoice: String, CaseIterable, Identifiable, Codable, Sendable {
    case male, female, system, naturalMale, naturalFemale, retroMale, retroFemale, imported

    var id: String { rawValue }
    var gender: AVSpeechSynthesisVoiceGender {
        [.female, .naturalFemale, .retroFemale].contains(self) ? .female : .male
    }
    var pitch: Float { gender == .male ? 0.96 : 1.0 }
    var usesPack: Bool { [.naturalMale, .naturalFemale, .retroMale, .retroFemale, .imported].contains(self) }
    var isRetro: Bool { self == .retroMale || self == .retroFemale }

    static func readingLocale(_ languageCode: String) -> String {
        languageCode.hasPrefix("zh") ? "zh-TW" : languageCode
    }

    @MainActor func title(in language: AppLanguage) -> String {
        switch self {
        case .male: return language.text("System male", "系统男声", "システム男性声")
        case .female: return language.text("System female", "系统女声", "システム女性声")
        case .system: return language.text("Choose system voice", "更多系统音色", "システム音声を選ぶ")
        case .naturalMale: return language.text("Natural narrator · male", "自然图鉴男声 · 离线", "自然な男性声・オフライン")
        case .naturalFemale: return language.text("Natural narrator · female", "自然图鉴女声 · 离线", "自然な女性声・オフライン")
        case .retroMale: return language.text("Retro dub · male", "复古译制男声 · 离线", "レトロ男性声・オフライン")
        case .retroFemale: return language.text("Retro dub · female", "复古译制女声 · 离线", "レトロ女性声・オフライン")
        case .imported: return language.text("Imported voice pack", "导入的离线音色包", "読み込んだ音声パック")
        }
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

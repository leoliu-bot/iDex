import AVFoundation
import Foundation
import Observation

nonisolated enum NarratorVoice: String, CaseIterable, Identifiable, Codable, Sendable {
    case male, female

    var id: String { rawValue }
    var gender: AVSpeechSynthesisVoiceGender { self == .male ? .male : .female }
    var pitch: Float { self == .male ? 0.82 : 1.02 }

    static func readingLocale(_ languageCode: String) -> String {
        languageCode.lowercased().hasPrefix("zh") ? "zh-TW" : languageCode
    }

    @MainActor func title(in language: AppLanguage) -> String {
        self == .male
            ? language.text("Automatic male", "自动男声 · 台湾国语优先", "自動・男性声")
            : language.text("Automatic female", "自动女声 · 台湾国语优先", "自動・女性声")
    }
}

/// Uses the installed voice's real gender; lowering a female voice's pitch is
/// not a substitute for selecting a male narrator. No particular actor is used.
nonisolated enum NarratorVoiceSelection {
    struct Choice: Sendable, Identifiable, Equatable {
        let identifier: String
        let language: String
        let gender: AVSpeechSynthesisVoiceGender
        let quality: Int
        let name: String
        let isPersonal: Bool
        let isNovelty: Bool

        var id: String { identifier }

        init(identifier: String, language: String, gender: AVSpeechSynthesisVoiceGender, quality: Int,
             name: String = "", isPersonal: Bool = false, isNovelty: Bool = false) {
            self.identifier = identifier
            self.language = language
            self.gender = gender
            self.quality = quality
            self.name = name
            self.isPersonal = isPersonal
            self.isNovelty = isNovelty
        }

        @MainActor func detail(in appLanguage: AppLanguage) -> String {
            let locale = Locale(identifier: appLanguage.localeIdentifier)
            let region = locale.localizedString(forIdentifier: language) ?? language
            let tier: String
            if quality >= AVSpeechSynthesisVoiceQuality.premium.rawValue {
                tier = appLanguage.text("Premium", "高品质", "プレミアム")
            } else if quality == AVSpeechSynthesisVoiceQuality.enhanced.rawValue {
                tier = appLanguage.text("Enhanced", "增强", "拡張")
            } else {
                tier = appLanguage.text("Standard", "标准", "標準")
            }
            return "\(region) · \(tier)"
        }
    }

    struct Preference: Codable, Sendable, Equatable {
        let identifier: String
        let name: String
        let language: String

        init(_ voice: Choice) {
            identifier = voice.identifier
            name = voice.name
            language = voice.language
        }
    }

    struct Delivery: Sendable {
        let rate: Float
        let pitch: Float
        let preDelay: TimeInterval
    }

    static func languageKey(_ code: String) -> String {
        code.replacingOccurrences(of: "_", with: "-").split(separator: "-").first.map { $0.lowercased() } ?? code.lowercased()
    }

    static func available(_ choices: [Choice], locale: String) -> [Choice] {
        let desired = NarratorVoice.readingLocale(locale)
        let family = languageKey(desired)
        return choices.filter {
            !$0.isPersonal && !$0.isNovelty
                && (languageKey($0.language) == family || (family == "zh" && languageKey($0.language) == "yue"))
        }.sorted {
            let left = $0.language == desired ? 1 : 0
            let right = $1.language == desired ? 1 : 0
            if left != right { return left > right }
            if $0.language != $1.language { return $0.language < $1.language }
            if $0.quality != $1.quality { return $0.quality > $1.quality }
            if $0.name != $1.name { return $0.name < $1.name }
            return $0.identifier < $1.identifier
        }
    }

    static func choose(_ choices: [Choice], locale: String, narrator: NarratorVoice,
                       preferredIdentifier: String? = nil) -> Choice? {
        let desired = NarratorVoice.readingLocale(locale)
        let candidates = available(choices, locale: locale)
        // An explicit installed voice overrides automatic gender/region ranking.
        if let preferredIdentifier,
           let selected = candidates.first(where: { $0.identifier == preferredIdentifier }) { return selected }
        return candidates.filter {
            languageKey(desired) != "zh" || (languageKey($0.language) == "zh" && !$0.language.hasPrefix("zh-HK"))
        }.sorted {
            func score(_ voice: Choice) -> Int {
                (voice.gender == narrator.gender ? 100 : 0)
                    + (voice.language == desired ? 20 : 0) + voice.quality
            }
            let left = score($0), right = score($1)
            return left == right ? $0.identifier < $1.identifier : left > right
        }.first
    }

    private static func choices(from voices: [AVSpeechSynthesisVoice]) -> [Choice] {
        voices.map { Choice(identifier: $0.identifier, language: $0.language, gender: $0.gender,
            quality: $0.quality.rawValue, name: $0.name,
            isPersonal: $0.voiceTraits.contains(.isPersonalVoice), isNovelty: $0.voiceTraits.contains(.isNoveltyVoice)) }
    }

    static func installedChoices(locale: String) -> [Choice] {
        available(choices(from: AVSpeechSynthesisVoice.speechVoices()), locale: locale)
    }

    static func installed(locale: String, narrator: NarratorVoice,
                          preferredIdentifier: String? = nil) -> AVSpeechSynthesisVoice? {
        // Re-enumerate before every reading, so removed voices are never reused
        // from a stale object cache and newly downloaded voices become usable.
        let voices = AVSpeechSynthesisVoice.speechVoices()
        guard let chosen = choose(choices(from: voices), locale: locale, narrator: narrator,
                                  preferredIdentifier: preferredIdentifier) else { return nil }
        return voices.first { $0.identifier == chosen.identifier }
    }

    static func delivery(locale: String, narrator: NarratorVoice, explicitVoice: Bool) -> Delivery {
        if explicitVoice { return Delivery(rate: AVSpeechUtteranceDefaultSpeechRate, pitch: 1, preDelay: 0.12) }
        return Delivery(rate: locale.hasPrefix("zh") ? 0.40 : 0.46, pitch: narrator.pitch, preDelay: 0.28)
    }
}

/// System voice discovery can synchronously consult accessibility services.
/// Keep that work outside the main actor, with one enumeration in flight.
@MainActor @Observable
final class InstalledNarratorVoices {
    typealias Loader = @Sendable (String) async -> [NarratorVoiceSelection.Choice]

    private(set) var choices: [NarratorVoiceSelection.Choice] = []
    private(set) var isRefreshing = false
    @ObservationIgnored private let loader: Loader
    @ObservationIgnored private var refreshTask: Task<Void, Never>?
    @ObservationIgnored private var requestedLocale: String?
    @ObservationIgnored private var displayedLocale: String?
    @ObservationIgnored private var generation = UUID()

    init(loader: @escaping Loader = { locale in
        await Task.detached(priority: .userInitiated) {
            NarratorVoiceSelection.installedChoices(locale: locale)
        }.value
    }) {
        self.loader = loader
    }

    func refresh(locale: String) {
        if displayedLocale != locale {
            displayedLocale = locale
            if !choices.isEmpty { choices = [] }
        }
        requestedLocale = locale
        guard refreshTask == nil else { return }
        isRefreshing = true
        let token = generation
        refreshTask = Task { [weak self] in
            guard let self else { return }
            await self.loadLatest(generation: token)
        }
    }

    func cancel() {
        generation = UUID()
        refreshTask?.cancel()
        refreshTask = nil
        requestedLocale = nil
        isRefreshing = false
    }

    private func loadLatest(generation token: UUID) async {
        defer {
            if generation == token {
                refreshTask = nil
                isRefreshing = false
            }
        }
        // Merge onAppear, foreground and availability notifications arriving
        // together. Notifications during discovery share that in-flight read.
        do { try await Task.sleep(for: .milliseconds(100)) }
        catch { return }
        while let locale = requestedLocale {
            requestedLocale = nil
            let result = await loader(locale)
            guard !Task.isCancelled, generation == token else { return }
            if let pending = requestedLocale, pending != locale { continue }
            requestedLocale = nil
            // An identical availability notification must not redraw the form
            // and start another SwiftUI appearance/accessibility cycle.
            if choices != result { choices = result }
        }
    }
}

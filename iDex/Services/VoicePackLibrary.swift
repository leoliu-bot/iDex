import AVFoundation
import Foundation
import Observation

@MainActor @Observable
final class VoicePackLibrary {
    static let shared = VoicePackLibrary()

    struct Choice: Identifiable {
        let id: String
        let title: String
        let entries: Int
    }

    private(set) var imported: [Choice] = []

    nonisolated static var directory: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("OfflineVoicePacks", isDirectory: true)
    }

    nonisolated static func url(filename: String) -> URL? {
        guard filename.hasSuffix(".pokedexvoice"), filename == URL(fileURLWithPath: filename).lastPathComponent,
              !filename.contains("..") else { return nil }
        let url = directory.appendingPathComponent(filename)
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    init() { refresh() }

    func refresh() {
        imported = ((try? FileManager.default.contentsOfDirectory(at: Self.directory, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "pokedexvoice" }
            .compactMap { url in
                guard let pack = try? VoicePackFile(url: url) else { return nil }
                return Choice(id: url.lastPathComponent, title: pack.manifest.title, entries: pack.manifest.clips.count)
            }.sorted { $0.title < $1.title }
    }

    func importFile(_ url: URL) async throws -> String {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        let filename = try await Task.detached(priority: .utility) {
            _ = try VoicePackFile(url: url, verifyAllClips: true)
            let data = try Data(contentsOf: url, options: .mappedIfSafe)
            let name = VoicePackFile.hash(data) + ".pokedexvoice"
            try FileManager.default.createDirectory(at: Self.directory, withIntermediateDirectories: true)
            var destination = Self.directory.appendingPathComponent(name)
            try data.write(to: destination, options: .atomic)
            var values = URLResourceValues()
            values.isExcludedFromBackup = true
            try destination.setResourceValues(values)
            return name
        }.value
        refresh()
        return filename
    }

    static func systemVoices(locale: String) -> [AVSpeechSynthesisVoice] {
        let family = locale.split(separator: "-").first
        return AVSpeechSynthesisVoice.speechVoices().filter {
            $0.language.split(separator: "-").first == family
                && !$0.voiceTraits.contains(.isPersonalVoice) && !$0.voiceTraits.contains(.isNoveltyVoice)
        }.sorted { ($0.language, $0.name, $0.identifier) < ($1.language, $1.name, $1.identifier) }
    }
}

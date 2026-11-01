import CryptoKit
import Foundation

/// Fixed-text, locally generated speech. Packs contain audio, never executable
/// models or scripts. Clip hashes bind recordings to the exact catalog text.
nonisolated struct VoicePackFile: Sendable {
    struct Clip: Codable, Sendable {
        let offset: Int
        let length: Int
        let sha256: String
    }

    struct Manifest: Codable, Sendable {
        let formatVersion: Int
        let id: String
        let title: String
        let language: String
        let gender: String
        let attribution: String
        let clips: [String: Clip]
    }

    enum Failure: Error { case invalidHeader, invalidManifest, invalidClip, missingText }

    let manifest: Manifest
    private let data: Data
    private let audioStart: Int

    init(url: URL, verifyAllClips: Bool = false) throws {
        let data = try Data(contentsOf: url, options: .mappedIfSafe)
        guard data.count >= 12, data.count <= 512 * 1_024 * 1_024,
              data.prefix(8) == Data("PKVOICE1".utf8) else { throw Failure.invalidHeader }
        let length = (0..<4).reduce(0) { $0 | Int(data[8 + $1]) << ($1 * 8) }
        guard length > 0, length <= 2_000_000, length <= data.count - 12 else { throw Failure.invalidHeader }
        let manifest = try JSONDecoder().decode(Manifest.self, from: data.subdata(in: 12..<(12 + length)))
        let start = 12 + length
        guard manifest.formatVersion == 1, !manifest.id.isEmpty, manifest.id.count <= 80,
              !manifest.title.isEmpty, manifest.title.count <= 120,
              !manifest.clips.isEmpty, manifest.clips.count <= 20_000 else { throw Failure.invalidManifest }
        func validHash(_ value: String) -> Bool {
            value.utf8.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
        }
        var previousEnd = 0
        for (textHash, clip) in manifest.clips.sorted(by: { $0.value.offset < $1.value.offset }) {
            guard validHash(textHash), validHash(clip.sha256), clip.offset >= previousEnd,
                  clip.length > 0, clip.length <= 8 * 1_024 * 1_024,
                  clip.length <= data.count - start,
                  clip.offset <= data.count - start - clip.length else { throw Failure.invalidClip }
            previousEnd = clip.offset + clip.length
            if verifyAllClips {
                let audio = data.subdata(in: (start + clip.offset)..<(start + previousEnd))
                guard Self.hash(audio) == clip.sha256 else { throw Failure.invalidClip }
            }
        }
        self.data = data
        self.manifest = manifest
        self.audioStart = start
    }

    func audio(for text: String) throws -> Data {
        guard let clip = manifest.clips[Self.hash(Data(text.utf8))] else { throw Failure.missingText }
        let audio = data.subdata(in: (audioStart + clip.offset)..<(audioStart + clip.offset + clip.length))
        guard Self.hash(audio) == clip.sha256 else { throw Failure.invalidClip }
        return audio
    }

    static func hash(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    static func bundledURL(female: Bool) -> URL? {
        let name = female ? "taiwan-female" : "taiwan-male"
        return Bundle.main.url(forResource: name, withExtension: "pokedexvoice", subdirectory: "VoicePacks")
            ?? Bundle.main.url(forResource: name, withExtension: "pokedexvoice")
    }
}

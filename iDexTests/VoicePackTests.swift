import Foundation
import Testing
@testable import iDex

@MainActor @Suite("Offline voice packs", .serialized)
struct VoicePackTests {
    @Test func bindsRecordingsToExactTextAndRejectsCorruptionAndUnsafeBounds() throws {
        let text = "皮卡丘。"
        let url = try makePack(text: text)
        defer { try? FileManager.default.removeItem(at: url) }
        let pack = try VoicePackFile(url: url, verifyAllClips: true)
        #expect(try pack.audio(for: text).starts(with: Data("RIFF".utf8)))
        #expect(throws: VoicePackFile.Failure.self) { try pack.audio(for: "另一条资料") }
        var bytes = try Data(contentsOf: url)
        bytes[bytes.count - 1] ^= 1
        try bytes.write(to: url)
        #expect(throws: VoicePackFile.Failure.self) { try VoicePackFile(url: url, verifyAllClips: true) }
        let invalid = try makePack(text: text, offset: Int.max)
        defer { try? FileManager.default.removeItem(at: invalid) }
        #expect(throws: VoicePackFile.Failure.self) { try VoicePackFile(url: invalid) }
    }

    @Test func packedSpeechRendersAndMetersWithoutInitializingSystemSpeech() async throws {
        await DeviceAudio.shared.suspend()?.value
        defer { DeviceAudio.shared.resume() }
        let url = try makePack(text: "测试图鉴语音。")
        defer { try? FileManager.default.removeItem(at: url) }
        let began = AudioPlaybackRequest(), peaked = AudioPlaybackRequest(), finished = AudioPlaybackRequest()
        let request = AudioPlaybackRequest(voicePackURL: url, speechLevel: { level in
            if level > 0.1 { peaked.cancel() }
        }, speechActivity: { speaking in
            if speaking { began.cancel() } else { finished.cancel() }
        })
        let worker = AudioPlaybackWorker(soundVolume: 0, speechVolume: 0)
        #expect(await worker.activate())
        worker.speak("测试图鉴语音。", languageCode: "zh-TW", narrator: .retroMale, request: request)
        for _ in 0..<500 {
            if finished.isCancelled { break }
            try await Task.sleep(for: .milliseconds(10))
        }
        #expect(began.isCancelled && peaked.isCancelled && finished.isCancelled)
        #expect(await !worker.status().hasSpeechSynthesizer)
        await worker.deactivate()
    }

    private func makePack(text: String, offset: Int = 0) throws -> URL {
        var pcm = Data()
        for i in 0..<11_025 {
            var value = Int16(sin(Double(i) * 2 * .pi * 440 / 22_050) * 5_000).littleEndian
            withUnsafeBytes(of: &value) { pcm.append(contentsOf: $0) }
        }
        var wave = Data("RIFF".utf8)
        func append<T: FixedWidthInteger>(_ value: T) {
            var little = value.littleEndian
            withUnsafeBytes(of: &little) { wave.append(contentsOf: $0) }
        }
        append(UInt32(36 + pcm.count)); wave.append(Data("WAVEfmt ".utf8))
        append(UInt32(16)); append(UInt16(1)); append(UInt16(1)); append(UInt32(22_050))
        append(UInt32(44_100)); append(UInt16(2)); append(UInt16(16))
        wave.append(Data("data".utf8)); append(UInt32(pcm.count)); wave.append(pcm)
        let manifest = VoicePackFile.Manifest(formatVersion: 1, id: "fixture", title: "Offline test voice",
            language: "zh-Hans", gender: "male", attribution: "Generated sine fixture, no recorded voice",
            clips: [VoicePackFile.hash(Data(text.utf8)): .init(offset: offset, length: wave.count, sha256: VoicePackFile.hash(wave))])
        let json = try JSONEncoder().encode(manifest)
        var bytes = Data("PKVOICE1".utf8)
        var length = UInt32(json.count).littleEndian
        withUnsafeBytes(of: &length) { bytes.append(contentsOf: $0) }
        bytes.append(json); bytes.append(wave)
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("voice-fixture-\(UUID()).pokedexvoice")
        try bytes.write(to: url)
        return url
    }
}

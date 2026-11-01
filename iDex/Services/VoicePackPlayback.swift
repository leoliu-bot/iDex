import AVFoundation
import Foundation

/// Owned by AudioPlaybackWorker's serial queue. Neural speech is pre-rendered
/// locally during pack creation; phone playback and metering need no network.
nonisolated final class VoicePackPlayback: @unchecked Sendable {
    private let queue: DispatchQueue
    private let volume: Float
    private var engine: AVAudioEngine?
    private var player: AVAudioPlayerNode?
    private var equalizer: AVAudioUnitEQ?
    private var request: AudioPlaybackRequest?
    private var packs: [URL: VoicePackFile] = [:]

    init(queue: DispatchQueue, volume: Float) {
        self.queue = queue
        self.volume = volume
    }

    var isPlaying: Bool { request != nil && (player?.isPlaying ?? false) }

    func play(text: String, url: URL, retro: Bool, request: AudioPlaybackRequest) throws {
        stop()
        let pack: VoicePackFile
        if let cached = packs[url] { pack = cached }
        else { pack = try VoicePackFile(url: url); packs[url] = pack }
        let data = try pack.audio(for: text)
        let temporary = FileManager.default.temporaryDirectory.appendingPathComponent("PokedexSpeech-\(UUID().uuidString).mp3")
        try data.write(to: temporary)
        defer { try? FileManager.default.removeItem(at: temporary) }
        let file = try AVAudioFile(forReading: temporary)
        guard file.processingFormat.sampleRate == 22_050, file.processingFormat.channelCount == 1,
              file.length > 0, file.length <= 22_050 * 180,
              let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)) else {
            throw VoicePackFile.Failure.invalidClip
        }
        try file.read(into: buffer)
        guard !request.isCancelled else { return }
        if engine == nil {
            let engine = AVAudioEngine()
            let player = AVAudioPlayerNode()
            let equalizer = AVAudioUnitEQ(numberOfBands: 2)
            engine.attach(player); engine.attach(equalizer)
            try engine.connectNode(player, to: equalizer, format: file.processingFormat)
            try engine.connectNode(equalizer, to: engine.mainMixerNode, format: file.processingFormat)
            engine.mainMixerNode.outputVolume = volume
            self.engine = engine; self.player = player; self.equalizer = equalizer
        }
        guard let engine, let player, let equalizer else { throw VoicePackFile.Failure.invalidClip }
        equalizer.bands[0].filterType = .highPass
        equalizer.bands[0].frequency = 150
        equalizer.bands[0].bypass = !retro
        equalizer.bands[1].filterType = .lowPass
        equalizer.bands[1].frequency = 4_300
        equalizer.bands[1].bypass = !retro
        let meter = SpeechRenderMeter(request: request)
        try equalizer.installAudioTap(onBus: 0, bufferSize: 1_024, format: file.processingFormat) { buffer, _ in
            meter.record(buffer)
        }
        self.request = request
        engine.prepare()
        try engine.start()
        try player.scheduleBuffer(buffer, at: nil, options: [], completionCallbackType: .dataPlayedBack) { [weak self] _ in
            request.reportSpeechActivity(false)
            guard let self else { return }
            self.queue.async {
                guard self.request === request else { return }
                self.stop()
            }
        }
        try player.playAudio()
    }

    func stop() {
        player?.stop()
        if request != nil { equalizer?.removeTap(onBus: 0) }
        engine?.pause()
        request?.reportSpeechActivity(false)
        request = nil
    }
}

nonisolated private final class SpeechRenderMeter: @unchecked Sendable {
    private let lock = NSLock()
    private var started = false
    private let request: AudioPlaybackRequest

    init(request: AudioPlaybackRequest) { self.request = request }

    func record(_ buffer: AVReadOnlyAudioPCMBuffer) {
        guard !request.isCancelled, case .float(let samples) = buffer.channelData(0), buffer.frameLength > 0 else { return }
        var square = 0.0
        for i in 0..<Int(buffer.frameLength) { square += Double(samples[i] * samples[i]) }
        let rms = sqrt(square / Double(buffer.frameLength))
        if rms > 0.001 {
            let first = lock.withLock { if started { return false }; started = true; return true }
            if first { request.reportSpeechActivity(true) }
        }
        request.reportSpeechLevel(min(1, rms * 7))
    }
}

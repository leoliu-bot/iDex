import SwiftUI
import Testing
import UIKit
@testable import iDex

@MainActor
@Suite(.serialized)
struct ScannerLayoutTests {
    @Test(arguments: AppLanguage.allCases)
    func detailDisplayKeepsItsBoundsForNotesAndStats(language: AppLanguage) throws {
        let store = DexStore()
        let savedLanguage = UserDefaults.standard.object(forKey: "idex.language")
        defer { UserDefaults.standard.set(savedLanguage, forKey: "idex.language") }
        store.language = language
        store.selected = PokemonCatalog.shared.pokemon(id: 25)
        for size in [CGSize(width: 466, height: 678), CGSize(width: 465, height: 669)] {
            var bounds: [CGRect] = []
            for stats in [false, true] {
                let renderer = ImageRenderer(content: EntryPanel(store: store, showStats: stats)
                    .frame(width: size.width, height: size.height).background(ShellSurface()))
                renderer.scale = 1
                let image = try #require(renderer.uiImage)
                bounds.append(try greenDisplayBounds(image))
                Attachment.record(image, named: "detail-\(language.rawValue)-\(Int(size.width))-\(stats ? "stats" : "notes")", as: .png)
            }
            #expect(bounds[0] == bounds[1])
        }
        store.suspend()
    }

    private func greenDisplayBounds(_ image: UIImage) throws -> CGRect {
        let cgImage = try #require(image.cgImage)
        let width = cgImage.width, height = cgImage.height
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        try pixels.withUnsafeMutableBytes { bytes in
            let context = try #require(CGContext(data: bytes.baseAddress, width: width, height: height,
                bitsPerComponent: 8, bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue))
            context.draw(cgImage, in: CGRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height)))
        }
        var minX = width, minY = height, maxX = -1, maxY = -1
        for y in 80..<(height - 110) {
            for x in 0..<width {
                let i = (y * width + x) * 4
                let r = Int(pixels[i]), g = Int(pixels[i + 1]), b = Int(pixels[i + 2])
                if r > 90 && g > r + 8 && b < g - 25 {
                    minX = min(minX, x); minY = min(minY, y)
                    maxX = max(maxX, x); maxY = max(maxY, y)
                }
            }
        }
        #expect(maxX > minX && maxY > minY)
        return CGRect(x: CGFloat(minX), y: CGFloat(minY), width: CGFloat(maxX - minX + 1), height: CGFloat(maxY - minY + 1))
    }

    @Test func scanningCyclesThroughThreeLightsAndStopsForSpeech() async throws {
        let scene = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let previousWindow = scene.windows.first { $0.isKeyWindow }
        let window = UIWindow(windowScene: scene)
        let host = UIHostingController(rootView: ScannerLights(isScanning: true, isSpeaking: false)
            .padding(24).background(DexTheme.red))
        window.rootViewController = host
        window.makeKeyAndVisible()
        defer {
            window.isHidden = true
            previousWindow?.makeKey()
        }
        host.view.layoutIfNeeded()
        try await Task.sleep(for: .milliseconds(100))

        func snapshot() -> UIImage {
            UIGraphicsImageRenderer(bounds: host.view.bounds).image { _ in
                host.view.drawHierarchy(in: host.view.bounds, afterScreenUpdates: true)
            }
        }

        func pixels(_ image: UIImage) throws -> Data {
            let cgImage = try #require(image.cgImage)
            let width = cgImage.width, height = cgImage.height
            var bytes = [UInt8](repeating: 0, count: width * height * 4)
            try bytes.withUnsafeMutableBytes { buffer in
                let context = try #require(CGContext(data: buffer.baseAddress, width: width, height: height,
                    bitsPerComponent: 8, bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                    bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue))
                context.draw(cgImage, in: CGRect(x: 0, y: 0, width: CGFloat(width), height: CGFloat(height)))
            }
            return Data(bytes)
        }

        func speechLensIsLit(_ bytes: Data) -> Bool {
            // The unlit lens has no bright cyan pixels; the speech frame has
            // thousands. Confirm the new state before accepting equal frames.
            bytes.withUnsafeBytes { (buffer: UnsafeRawBufferPointer) in
                var brightCyan = 0
                for offset in stride(from: 0, to: buffer.count, by: 4) {
                    if buffer[offset] < 100 && buffer[offset + 1] > 150 && buffer[offset + 2] > 180 {
                        brightCyan += 1
                        if brightCyan > 100 { return true }
                    }
                }
                return false
            }
        }

        func sameAppearance(_ expected: Data, _ actual: Data) -> Bool {
            guard expected.count == actual.count else { return false }
            // Simulator captures of the unlit red indicator's shadow vary by
            // at most 2/255 after compositing. A chase light changes far more.
            return expected.withUnsafeBytes { (left: UnsafeRawBufferPointer) in
                actual.withUnsafeBytes { (right: UnsafeRawBufferPointer) in
                    for offset in 0..<left.count {
                        if abs(Int(left[offset]) - Int(right[offset])) > 2 { return false }
                    }
                    return true
                }
            }
        }

        func difference(_ expected: Data, _ actual: Data, width: Int) -> String {
            guard expected.count == actual.count else { return "Different byte counts: \(expected.count), \(actual.count)" }
            let baseline = [UInt8](expected), sample = [UInt8](actual)
            var count = 0, maximumDelta = 0
            var minX = width, minY = baseline.count / 4 / width, maxX = -1, maxY = -1
            for offset in stride(from: 0, to: baseline.count, by: 4) {
                var changed = false
                for channel in 0..<4 {
                    let delta = abs(Int(baseline[offset + channel]) - Int(sample[offset + channel]))
                    maximumDelta = max(maximumDelta, delta)
                    changed = changed || delta > 0
                }
                if changed {
                    count += 1
                    let pixel = offset / 4, x = pixel % width, y = pixel / width
                    minX = min(minX, x); maxX = max(maxX, x)
                    minY = min(minY, y); maxY = max(maxY, y)
                }
            }
            return "changedPixels=\(count), maximumChannelDelta=\(maximumDelta), bounds=(\(minX),\(minY))...(\(maxX),\(maxY))"
        }

        var frames: [Data] = []
        for _ in 0..<20 {
            let image = snapshot()
            let imagePixels = try pixels(image)
            if !frames.contains(where: { sameAppearance($0, imagePixels) }) {
                frames.append(imagePixels)
                Attachment.record(image, named: "scanner-chase-\(frames.count)", as: .png)
            }
            if frames.count >= 3 { break }
            try await Task.sleep(for: .milliseconds(50))
        }
        #expect(frames.count >= 3)

        host.rootView = ScannerLights(isScanning: true, isSpeaking: true)
            .padding(24).background(DexTheme.red)
        host.view.layoutIfNeeded()
        // Hosting updates are asynchronous on the simulator. Wait for the
        // speaking appearance to settle, then observe longer than a full
        // three-light chase. Normalize to RGBA8 so storage formats and row
        // padding cannot produce false differences in otherwise equal images.
        var speaking = snapshot()
        var settled = false
        for _ in 0..<15 {
            try await Task.sleep(for: .milliseconds(100))
            let next = snapshot()
            let nextPixels = try pixels(next)
            let previousPixels = try pixels(speaking)
            if speechLensIsLit(nextPixels) && sameAppearance(nextPixels, previousPixels) {
                speaking = next
                settled = true
                break
            }
            speaking = next
        }
        #expect(settled)
        let speakingPixels = try pixels(speaking)
        #expect(speechLensIsLit(speakingPixels))
        let source = try #require(speaking.cgImage)
        print("Speech snapshot: \(source.width)x\(source.height), bitsPerPixel=\(source.bitsPerPixel), bytesPerRow=\(source.bytesPerRow), bitmapInfo=\(source.bitmapInfo.rawValue)")
        for index in 0..<4 {
            try await Task.sleep(for: .milliseconds(220))
            let sample = snapshot(), samplePixels = try pixels(sample)
            let matches = sameAppearance(samplePixels, speakingPixels)
            if !matches {
                Attachment.record(sample, named: "scanner-speech-followup-\(index)", as: .png)
                print("Speech snapshot \(index): \(difference(speakingPixels, samplePixels, width: source.width))")
            }
            #expect(matches)
        }
        Attachment.record(speaking, named: "scanner-chase-stopped-for-speech", as: .png)
    }

    @Test func scannerLightsDistinguishIdleScanningAndSpeech() throws {
        for (name, scanning, speaking) in [("idle", false, false), ("scanning", true, false),
                                           ("speaking", false, true), ("speech-overrides-scan", true, true)] {
            let renderer = ImageRenderer(content: ScannerLights(isScanning: scanning, isSpeaking: speaking)
                .padding(24).background(DexTheme.red))
            renderer.scale = 3
            let image = try #require(renderer.uiImage)
            Attachment.record(image, named: "scanner-lights-\(name)", as: .png)
        }
    }

    @Test(arguments: AppLanguage.allCases)
    func scannerStatesFitCoverAndExpandedLayouts(language: AppLanguage) throws {
        let savedLanguage = UserDefaults.standard.object(forKey: "idex.language")
        let savedViewed = UserDefaults.standard.object(forKey: "idex.lastViewed")
        let soundWasEnabled = DeviceAudio.shared.isSoundEnabled
        DeviceAudio.shared.isSoundEnabled = false
        defer {
            DeviceAudio.shared.isSoundEnabled = soundWasEnabled
            UserDefaults.standard.set(savedLanguage, forKey: "idex.language")
            UserDefaults.standard.set(savedViewed, forKey: "idex.lastViewed")
        }
        let store = DexStore()
        store.language = language
        store.useSample = true
        store.capturedImage = UIImage(named: "pokemon-025")
        let candidate = RecognitionCandidate(dexID: 25, name: "pikachu", confidence: 0.1, logit: 1)

        for size in [CGSize(width: 466, height: 678), CGSize(width: 951, height: 669)] {
            for scanning in [true, false] {
                if !scanning {
                    try store.applyRecognition(RecognitionResult(candidates: [candidate], accepted: nil, logitMargin: 0))
                }
                store.isScanning = scanning
                let renderer = ImageRenderer(content: ContentView(store: store)
                    .frame(width: size.width, height: size.height))
                renderer.scale = 2
                let image = try #require(renderer.uiImage)
                #expect(image.size == size)
                let posture = size.width > 850 ? "expanded" : "cover"
                let state = scanning ? "scanning" : "best-match"
                Attachment.record(image, named: "scanner-\(posture)-\(state)-\(language.rawValue)", as: .png)
            }
            store.rescan()
            store.capturedImage = UIImage(named: "pokemon-025")
        }
        store.suspend()
    }

    @Test(arguments: AppLanguage.allCases)
    func recordsFitCoverAndExpandedLayouts(language: AppLanguage) throws {
        let savedLanguage = UserDefaults.standard.object(forKey: "idex.language")
        let savedViewed = UserDefaults.standard.object(forKey: "idex.lastViewed")
        let soundWasEnabled = DeviceAudio.shared.isSoundEnabled
        DeviceAudio.shared.isSoundEnabled = false
        defer {
            DeviceAudio.shared.isSoundEnabled = soundWasEnabled
            UserDefaults.standard.set(savedLanguage, forKey: "idex.language")
            UserDefaults.standard.set(savedViewed, forKey: "idex.lastViewed")
        }
        let store = DexStore()
        store.language = language
        // A long name and two type badges exercise the compact entry column.
        store.selected = PokemonCatalog.shared.pokemon(id: 71)
        for size in [CGSize(width: 466, height: 678), CGSize(width: 951, height: 669)] {
            let expanded = size.width > 850
            let renderer = ImageRenderer(content: Group {
                if expanded {
                    ContentView(store: store)
                } else {
                    CompactRecordView(store: store)
                }
            }.frame(width: size.width, height: size.height)
                .containerShape(UnevenRoundedRectangle(
                    topLeadingRadius: expanded ? 55 : 8,
                    bottomLeadingRadius: expanded ? 55 : 8,
                    bottomTrailingRadius: expanded ? 55 : 59,
                    topTrailingRadius: expanded ? 55 : 59
                )))
            renderer.scale = 2
            let image = try #require(renderer.uiImage)
            #expect(image.size == size)
            Attachment.record(image, named: "record-\(expanded ? "expanded" : "cover")-\(language.rawValue)", as: .png)
        }
        store.suspend()
    }
}

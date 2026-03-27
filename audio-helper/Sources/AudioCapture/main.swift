import AVFoundation
import CoreMedia
import Foundation
import ScreenCaptureKit

// MARK: - Audio Capture via ScreenCaptureKit
//
// Captures system audio and writes raw 16-bit signed LE PCM at 16kHz mono
// to stdout. No custom audio drivers needed.
//
// Usage:
//   audio-helper                     # Capture all system audio
//   audio-helper --list              # List running apps with audio
//   audio-helper --app "zoom.us"     # Capture audio from a specific app

// Output at 48kHz — resampling to 16kHz done in Python for better quality
let outputSampleRate: Double = 48000

// MARK: - Stream Output Handler

class AudioCaptureDelegate: NSObject, SCStreamDelegate, SCStreamOutput {
    private var audioFrameCount: UInt64 = 0
    private var screenFrameCount: UInt64 = 0

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        if type == .screen {
            screenFrameCount += 1
            if screenFrameCount == 1 {
                fputs("Screen frames flowing\n", stderr)
            }
            return
        }

        guard type == .audio else { return }
        guard CMSampleBufferDataIsReady(sampleBuffer) else { return }

        // Check number of samples
        let numSamples = CMSampleBufferGetNumSamples(sampleBuffer)
        if numSamples == 0 { return }

        guard let blockBuffer = CMSampleBufferGetDataBuffer(sampleBuffer) else { return }

        var length = 0
        var dataPointer: UnsafeMutablePointer<Int8>?
        let status = CMBlockBufferGetDataPointer(blockBuffer, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &length, dataPointerOut: &dataPointer)

        guard status == kCMBlockBufferNoErr, let data = dataPointer, length > 0 else { return }

        guard let formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc) else { return }

        let inputSampleRate = asbd.pointee.mSampleRate
        let inputChannels = Int(asbd.pointee.mChannelsPerFrame)
        let bitsPerChannel = Int(asbd.pointee.mBitsPerChannel)
        let formatFlags = asbd.pointee.mFormatFlags

        if audioFrameCount == 0 {
            fputs("Audio: \(inputSampleRate)Hz, \(inputChannels)ch, \(bitsPerChannel)bit, flags=0x\(String(formatFlags, radix: 16)), len=\(length)\n", stderr)
        }
        audioFrameCount += 1

        let isFloat = (formatFlags & kAudioFormatFlagIsFloat) != 0

        let monoSamples: [Float32]
        if isFloat && bitsPerChannel == 32 {
            let floatCount = length / MemoryLayout<Float32>.size
            let floatPointer = UnsafeRawPointer(data).bindMemory(to: Float32.self, capacity: floatCount)

            if inputChannels >= 2 {
                let frameCount = floatCount / inputChannels
                monoSamples = (0..<frameCount).map { frame in
                    var sum: Float32 = 0
                    for ch in 0..<inputChannels {
                        sum += floatPointer[frame * inputChannels + ch]
                    }
                    return sum / Float32(inputChannels)
                }
            } else {
                monoSamples = Array(UnsafeBufferPointer(start: floatPointer, count: floatCount))
            }
        } else {
            if audioFrameCount <= 1 {
                fputs("Warning: unexpected audio format (not float32)\n", stderr)
            }
            return
        }

        // Resample to 16kHz
        let outputSamples: [Float32]
        if abs(inputSampleRate - outputSampleRate) > 1.0 {
            let ratio = outputSampleRate / inputSampleRate
            let outputCount = Int(Double(monoSamples.count) * ratio)
            outputSamples = (0..<outputCount).map { i in
                let srcIndex = min(Int(Double(i) / ratio), monoSamples.count - 1)
                return monoSamples[srcIndex]
            }
        } else {
            outputSamples = monoSamples
        }

        // Convert float32 to int16
        let int16Samples = outputSamples.map { sample -> Int16 in
            let clamped = max(-1.0, min(1.0, sample))
            return Int16(clamped * 32767.0)
        }

        int16Samples.withUnsafeBytes { rawBuffer in
            let written = fwrite(rawBuffer.baseAddress!, 1, rawBuffer.count, stdout)
            if written != rawBuffer.count {
                exit(0)
            }
        }
        fflush(stdout)
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fputs("Stream stopped: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

// MARK: - List Apps

func listApps() async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
    let apps = content.applications
        .sorted { ($0.applicationName) < ($1.applicationName) }

    for app in apps {
        fputs("\(app.bundleIdentifier) — \(app.applicationName)\n", stderr)
    }
}

// MARK: - Start Capture

func startCapture(appBundleID: String?) async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)

    guard let display = content.displays.first else {
        fputs("Error: No display found\n", stderr)
        exit(1)
    }

    fputs("Display: \(display.width)x\(display.height)\n", stderr)

    let config = SCStreamConfiguration()

    // Audio configuration — use system defaults, resample ourselves
    config.capturesAudio = true
    config.excludesCurrentProcessAudio = false

    // Minimal video config (required for audio to flow)
    config.width = 2
    config.height = 2
    config.minimumFrameInterval = CMTime(value: 1, timescale: 2)
    config.showsCursor = false

    // Content filter
    let filter: SCContentFilter
    if let bundleID = appBundleID {
        guard let app = content.applications.first(where: { $0.bundleIdentifier == bundleID }) else {
            fputs("Error: App '\(bundleID)' not found.\n", stderr)
            exit(1)
        }
        filter = SCContentFilter(display: display, including: [app], exceptingWindows: [])
        fputs("Capturing: \(app.applicationName) (\(bundleID))\n", stderr)
    } else {
        filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
        fputs("Capturing: all system audio\n", stderr)
    }

    let delegate = AudioCaptureDelegate()
    let stream = SCStream(filter: filter, configuration: config, delegate: delegate)

    let audioQueue = DispatchQueue(label: "audio", qos: .userInteractive)
    let screenQueue = DispatchQueue(label: "screen", qos: .background)

    try stream.addStreamOutput(delegate, type: .screen, sampleHandlerQueue: screenQueue)
    try stream.addStreamOutput(delegate, type: .audio, sampleHandlerQueue: audioQueue)

    fputs("Starting capture...\n", stderr)
    signal(SIGPIPE, SIG_IGN)
    try await stream.startCapture()
    fputs("Stream active\n", stderr)

    // Keep running — use RunLoop instead of dispatchMain() for subprocess compatibility
    while true {
        try await Task.sleep(for: .seconds(1))
    }
}

// MARK: - Main

let args = CommandLine.arguments

Task {
    do {
        if args.contains("--list") {
            try await listApps()
            exit(0)
        } else {
            let appBundleID: String?
            if let appIndex = args.firstIndex(of: "--app"), appIndex + 1 < args.count {
                appBundleID = args[appIndex + 1]
            } else {
                appBundleID = nil
            }
            try await startCapture(appBundleID: appBundleID)
        }
    } catch {
        fputs("Error: \(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

// Keep process alive using RunLoop (more compatible with subprocess execution than dispatchMain)
RunLoop.current.run()

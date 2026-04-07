import AVFoundation
import SwiftUI
import UIKit
import Vision

/// Live camera scanner that automatically captures when a target is
/// detected, stable, and large enough.
struct LiveScannerView: View {
    let competition: Competition
    let session: CompetitionSession
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var capturedImage: UIImage?
    @State private var scanResult: ScanResult?
    @State private var showReview = false

    var body: some View {
        NavigationStack {
            ZStack {
                LiveCameraView(
                    onAutoCaptured: { image, result in
                        capturedImage = image
                        scanResult = result
                        showReview = true
                    }
                )
                .ignoresSafeArea()

                VStack {
                    HStack {
                        Button {
                            dismiss()
                        } label: {
                            Image(systemName: "xmark")
                                .font(.title3)
                                .fontWeight(.semibold)
                                .foregroundStyle(.white)
                                .padding(12)
                                .background(.black.opacity(0.5), in: Circle())
                        }
                        Spacer()
                    }
                    .padding()
                    Spacer()
                }
            }
            .navigationBarHidden(true)
            .navigationDestination(isPresented: $showReview) {
                if let image = capturedImage, let result = scanResult {
                    ScanReviewView(
                        image: image,
                        scanResult: result,
                        competition: competition,
                        session: session,
                        onSaved: {
                            dismiss()
                            await onSaved?()
                        }
                    )
                }
            }
        }
    }
}

// MARK: - Live Camera UIViewRepresentable

struct LiveCameraView: UIViewRepresentable {
    var onAutoCaptured: (UIImage, ScanResult) -> Void

    func makeUIView(context: Context) -> LiveCameraUIView {
        let view = LiveCameraUIView()
        view.onAutoCaptured = onAutoCaptured
        return view
    }

    func updateUIView(_ uiView: LiveCameraUIView, context: Context) {}
}

/// UIView-based camera view. Uses a separate nonisolated delegate
/// to handle camera callbacks on background queues without
/// conflicting with @MainActor isolation.
class LiveCameraUIView: UIView {
    var onAutoCaptured: ((UIImage, ScanResult) -> Void)?

    private let captureSession = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private let sessionQueue = DispatchQueue(label: "de.unefy.scanner.session")
    private var delegate: CameraDelegate?
    private let overlayLayer = CALayer()
    private let statusLabel = UILabel()

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .black
        setupOverlay()
        sessionQueue.async { [weak self] in
            self?.setupCamera()
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        previewLayer?.frame = bounds
        overlayLayer.frame = bounds
    }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil {
            sessionQueue.async { [weak self] in
                self?.captureSession.startRunning()
            }
        } else {
            sessionQueue.async { [weak self] in
                self?.captureSession.stopRunning()
            }
        }
    }

    private func setupOverlay() {
        overlayLayer.frame = bounds
        layer.addSublayer(overlayLayer)

        statusLabel.font = .systemFont(ofSize: 16, weight: .semibold)
        statusLabel.textColor = .white
        statusLabel.textAlignment = .center
        statusLabel.backgroundColor = UIColor.black.withAlphaComponent(0.6)
        statusLabel.layer.cornerRadius = 16
        statusLabel.clipsToBounds = true
        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.text = "  Scheibe suchen…  "
        addSubview(statusLabel)
        NSLayoutConstraint.activate([
            statusLabel.bottomAnchor.constraint(equalTo: safeAreaLayoutGuide.bottomAnchor, constant: -80),
            statusLabel.centerXAnchor.constraint(equalTo: centerXAnchor),
            statusLabel.heightAnchor.constraint(equalToConstant: 40),
            statusLabel.widthAnchor.constraint(greaterThanOrEqualToConstant: 200),
        ])
    }

    /// Called on sessionQueue.
    private func setupCamera() {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let input = try? AVCaptureDeviceInput(device: device) else {
            return
        }

        let videoOutput = AVCaptureVideoDataOutput()
        let photoOutput = AVCapturePhotoOutput()
        let processingQueue = DispatchQueue(label: "de.unefy.scanner.processing", qos: .userInitiated)

        captureSession.beginConfiguration()
        captureSession.sessionPreset = .photo
        if captureSession.canAddInput(input) { captureSession.addInput(input) }

        videoOutput.alwaysDiscardsLateVideoFrames = true
        if captureSession.canAddOutput(videoOutput) { captureSession.addOutput(videoOutput) }
        if captureSession.canAddOutput(photoOutput) { captureSession.addOutput(photoOutput) }

        let del = CameraDelegate(
            photoOutput: photoOutput,
            sessionQueue: sessionQueue,
            captureSession: captureSession,
            overlayLayer: overlayLayer,
            statusLabel: statusLabel,
            onAutoCaptured: { [weak self] image, result in
                DispatchQueue.main.async {
                    self?.onAutoCaptured?(image, result)
                }
            }
        )
        videoOutput.setSampleBufferDelegate(del, queue: processingQueue)
        self.delegate = del

        captureSession.commitConfiguration()

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let preview = AVCaptureVideoPreviewLayer(session: self.captureSession)
            preview.videoGravity = .resizeAspectFill
            preview.frame = self.bounds
            self.layer.insertSublayer(preview, at: 0)
            self.previewLayer = preview
        }

    }
}

// MARK: - Camera Delegate (nonisolated — runs on background queues)

nonisolated private class CameraDelegate: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, AVCapturePhotoCaptureDelegate, @unchecked Sendable {
    private let photoOutput: AVCapturePhotoOutput
    private let sessionQueue: DispatchQueue
    private let captureSession: AVCaptureSession
    private weak var overlayLayer: CALayer?
    private weak var statusLabel: UILabel?
    private let onAutoCaptured: (UIImage, ScanResult) -> Void

    private var vnModel: VNCoreMLModel?
    /// Lock protecting mutable state accessed from multiple queues.
    private let stateLock = NSLock()
    private var frameCount = 0
    private var _isProcessingFrame = false
    private var _isCapturing = false
    private var targetStableFrames = 0
    private var lastTargetBBox: CGRect = .zero
    private let requiredStableFrames = 20
    private let minTargetFraction: CGFloat = 0.3
    private let stabilityThreshold: CGFloat = 0.03
    private let confidenceThreshold: Float = 0.5
    private let numClasses = 6
    private let classNames: [Int: String] = [
        0: "hit_cluster", 1: "hit_medium", 2: "hit_small",
        3: "patch", 4: "target", 5: "target_center",
    ]

    init(photoOutput: AVCapturePhotoOutput, sessionQueue: DispatchQueue,
         captureSession: AVCaptureSession, overlayLayer: CALayer,
         statusLabel: UILabel, onAutoCaptured: @escaping (UIImage, ScanResult) -> Void) {
        self.photoOutput = photoOutput
        self.sessionQueue = sessionQueue
        self.captureSession = captureSession
        self.overlayLayer = overlayLayer
        self.statusLabel = statusLabel
        self.onAutoCaptured = onAutoCaptured
        super.init()
        loadModel()
    }

    private func loadModel() {
        for name in ["TargetDetector", "best"] {
            for ext in ["mlmodelc", "mlpackage"] {
                if let url = Bundle.main.url(forResource: name, withExtension: ext) {
                    let config = MLModelConfiguration()
                    config.computeUnits = .all
                    if let ml = try? MLModel(contentsOf: url, configuration: config) {
                        vnModel = try? VNCoreMLModel(for: ml)
                        return
                    }
                }
            }
        }
    }

    // MARK: - Thread-safe accessors

    private var isCapturing: Bool {
        get { stateLock.lock(); defer { stateLock.unlock() }; return _isCapturing }
        set { stateLock.lock(); defer { stateLock.unlock() }; _isCapturing = newValue }
    }

    private var isProcessingFrame: Bool {
        get { stateLock.lock(); defer { stateLock.unlock() }; return _isProcessingFrame }
        set { stateLock.lock(); defer { stateLock.unlock() }; _isProcessingFrame = newValue }
    }

    // MARK: - Video Frame

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard !isCapturing, !isProcessingFrame else { return }
        frameCount += 1
        guard frameCount % 3 == 0 else { return }
        guard let vnModel, let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        isProcessingFrame = true
        let request = VNCoreMLRequest(model: vnModel) { [weak self] request, _ in
            guard let self else { return }
            let detections = self.parseOutput(request.results ?? [])
            let target = detections.first { $0.className == "target" }
            self.updateOverlay(detections)
            self.checkAutoCapture(target: target)
            self.isProcessingFrame = false
        }
        request.imageCropAndScaleOption = .scaleFill
        try? VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:]).perform([request])
    }

    // MARK: - Photo Capture

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        guard let data = photo.fileDataRepresentation(), let image = UIImage(data: data) else {
            isCapturing = false
            return
        }
        sessionQueue.async { [weak self] in
            self?.captureSession.stopRunning()
        }
        let detector = TargetDetectorService()
        Task {
            let result = try? await detector.detect(in: image)
            self.onAutoCaptured(image, result ?? ScanResult(detections: [], imageSize: image.size))
        }
    }

    // MARK: - Auto-Capture

    private func checkAutoCapture(target: Detection?) {
        guard !isCapturing, let target else {
            targetStableFrames = 0
            return
        }
        let fraction = target.bbox.width * target.bbox.height
        guard fraction >= minTargetFraction else {
            targetStableFrames = 0
            return
        }
        let dx = abs(target.bbox.midX - lastTargetBBox.midX)
        let dy = abs(target.bbox.midY - lastTargetBBox.midY)
        if dx < stabilityThreshold && dy < stabilityThreshold {
            targetStableFrames += 1
        } else {
            targetStableFrames = max(0, targetStableFrames - 5)
        }
        lastTargetBBox = target.bbox

        if targetStableFrames >= requiredStableFrames {
            isCapturing = true
            DispatchQueue.main.async {
                UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
            }
            sessionQueue.async { [weak self] in
                guard let self else { return }
                let settings = AVCapturePhotoSettings()
                self.photoOutput.capturePhoto(with: settings, delegate: self)
            }
        }
    }

    // MARK: - Overlay

    private func updateOverlay(_ detections: [Detection]) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let overlay = self.overlayLayer, let label = self.statusLabel else { return }
            let viewSize = overlay.bounds.size
            overlay.sublayers?.forEach { $0.removeFromSuperlayer() }

            let target = detections.first { $0.className == "target" }
            let hits = detections.filter { $0.className.hasPrefix("hit") }
            let patches = detections.filter { $0.className == "patch" }

            if let t = target {
                let rect = CGRect(
                    x: t.bbox.minX * viewSize.width, y: t.bbox.minY * viewSize.height,
                    width: t.bbox.width * viewSize.width, height: t.bbox.height * viewSize.height
                )
                let border = CAShapeLayer()
                border.path = UIBezierPath(roundedRect: rect, cornerRadius: 8).cgPath
                border.strokeColor = UIColor.systemGreen.cgColor
                border.fillColor = nil
                border.lineWidth = 3
                border.lineDashPattern = [8, 4]
                overlay.addSublayer(border)
            }

            for hit in hits {
                let c = CGPoint(x: hit.center.x * viewSize.width, y: hit.center.y * viewSize.height)
                let dot = CAShapeLayer()
                dot.path = UIBezierPath(ovalIn: CGRect(x: c.x - 6, y: c.y - 6, width: 12, height: 12)).cgPath
                dot.fillColor = UIColor.systemRed.cgColor
                dot.strokeColor = UIColor.white.cgColor
                dot.lineWidth = 1.5
                overlay.addSublayer(dot)
            }

            for patch in patches {
                let c = CGPoint(x: patch.center.x * viewSize.width, y: patch.center.y * viewSize.height)
                let dot = CAShapeLayer()
                dot.path = UIBezierPath(ovalIn: CGRect(x: c.x - 5, y: c.y - 5, width: 10, height: 10)).cgPath
                dot.fillColor = UIColor.gray.withAlphaComponent(0.5).cgColor
                overlay.addSublayer(dot)
            }

            // Status
            if let t = target {
                let frac = t.bbox.width * t.bbox.height
                let progress = min(1.0, CGFloat(self.targetStableFrames) / CGFloat(self.requiredStableFrames))
                if frac < self.minTargetFraction {
                    label.text = "  📷 Näher rangehen  "
                    label.backgroundColor = UIColor.systemOrange.withAlphaComponent(0.8)
                } else if progress < 1.0 {
                    label.text = "  Ruhig halten… \(Int(progress * 100))%  "
                    label.backgroundColor = UIColor.systemBlue.withAlphaComponent(0.8)
                } else {
                    label.text = "  ✓ Wird aufgenommen…  "
                    label.backgroundColor = UIColor.systemGreen.withAlphaComponent(0.8)
                }
            } else {
                label.text = "  Scheibe suchen…  "
                label.backgroundColor = UIColor.black.withAlphaComponent(0.6)
            }
        }
    }

    // MARK: - YOLO Post-Processing

    private func parseOutput(_ results: [Any]) -> [Detection] {
        guard let obs = results as? [VNCoreMLFeatureValueObservation],
              let tensor = obs.first(where: {
                  $0.featureValue.multiArrayValue?.shape.count == 3
                  && ($0.featureValue.multiArrayValue?.shape[2].intValue ?? 0) > 1000
              })?.featureValue.multiArrayValue else { return [] }

        let cols = tensor.shape[2].intValue
        let inputSize: Float = 1280
        let ptr = tensor.dataPointer.assumingMemoryBound(to: Float.self)
        var candidates: [Detection] = []

        for j in 0..<cols {
            var bestCls = -1; var bestScore: Float = 0
            for c in 0..<numClasses {
                let s = ptr[(4 + c) * cols + j]
                if s > bestScore { bestScore = s; bestCls = c }
            }
            guard bestScore >= confidenceThreshold else { continue }
            let cx = ptr[j] / inputSize
            let cy = ptr[cols + j] / inputSize
            let w = ptr[2 * cols + j] / inputSize
            let h = ptr[3 * cols + j] / inputSize
            candidates.append(Detection(
                id: UUID().uuidString, classId: bestCls,
                className: classNames[bestCls] ?? "unknown",
                bbox: CGRect(x: CGFloat(cx - w/2), y: CGFloat(cy - h/2), width: CGFloat(w), height: CGFloat(h)),
                confidence: bestScore
            ))
        }
        return postFilter(nms(candidates))
    }

    private func postFilter(_ dets: [Detection]) -> [Detection] {
        var result: [Detection] = []
        var bestTarget: Detection?
        var bestCenter: Detection?
        for d in dets {
            if d.isTarget {
                if bestTarget == nil || d.confidence > bestTarget!.confidence { bestTarget = d }
            } else if d.isTargetCenter {
                if bestCenter == nil || d.confidence > bestCenter!.confidence { bestCenter = d }
            } else {
                result.append(d)
            }
        }
        if let t = bestTarget { result.append(t) }
        if let c = bestCenter { result.append(c) }
        return result
    }

    private func nms(_ dets: [Detection]) -> [Detection] {
        var result: [Detection] = []
        for (_, group) in Dictionary(grouping: dets, by: { $0.className }) {
            let sorted = group.sorted { $0.confidence > $1.confidence }
            var kept: [Detection] = []
            for d in sorted {
                if !kept.contains(where: { iou(d.bbox, $0.bbox) > 0.45 }) { kept.append(d) }
            }
            result.append(contentsOf: kept)
        }
        return result
    }

    private func iou(_ a: CGRect, _ b: CGRect) -> Float {
        let i = a.intersection(b)
        guard !i.isNull else { return 0 }
        let ia = Float(i.width * i.height)
        let ua = Float(a.width * a.height + b.width * b.height) - ia
        return ua > 0 ? ia / ua : 0
    }
}

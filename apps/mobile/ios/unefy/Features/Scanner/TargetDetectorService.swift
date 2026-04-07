import CoreImage
import CoreML
import UIKit
import Vision

/// Runs the TargetDetector Core ML model on an image and returns detections.
/// The YOLOv8-seg model outputs raw tensors — we post-process them manually
/// (bbox extraction, confidence filter, NMS).
nonisolated final class TargetDetectorService: @unchecked Sendable {

    private let classNames: [Int: String] = [
        0: "hit_cluster",
        1: "hit_medium",
        2: "hit_small",
        3: "patch",
        4: "target",
        5: "target_center",
    ]

    private let numClasses = 6
    private let confidenceThreshold: Float = 0.5
    private let iouThreshold: Float = 0.45
    private var mlModel: MLModel?

    init() {
        loadModel()
    }

    private func loadModel() {
        let candidates = ["TargetDetector", "best"]
        let extensions = ["mlmodelc", "mlpackage"]

        var modelURL: URL?
        for name in candidates {
            for ext in extensions {
                if let url = Bundle.main.url(forResource: name, withExtension: ext) {
                    modelURL = url
                    break
                }
            }
            if modelURL != nil { break }
        }

        guard let url = modelURL else {
            print("[TargetDetector] Model not found in bundle")
            return
        }

        do {
            let config = MLModelConfiguration()
            config.computeUnits = .all
            mlModel = try MLModel(contentsOf: url, configuration: config)
            print("[TargetDetector] Model loaded")
        } catch {
            print("[TargetDetector] Load error: \(error)")
        }
    }

    var isModelLoaded: Bool { mlModel != nil }

    @concurrent
    func detect(in image: UIImage) async throws -> ScanResult {
        guard let mlModel else {
            return ScanResult(detections: [], imageSize: image.size)
        }
        guard let cgImage = image.cgImage else {
            return ScanResult(detections: [], imageSize: image.size)
        }

        let imageSize = CGSize(
            width: CGFloat(cgImage.width),
            height: CGFloat(cgImage.height)
        )

        // Use Vision to handle image preprocessing (resize to 640x640).
        let vnModel = try VNCoreMLModel(for: mlModel)

        return try await withCheckedThrowingContinuation { continuation in
            let request = VNCoreMLRequest(model: vnModel) { [weak self] request, error in
                guard let self else {
                    continuation.resume(returning: ScanResult(detections: [], imageSize: imageSize))
                    return
                }
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let detections = self.postProcess(results: request.results ?? [])
                print("[TargetDetector] Detections: \(detections.count)")
                continuation.resume(returning: ScanResult(detections: detections, imageSize: imageSize))
            }
            request.imageCropAndScaleOption = .scaleFill

            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            do {
                try handler.perform([request])
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    // MARK: - YOLOv8 Raw Output Post-Processing

    /// Parse the raw YOLOv8-seg output tensor into detections.
    /// Tensor shape: 1 × (4 + numClasses + 32) × 8400
    /// - Rows 0-3: cx, cy, w, h (normalized to 640)
    /// - Rows 4..<4+numClasses: class scores
    /// - Rows 4+numClasses..: mask coefficients (ignored)
    private func postProcess(results: [Any]) -> [Detection] {
        guard let observations = results as? [VNCoreMLFeatureValueObservation] else {
            return []
        }

        // Find the detection tensor (1 × 44 × 8400 for 8 classes + 4 bbox + 32 masks).
        guard let detTensor = observations.first(where: {
            $0.featureValue.multiArrayValue?.shape.count == 3
            && $0.featureValue.multiArrayValue?.shape[2].intValue ?? 0 > 1000
        })?.featureValue.multiArrayValue else {
            print("[TargetDetector] Detection tensor not found")
            return []
        }

        let shape = detTensor.shape.map { $0.intValue }
        // shape = [1, 44, 8400] → rows=44, cols=8400
        let rows = shape[1]
        let cols = shape[2]
        let inputSize: Float = 1280.0

        guard rows >= 4 + numClasses else {
            print("[TargetDetector] Unexpected tensor shape: \(shape)")
            return []
        }

        let pointer = detTensor.dataPointer.assumingMemoryBound(to: Float.self)

        var candidates: [Detection] = []

        for j in 0..<cols {
            // Extract class scores.
            var bestClassId = -1
            var bestScore: Float = 0
            for c in 0..<numClasses {
                let score = pointer[(4 + c) * cols + j]
                if score > bestScore {
                    bestScore = score
                    bestClassId = c
                }
            }

            guard bestScore >= confidenceThreshold else { continue }

            // Extract bbox (cx, cy, w, h in pixel coords relative to 640x640).
            let cx = pointer[0 * cols + j] / inputSize
            let cy = pointer[1 * cols + j] / inputSize
            let w = pointer[2 * cols + j] / inputSize
            let h = pointer[3 * cols + j] / inputSize

            let bbox = CGRect(
                x: CGFloat(cx - w / 2),
                y: CGFloat(cy - h / 2),
                width: CGFloat(w),
                height: CGFloat(h)
            )

            let className = mapClassName(classNames[bestClassId] ?? "unknown")

            candidates.append(Detection(
                id: UUID().uuidString,
                classId: bestClassId,
                className: className,
                bbox: bbox,
                confidence: bestScore
            ))
        }

        // Apply NMS per class, then post-filter.
        return postFilter(nms(candidates))
    }

    /// Keep only the single best detection for target + target_center.
    private func postFilter(_ detections: [Detection]) -> [Detection] {
        var result: [Detection] = []
        var bestTarget: Detection?
        var bestCenter: Detection?

        for det in detections {
            if det.isTarget {
                if bestTarget == nil || det.confidence > bestTarget!.confidence {
                    bestTarget = det
                }
            } else if det.isTargetCenter {
                if bestCenter == nil || det.confidence > bestCenter!.confidence {
                    bestCenter = det
                }
            } else {
                result.append(det)
            }
        }
        if let t = bestTarget { result.append(t) }
        if let c = bestCenter { result.append(c) }
        return result
    }

    /// Non-Maximum Suppression: remove overlapping boxes per class.
    private func nms(_ detections: [Detection]) -> [Detection] {
        var result: [Detection] = []
        let grouped = Dictionary(grouping: detections, by: { $0.className })

        for (_, group) in grouped {
            let sorted = group.sorted { $0.confidence > $1.confidence }
            var kept: [Detection] = []

            for det in sorted {
                var dominated = false
                for existing in kept {
                    if iou(det.bbox, existing.bbox) > iouThreshold {
                        dominated = true
                        break
                    }
                }
                if !dominated {
                    kept.append(det)
                }
            }
            result.append(contentsOf: kept)
        }

        return result
    }

    private func iou(_ a: CGRect, _ b: CGRect) -> Float {
        let intersection = a.intersection(b)
        guard !intersection.isNull else { return 0 }
        let intersectionArea = Float(intersection.width * intersection.height)
        let unionArea = Float(a.width * a.height + b.width * b.height) - intersectionArea
        return unionArea > 0 ? intersectionArea / unionArea : 0
    }

    private func mapClassName(_ raw: String) -> String {
        raw
    }
}

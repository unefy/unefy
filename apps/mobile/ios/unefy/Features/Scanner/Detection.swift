import Foundation
import CoreGraphics

/// A single detection from the ML model.
nonisolated struct Detection: Identifiable, Sendable {
    let id: String
    let classId: Int
    let className: String
    /// Bounding box in normalized image coordinates (0...1).
    let bbox: CGRect
    let confidence: Float

    var isHit: Bool {
        className.hasPrefix("hit_")
    }

    var isPatch: Bool {
        className == "patch"
    }

    var isTarget: Bool {
        className == "target"
    }

    var isTargetCenter: Bool {
        className == "target_center"
    }

    var isCluster: Bool {
        className == "hit_cluster"
    }

    /// Center point in normalized coordinates.
    var center: CGPoint {
        CGPoint(x: bbox.midX, y: bbox.midY)
    }
}

/// Result of running the ML model on a target photo.
nonisolated struct ScanResult: Sendable {
    let detections: [Detection]
    let imageSize: CGSize

    var target: Detection? { detections.first { $0.isTarget } }
    var targetCenter: Detection? { detections.first { $0.isTargetCenter } }
    var hits: [Detection] { detections.filter { $0.isHit } }
    var patches: [Detection] { detections.filter { $0.isPatch } }
    var clusters: [Detection] { detections.filter { $0.isCluster } }

    /// Convert a hit detection to normalized coordinates relative to the
    /// target center (-1...1, center = 0,0).
    func normalizedPosition(of hit: Detection) -> (x: Double, y: Double)? {
        guard let target, let center = targetCenter else { return nil }
        let targetWidth = target.bbox.width
        let targetHeight = target.bbox.height
        guard targetWidth > 0, targetHeight > 0 else { return nil }

        let cx = center.center.x
        let cy = center.center.y
        let hx = hit.center.x
        let hy = hit.center.y

        // Normalize: distance from center as fraction of target radius.
        let nx = Double((hx - cx) / (targetWidth / 2))
        let ny = Double((hy - cy) / (targetHeight / 2))
        return (x: nx, y: ny)
    }
}

import SwiftUI

/// Read-only rendering of a target with shots. Used in entry detail views.
struct TargetView: View {
    let shots: [EntryDetails.ShotDetail]
    let targetType: TargetType?
    var size: CGFloat = 280

    private var tt: TargetType { targetType ?? .sportPistol25m }

    var body: some View {
        Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
            let viewRadius = min(canvasSize.width, canvasSize.height) / 2

            // Background
            context.fill(
                Path(CGRect(origin: .zero, size: canvasSize)),
                with: .color(Color(red: 0.95, green: 0.92, blue: 0.78))
            )

            // Black zone
            let blackR = tt.ringFraction(ring: tt.blackFromRing) * viewRadius
            context.fill(
                Path(ellipseIn: CGRect(x: center.x - blackR, y: center.y - blackR, width: blackR * 2, height: blackR * 2)),
                with: .color(.black)
            )

            // Rings
            for ring in 1...10 {
                let r = tt.ringFraction(ring: ring) * viewRadius
                let rect = CGRect(x: center.x - r, y: center.y - r, width: r * 2, height: r * 2)
                let isBlack = ring >= tt.blackFromRing
                context.stroke(Path(ellipseIn: rect), with: .color(isBlack ? .white.opacity(0.4) : .black.opacity(0.25)), lineWidth: 0.5)
            }

            // Shots
            let markerR = max(CGFloat(tt.caliberDiameter / tt.totalDiameter) * viewRadius, 3)
            for (i, shot) in shots.enumerated() {
                let px = center.x + CGFloat(shot.x) * viewRadius
                let py = center.y + CGFloat(shot.y) * viewRadius

                // Shot hole
                context.fill(
                    Path(ellipseIn: CGRect(x: px - markerR, y: py - markerR, width: markerR * 2, height: markerR * 2)),
                    with: .color(.red)
                )
                // White center dot
                let inner = max(markerR * 0.3, 1)
                context.fill(
                    Path(ellipseIn: CGRect(x: px - inner, y: py - inner, width: inner * 2, height: inner * 2)),
                    with: .color(.white.opacity(0.8))
                )
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

extension TargetView {
    init(details: EntryDetails?, size: CGFloat = 280) {
        self.shots = details?.shots ?? []
        self.targetType = details?.targetType.flatMap { TargetType.byId($0) }
        self.size = size
    }
}

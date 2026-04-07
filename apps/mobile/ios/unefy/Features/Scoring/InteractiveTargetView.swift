import SwiftUI

/// A shot placed on the target by the user.
struct PlacedShot: Identifiable, Equatable {
    let id: String
    var x: Double
    var y: Double
    var ring: Int

    init(x: Double, y: Double, ring: Int = 0) {
        self.id = UUID().uuidString
        self.x = x
        self.y = y
        self.ring = ring
    }
}

/// Interactive shooting target with native UIScrollView zoom/pan.
/// Tap = place shot. Long-press on shot = edit callback.
struct InteractiveTargetView: View {
    let targetType: TargetType
    @Binding var shots: [PlacedShot]
    /// Called when user long-presses on an existing shot.
    var onLongPressShot: ((PlacedShot) -> Void)?

    var body: some View {
        ZoomableContainer(minScale: 1, maxScale: 8) {
            TargetShapeView(
                targetType: targetType,
                shots: $shots,
                onLongPressShot: onLongPressShot
            )
        }
    }
}

/// Vector-based target rendering using SwiftUI Shapes.
private struct TargetShapeView: View {
    let targetType: TargetType
    @Binding var shots: [PlacedShot]
    var onLongPressShot: ((PlacedShot) -> Void)?
    @State private var selectedShotId: String?

    private let sheetToScoringRatio: CGFloat = 1.1

    var body: some View {
        GeometryReader { geo in
            let size = min(geo.size.width, geo.size.height)
            let center = size / 2
            let scoringRadius = center / sheetToScoringRatio

            ZStack {
                // Sheet background
                Rectangle()
                    .fill(Color(red: 0.94, green: 0.91, blue: 0.77))

                // Black zone (Spiegel)
                let blackR = targetType.ringFraction(ring: targetType.blackFromRing) * scoringRadius
                Circle()
                    .fill(Color(red: 0.1, green: 0.1, blue: 0.1))
                    .frame(width: blackR * 2, height: blackR * 2)

                // Ring lines
                ForEach(1...10, id: \.self) { ring in
                    let r = targetType.ringFraction(ring: ring) * scoringRadius
                    let isBlack = ring >= targetType.blackFromRing
                    Circle()
                        .strokeBorder(
                            isBlack ? .white.opacity(0.4) : .black.opacity(0.3),
                            lineWidth: isBlack ? 0.6 : 0.8
                        )
                        .frame(width: r * 2, height: r * 2)
                }

                // Ring numbers
                ForEach(1...9, id: \.self) { ring in
                    let outerFrac = targetType.ringFraction(ring: ring)
                    let innerFrac = targetType.ringFraction(ring: ring + 1)
                    let midR = ((outerFrac + innerFrac) / 2) * scoringRadius
                    let isBlack = ring >= targetType.blackFromRing
                    let color: Color = isBlack ? .white : .black.opacity(0.5)
                    let fontSize: CGFloat = isBlack ? 9 : 11

                    RingNumber(ring: ring, color: color, fontSize: fontSize)
                        .offset(x: -midR, y: 0)
                    RingNumber(ring: ring, color: color, fontSize: fontSize)
                        .offset(x: midR, y: 0)
                    RingNumber(ring: ring, color: color, fontSize: fontSize)
                        .offset(x: 0, y: -midR)
                    RingNumber(ring: ring, color: color, fontSize: fontSize)
                        .offset(x: 0, y: midR)
                }

                // Mouche
                let moucheR = targetType.moucheFraction * scoringRadius
                if moucheR > 1 {
                    Circle()
                        .strokeBorder(.white.opacity(0.3), lineWidth: 0.5)
                        .frame(width: moucheR * 2, height: moucheR * 2)
                }

                // Center dot
                Circle()
                    .fill(.white.opacity(0.4))
                    .frame(width: 3, height: 3)

                // Shot markers
                ForEach(shots) { shot in
                    ShotMarkerView(
                        shot: shot,
                        isSelected: selectedShotId == shot.id,
                        markerSize: max(CGFloat(targetType.caliberDiameter / targetType.totalDiameter) * scoringRadius * 2, 12),
                        onLongPress: {
                            selectedShotId = shot.id
                            UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
                        }
                    )
                    .offset(
                        x: CGFloat(shot.x) * scoringRadius,
                        y: CGFloat(shot.y) * scoringRadius
                    )
                }
            }
            .frame(width: size, height: size)
            .contentShape(Rectangle())
            .onTapGesture { location in
                handleTap(at: location, center: center, scoringRadius: scoringRadius)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .aspectRatio(1, contentMode: .fit)
    }

    // MARK: - Tap handling

    private func handleTap(at point: CGPoint, center: CGFloat, scoringRadius: CGFloat) {
        let nx = Double((point.x - center) / scoringRadius)
        let ny = Double((point.y - center) / scoringRadius)
        let dist = sqrt(nx * nx + ny * ny)

        // If a shot is selected...
        if let selectedId = selectedShotId {
            // Tap on the selected shot → delete
            if let shot = shots.first(where: { $0.id == selectedId }) {
                let d = sqrt(pow(nx - shot.x, 2) + pow(ny - shot.y, 2))
                if d < 0.03 {
                    withAnimation { shots.removeAll { $0.id == selectedId } }
                    selectedShotId = nil
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    return
                }
            }

            // Tap outside target → deselect
            guard dist <= 1.1 else {
                selectedShotId = nil
                return
            }

            // Tap inside target → move selected shot there
            let ring = targetType.ringValue(normalizedDistance: dist)
            if let idx = shots.firstIndex(where: { $0.id == selectedId }) {
                shots[idx].x = nx
                shots[idx].y = ny
                shots[idx].ring = ring
                selectedShotId = nil
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            return
        }

        // No selection — place new shot
        guard dist <= 1.1 else { return }

        // Don't place on top of existing shot (long-press handles those).
        for shot in shots {
            let d = sqrt(pow(nx - shot.x, 2) + pow(ny - shot.y, 2))
            if d < 0.02 { return }
        }

        let ring = targetType.ringValue(normalizedDistance: dist)
        var shot = PlacedShot(x: nx, y: ny)
        shot.ring = ring
        shots.append(shot)
        UIImpactFeedbackGenerator(style: .rigid).impactOccurred()
    }
}

// MARK: - Subviews

private struct RingNumber: View {
    let ring: Int
    let color: Color
    let fontSize: CGFloat

    var body: some View {
        Text("\(ring)")
            .font(.system(size: fontSize, weight: .semibold))
            .foregroundStyle(color)
    }
}

private struct ShotMarkerView: View {
    let shot: PlacedShot
    let isSelected: Bool
    let markerSize: CGFloat
    let onLongPress: () -> Void

    var body: some View {
        ZStack {
            // Selection ring
            if isSelected {
                Circle()
                    .strokeBorder(.white, lineWidth: 2)
                    .frame(width: markerSize + 6, height: markerSize + 6)
            }

            // Shadow
            Circle()
                .fill(.black.opacity(0.25))
                .frame(width: markerSize, height: markerSize)
                .offset(y: 1)

            // Marker
            Circle()
                .fill(isSelected ? .orange : .red)
                .frame(width: markerSize, height: markerSize)

            // Ring value
            Text("\(shot.ring)")
                .font(.system(size: max(markerSize * 0.4, 8), weight: .bold))
                .foregroundStyle(.white)
        }
        .onLongPressGesture(minimumDuration: 0.4) {
            onLongPress()
        }
    }
}

#Preview {
    struct PreviewWrapper: View {
        @State var shots: [PlacedShot] = []
        var body: some View {
            VStack {
                InteractiveTargetView(targetType: .sportPistol25m, shots: $shots)
                    .padding()
                Text("Treffer: \(shots.count) · Ringe: \(shots.map(\.ring).reduce(0, +))")
                    .font(.headline)
            }
        }
    }
    return PreviewWrapper()
}

import SwiftUI
import UIKit

/// UIScrollView wrapper for native pinch-to-zoom and pan.
///
/// After zoom ends, `contentScaleFactor` is increased so the content
/// re-renders at full resolution — no layout changes, no performance hit.
struct ZoomableContainer<Content: View>: UIViewRepresentable {
    let minScale: CGFloat
    let maxScale: CGFloat
    @ViewBuilder let content: () -> Content

    init(minScale: CGFloat = 1, maxScale: CGFloat = 6, @ViewBuilder content: @escaping () -> Content) {
        self.minScale = minScale
        self.maxScale = maxScale
        self.content = content
    }

    func makeUIView(context: Context) -> UIScrollView {
        let scrollView = UIScrollView()
        scrollView.delegate = context.coordinator
        scrollView.minimumZoomScale = minScale
        scrollView.maximumZoomScale = maxScale
        scrollView.bouncesZoom = true
        scrollView.showsVerticalScrollIndicator = false
        scrollView.showsHorizontalScrollIndicator = false
        scrollView.backgroundColor = .clear

        let hostedView = context.coordinator.hostingController.view!
        hostedView.translatesAutoresizingMaskIntoConstraints = false
        hostedView.backgroundColor = .clear

        scrollView.addSubview(hostedView)
        NSLayoutConstraint.activate([
            hostedView.leadingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.leadingAnchor),
            hostedView.trailingAnchor.constraint(equalTo: scrollView.contentLayoutGuide.trailingAnchor),
            hostedView.topAnchor.constraint(equalTo: scrollView.contentLayoutGuide.topAnchor),
            hostedView.bottomAnchor.constraint(equalTo: scrollView.contentLayoutGuide.bottomAnchor),
            hostedView.widthAnchor.constraint(equalTo: scrollView.frameLayoutGuide.widthAnchor),
            hostedView.heightAnchor.constraint(equalTo: scrollView.frameLayoutGuide.heightAnchor),
        ])

        let doubleTap = UITapGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleDoubleTap(_:))
        )
        doubleTap.numberOfTapsRequired = 2
        scrollView.addGestureRecognizer(doubleTap)

        return scrollView
    }

    func updateUIView(_ scrollView: UIScrollView, context: Context) {
        context.coordinator.hostingController.rootView = content()
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(content: content())
    }

    class Coordinator: NSObject, UIScrollViewDelegate {
        let hostingController: UIHostingController<Content>
        private let screenScale = UIScreen.main.scale

        init(content: Content) {
            self.hostingController = UIHostingController(rootView: content)
            hostingController.view.backgroundColor = .clear
        }

        func viewForZooming(in scrollView: UIScrollView) -> UIView? {
            hostingController.view
        }

        func scrollViewDidZoom(_ scrollView: UIScrollView) {
            centerContent(in: scrollView)
        }

        func scrollViewDidEndZooming(
            _ scrollView: UIScrollView, with view: UIView?, atScale scale: CGFloat
        ) {
            // Increase rendering resolution to match zoom level.
            // This makes text and shapes sharp without layout changes.
            let newScale = min(scale * screenScale, screenScale * 4)
            setScaleRecursively(hostingController.view, scale: newScale)
        }

        @objc func handleDoubleTap(_ recognizer: UITapGestureRecognizer) {
            guard let scrollView = recognizer.view as? UIScrollView else { return }
            if scrollView.zoomScale > scrollView.minimumZoomScale * 1.1 {
                scrollView.setZoomScale(scrollView.minimumZoomScale, animated: true)
            } else {
                let point = recognizer.location(in: scrollView.subviews.first)
                let size: CGFloat = 100
                scrollView.zoom(
                    to: CGRect(x: point.x - size / 2, y: point.y - size / 2, width: size, height: size),
                    animated: true
                )
            }
        }

        private func centerContent(in scrollView: UIScrollView) {
            let bounds = scrollView.bounds.size
            let content = scrollView.contentSize
            let x = max(0, (bounds.width - content.width) / 2)
            let y = max(0, (bounds.height - content.height) / 2)
            scrollView.contentInset = UIEdgeInsets(top: y, left: x, bottom: y, right: x)
        }

        private func setScaleRecursively(_ view: UIView, scale: CGFloat) {
            view.contentScaleFactor = scale
            for sub in view.subviews {
                setScaleRecursively(sub, scale: scale)
            }
        }
    }
}

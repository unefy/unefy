import PhotosUI
import SwiftUI

/// Entry point for the target scanner. User takes a photo or picks from
/// gallery, then the ML model runs and the review UI shows detections.
struct ScannerView: View {
    let competition: Competition
    let session: CompetitionSession
    var onSaved: (() async -> Void)?

    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    @State private var selectedPhoto: PhotosPickerItem?
    @State private var capturedImage: UIImage?
    @State private var showCamera = false
    @State private var showReview = false
    @State private var scanResult: ScanResult?
    @State private var isAnalyzing = false

    private let detector = TargetDetectorService()

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                if let image = capturedImage {
                    // Preview
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 400)
                        .clipShape(RoundedRectangle(cornerRadius: 12))

                    if isAnalyzing {
                        HStack(spacing: 8) {
                            ProgressView()
                            Text("scanner.analyzing")
                        }
                    } else {
                        Button {
                            Task { await analyze(image) }
                        } label: {
                            Label("scanner.analyze", systemImage: "scope")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)

                        Button("scanner.retake") {
                            capturedImage = nil
                            scanResult = nil
                        }
                        .foregroundStyle(.secondary)
                    }
                } else {
                    // No image yet — show capture options.
                    Spacer()

                    Image(systemName: "camera.viewfinder")
                        .font(.system(size: 80))
                        .foregroundStyle(.secondary)

                    Text("scanner.instructions")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)

                    Spacer()

                    VStack(spacing: 12) {
                        Button {
                            showCamera = true
                        } label: {
                            Label("scanner.takePhoto", systemImage: "camera")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)

                        PhotosPicker(
                            selection: $selectedPhoto,
                            matching: .images
                        ) {
                            Label("scanner.choosePhoto", systemImage: "photo.on.rectangle")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.large)
                    }
                }
            }
            .padding()
            .navigationTitle("scanner.title")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("common.cancel") { dismiss() }
                }
            }
            .fullScreenCover(isPresented: $showCamera) {
                CameraView { image in
                    capturedImage = image
                }
            }
            .onChange(of: selectedPhoto) { _, item in
                guard let item else { return }
                Task {
                    if let data = try? await item.loadTransferable(type: Data.self),
                       let image = UIImage(data: data) {
                        capturedImage = image
                    }
                }
            }
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

    private func analyze(_ image: UIImage) async {
        isAnalyzing = true
        defer { isAnalyzing = false }
        do {
            scanResult = try await detector.detect(in: image)
            showReview = true
        } catch {
            // Show error inline.
        }
    }
}

// MARK: - Simple Camera Wrapper

struct CameraView: UIViewControllerRepresentable {
    var onCapture: (UIImage) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onCapture: onCapture) }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onCapture: (UIImage) -> Void
        init(onCapture: @escaping (UIImage) -> Void) { self.onCapture = onCapture }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage {
                onCapture(image)
            }
            picker.dismiss(animated: true)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
        }
    }
}

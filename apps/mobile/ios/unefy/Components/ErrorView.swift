import SwiftUI

struct ErrorView: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        ContentUnavailableView {
            Label("errors.title", systemImage: "exclamationmark.triangle")
        } description: {
            Text(message)
        } actions: {
            Button {
                retry()
            } label: {
                Text("common.retry")
            }
            .buttonStyle(.borderedProminent)
        }
    }
}

import SwiftUI

struct OfflineBanner: View {
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "wifi.slash")
            Text("common.offline")
                .fontWeight(.medium)
            Spacer()
        }
        .font(.footnote)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.orange.opacity(0.15))
        .foregroundStyle(.orange)
    }
}

#Preview {
    OfflineBanner()
}

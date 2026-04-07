import Foundation

/// Converts the ISO-8601 date/datetime strings from the backend into
/// locale-aware display strings. Backend sends:
/// - `YYYY-MM-DD` for pure dates (birthday, joined_at, left_at)
/// - `YYYY-MM-DDTHH:MM:SS[.ffffff][+00:00]` for datetimes (created_at, etc.)
nonisolated enum DateFormatting {
    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        return formatter
    }()

    private nonisolated(unsafe) static let isoDateTimeFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private nonisolated(unsafe) static let fallbackDateTimeFormatter: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    private static let displayDayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .none
        return formatter
    }()

    /// Parse a backend date string (either `YYYY-MM-DD` or full ISO-8601)
    /// and return a localized short date like "5. Apr. 2026".
    static func displayDate(_ raw: String?) -> String? {
        guard let raw, !raw.isEmpty else { return nil }
        let date = parse(raw)
        guard let date else { return raw }
        return displayDayFormatter.string(from: date)
    }

    static func parse(_ raw: String) -> Date? {
        if let date = dayFormatter.date(from: raw) { return date }
        if let date = isoDateTimeFormatter.date(from: raw) { return date }
        if let date = fallbackDateTimeFormatter.date(from: raw) { return date }
        return nil
    }
}

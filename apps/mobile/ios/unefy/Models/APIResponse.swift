import Foundation

nonisolated struct ListResponse<T: Decodable & Sendable>: Decodable, Sendable {
    let data: [T]
    let meta: ListMeta
}

nonisolated struct ListMeta: Decodable, Sendable {
    let total: Int
    let page: Int
    let perPage: Int
    let totalPages: Int
    let statusCounts: [String: Int]?
}

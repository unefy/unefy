import Foundation

/// Typed description of a single API call. Built in `APIClient`.
struct Endpoint: Sendable {
    enum Method: String, Sendable {
        case get = "GET"
        case post = "POST"
        case patch = "PATCH"
        case delete = "DELETE"
    }

    let method: Method
    let path: String
    let query: [URLQueryItem]
    let body: Data?
    let requiresAuth: Bool
}

extension Endpoint {
    static func devLogin(email: String) -> Endpoint {
        let body = try? JSONEncoder.snake.encode(["email": email])
        return Endpoint(
            method: .post,
            path: "/api/v1/auth/mobile/dev/login",
            query: [],
            body: body,
            requiresAuth: false
        )
    }

    static func refresh(refreshToken: String) -> Endpoint {
        let body = try? JSONEncoder.snake.encode(["refresh_token": refreshToken])
        return Endpoint(
            method: .post,
            path: "/api/v1/auth/mobile/refresh",
            query: [],
            body: body,
            requiresAuth: false
        )
    }

    static func logout(refreshToken: String) -> Endpoint {
        let body = try? JSONEncoder.snake.encode(["refresh_token": refreshToken])
        return Endpoint(
            method: .post,
            path: "/api/v1/auth/mobile/logout",
            query: [],
            body: body,
            requiresAuth: true
        )
    }

    static var me: Endpoint {
        Endpoint(
            method: .get,
            path: "/api/v1/auth/me",
            query: [],
            body: nil,
            requiresAuth: true
        )
    }

    static func members(
        page: Int,
        perPage: Int,
        search: String?,
        status: String?
    ) -> Endpoint {
        var items = [
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "per_page", value: "\(perPage)"),
        ]
        if let search, !search.isEmpty {
            items.append(URLQueryItem(name: "search", value: search))
        }
        if let status, !status.isEmpty {
            items.append(URLQueryItem(name: "status", value: status))
        }
        return Endpoint(
            method: .get,
            path: "/api/v1/members",
            query: items,
            body: nil,
            requiresAuth: true
        )
    }

    static func member(id: String) -> Endpoint {
        Endpoint(
            method: .get,
            path: "/api/v1/members/\(id)",
            query: [],
            body: nil,
            requiresAuth: true
        )
    }

    static func createMember(_ data: MemberCreatePayload) -> Endpoint {
        Endpoint(
            method: .post,
            path: "/api/v1/members",
            query: [],
            body: try? JSONEncoder.snake.encode(data),
            requiresAuth: true
        )
    }

    static func updateMember(id: String, data: MemberUpdatePayload) -> Endpoint {
        Endpoint(
            method: .patch,
            path: "/api/v1/members/\(id)",
            query: [],
            body: try? JSONEncoder.snake.encode(data),
            requiresAuth: true
        )
    }

    static func deleteMember(id: String) -> Endpoint {
        Endpoint(
            method: .delete,
            path: "/api/v1/members/\(id)",
            query: [],
            body: nil,
            requiresAuth: true
        )
    }

    // MARK: - Competitions

    static func competitions(page: Int, perPage: Int, type: String? = nil) -> Endpoint {
        var items = [
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "per_page", value: "\(perPage)"),
        ]
        if let type { items.append(URLQueryItem(name: "competition_type", value: type)) }
        return Endpoint(method: .get, path: "/api/v1/competitions", query: items, body: nil, requiresAuth: true)
    }

    static func createCompetition(_ data: CompetitionCreate, clientId: String? = nil) -> Endpoint {
        var payload = data
        // If a client-generated ID is provided, we need to include it in the JSON body.
        // Since CompetitionCreate doesn't have id, we build the body manually.
        var dict: [String: Any] = [
            "name": data.name,
            "competition_type": data.competitionType,
            "start_date": data.startDate,
            "scoring_mode": data.scoringMode,
            "scoring_unit": data.scoringUnit,
        ]
        if let id = clientId { dict["id"] = id }
        if let desc = data.description { dict["description"] = desc }
        if let end = data.endDate { dict["end_date"] = end }
        if let discs = data.disciplines { dict["disciplines"] = discs }
        return Endpoint(method: .post, path: "/api/v1/competitions", query: [], body: try? JSONSerialization.data(withJSONObject: dict), requiresAuth: true)
    }

    static func competition(id: String) -> Endpoint {
        Endpoint(method: .get, path: "/api/v1/competitions/\(id)", query: [], body: nil, requiresAuth: true)
    }

    static func deleteCompetition(id: String) -> Endpoint {
        Endpoint(method: .delete, path: "/api/v1/competitions/\(id)", query: [], body: nil, requiresAuth: true)
    }

    static func scoreboard(competitionId: String, discipline: String? = nil) -> Endpoint {
        var items: [URLQueryItem] = []
        if let discipline { items.append(URLQueryItem(name: "discipline", value: discipline)) }
        return Endpoint(method: .get, path: "/api/v1/competitions/\(competitionId)/scoreboard", query: items, body: nil, requiresAuth: true)
    }

    // MARK: - Sessions

    static func sessions(competitionId: String, page: Int = 1, perPage: Int = 100) -> Endpoint {
        Endpoint(method: .get, path: "/api/v1/competitions/\(competitionId)/sessions", query: [
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "per_page", value: "\(perPage)"),
        ], body: nil, requiresAuth: true)
    }

    static func deleteSession(competitionId: String, sessionId: String) -> Endpoint {
        Endpoint(method: .delete, path: "/api/v1/competitions/\(competitionId)/sessions/\(sessionId)", query: [], body: nil, requiresAuth: true)
    }

    static func createSession(competitionId: String, data: CompetitionSessionCreate, clientId: String? = nil) -> Endpoint {
        var dict: [String: Any] = ["date": data.date]
        if let id = clientId { dict["id"] = id }
        if let name = data.name { dict["name"] = name }
        if let loc = data.location { dict["location"] = loc }
        if let disc = data.discipline { dict["discipline"] = disc }
        return Endpoint(method: .post, path: "/api/v1/competitions/\(competitionId)/sessions", query: [], body: try? JSONSerialization.data(withJSONObject: dict), requiresAuth: true)
    }

    // MARK: - Entries

    static func entries(competitionId: String, sessionId: String, page: Int = 1, perPage: Int = 500) -> Endpoint {
        Endpoint(method: .get, path: "/api/v1/competitions/\(competitionId)/sessions/\(sessionId)/entries", query: [
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "per_page", value: "\(perPage)"),
        ], body: nil, requiresAuth: true)
    }

    static func deleteEntry(competitionId: String, sessionId: String, entryId: String) -> Endpoint {
        Endpoint(method: .delete, path: "/api/v1/competitions/\(competitionId)/sessions/\(sessionId)/entries/\(entryId)", query: [], body: nil, requiresAuth: true)
    }

    static func createEntry(competitionId: String, sessionId: String, payload: EntryCreatePayload) -> Endpoint {
        Endpoint(method: .post, path: "/api/v1/competitions/\(competitionId)/sessions/\(sessionId)/entries", query: [], body: try? JSONEncoder.snake.encode(payload), requiresAuth: true)
    }
}

import Foundation

@MainActor
struct CompetitionRepository {
    let apiClient: APIClient

    func list(page: Int, perPage: Int, type: String? = nil) async throws -> ListResponse<Competition> {
        try await apiClient.requestRaw(.competitions(page: page, perPage: perPage, type: type))
    }

    func create(_ data: CompetitionCreate) async throws -> Competition {
        try await apiClient.request(.createCompetition(data))
    }

    func sessions(competitionId: String) async throws -> ListResponse<CompetitionSession> {
        try await apiClient.requestRaw(.sessions(competitionId: competitionId))
    }

    func createSession(competitionId: String, data: CompetitionSessionCreate) async throws -> CompetitionSession {
        try await apiClient.request(.createSession(competitionId: competitionId, data: data))
    }

    func entries(competitionId: String, sessionId: String) async throws -> ListResponse<Entry> {
        try await apiClient.requestRaw(.entries(competitionId: competitionId, sessionId: sessionId))
    }

    func scoreboard(competitionId: String, discipline: String? = nil) async throws -> ScoreboardResponse {
        try await apiClient.requestRaw(.scoreboard(competitionId: competitionId, discipline: discipline))
    }
}

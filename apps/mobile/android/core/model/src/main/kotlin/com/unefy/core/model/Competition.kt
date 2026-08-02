package com.unefy.core.model

/**
 * A competition. Sport-agnostic on purpose: the scoring unit and mode come from
 * the backend, so a shooting club counts rings and another club counts whatever
 * it counts without the app knowing the difference.
 */
data class Competition(
    val id: String,
    val name: String,
    val description: String?,
    val type: String?,
    val startDate: String,
    val endDate: String?,
    val scoringUnit: String,
    val scoringMode: String,
    val disciplines: List<String>,
) {
    /** True when higher scores win, which decides how a ranking reads. */
    val highestWins: Boolean get() = scoringMode == "highest_wins"
}

/**
 * A ranking over all sessions of a competition.
 *
 * [unit] travels with the rows rather than being assumed: "1040" means nothing
 * without knowing it is rings.
 */
data class Scoreboard(
    val unit: String,
    val highestWins: Boolean,
    val rows: List<ScoreboardRow>,
)

data class ScoreboardRow(
    val rank: Int,
    val memberId: String,
    val memberName: String,
    val totalScore: Double,
    val bestScore: Double,
    val averageScore: Double,
    val entryCount: Int,
)

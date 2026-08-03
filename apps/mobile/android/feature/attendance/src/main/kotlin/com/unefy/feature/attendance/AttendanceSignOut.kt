package com.unefy.feature.attendance

import com.unefy.core.auth.SignOutTask
import com.unefy.core.database.CachedMemberDao
import com.unefy.core.database.CachedSessionDao
import com.unefy.core.database.CachedSessionRecordDao
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Drops everything attendance keeps about the account that just left.
 *
 * The seed is the reason this exists. It is a member's own credential — anyone
 * holding it can produce that member's codes for a day — and leaving it behind
 * meant the next person to sign in on this phone would hand out somebody else's
 * code and be checked in as them.
 *
 * The read caches go with it: a member list and an attendance list belong to
 * the club the previous account was in, and showing them to the next one is a
 * small leak with no upside.
 *
 * The pending check-in queue is deliberately kept. It holds check-ins that
 * exist nowhere else, and discarding evidence because somebody signed out is
 * the one thing this feature must never do. They sync under whoever signs in
 * next, which is not ideal — `verified_by_user_id` then names the wrong
 * supervisor — and is noted in docs/plans/attendance-and-shooting-proof.md
 * rather than silently accepted as correct.
 */
@Singleton
class AttendanceSignOut @Inject constructor(
    private val seedStore: SeedStore,
    private val members: CachedMemberDao,
    private val sessions: CachedSessionDao,
    private val records: CachedSessionRecordDao,
) : SignOutTask {

    override suspend fun onSignOut() {
        seedStore.clear()
        // Records before sessions: reading the session list to find the
        // records would have come up empty right after clearing it.
        records.deleteAll()
        sessions.retainOnly(emptyList())
        members.retainOnly(emptyList())
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class AttendanceSignOutModule {
    @Binds
    @IntoSet
    abstract fun bindAttendanceSignOut(impl: AttendanceSignOut): SignOutTask
}

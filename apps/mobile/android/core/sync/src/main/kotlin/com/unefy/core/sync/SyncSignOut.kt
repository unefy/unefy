package com.unefy.core.sync

import com.unefy.core.auth.SignOutTask
import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncTransaction
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Empties the mirror when an account leaves the phone.
 *
 * Two failures if this is missing, and the second is the quiet one:
 *
 * 1. The next person to sign in sees the previous club's member list — names,
 *    addresses, birthdays — until their first sync finishes, and everyone the
 *    previous club had who the new one does not, forever.
 * 2. The cursor stays behind. A cursor is a position in *one club's* change feed,
 *    so handing it back under a different account makes the server reject it —
 *    recoverable, since a rejected cursor triggers a re-bootstrap, but it means
 *    the first sync of every new session does a full re-read for no reason.
 *
 * Here rather than in each feature, and driven off the registered collections, so
 * a feature added later is covered without anyone remembering to cover it. The
 * precedent is `AttendanceSignOut`; the difference is that this one cannot be
 * forgotten per feature.
 *
 * Unlike the check-in queue, none of this is worth keeping: every row can be
 * fetched again, and a queued check-in cannot.
 */
@Singleton
class SyncSignOut @Inject constructor(
    private val collections: Set<@JvmSuppressWildcards SyncCollection>,
    private val cursors: SyncCursorDao,
    private val coordinator: SyncCoordinator,
    private val transaction: SyncTransaction,
) : SignOutTask {

    /**
     * Both in one transaction, because either order fails on its own if interrupted
     * and both failures are silent:
     *
     * - Rows gone, cursor kept, and the same account signs back into the same club:
     *   the cursor is still valid, so the next sync is a *delta* and the mirror
     *   stays nearly empty until the cursor ages out a fortnight later.
     * - Cursor gone, rows kept: the next sync is a bootstrap stamping generation 1,
     *   and its sweep drops nothing, so the previous club's members stay on the
     *   phone for good.
     */
    override suspend fun onSignOut() {
        transaction.immediate {
            collections.forEach { it.clear() }
            cursors.deleteAll()
        }
        coordinator.forgetStatuses()
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class SyncSignOutModule {
    @Binds
    @IntoSet
    abstract fun bindSyncSignOut(impl: SyncSignOut): SignOutTask
}

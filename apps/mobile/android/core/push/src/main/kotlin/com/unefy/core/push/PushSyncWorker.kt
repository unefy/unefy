package com.unefy.core.push

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.unefy.core.sync.SETTLE_DELAY_MS
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.util.concurrent.TimeUnit

/**
 * The drain a wake-up asks for, delayed past the server's safety lag.
 *
 * The lag lesson from the SSE path repeats here exactly: the wake-up arrives
 * right after the commit, but the sync endpoints withhold rows for five
 * seconds, so an
 * immediate drain returns nothing, stores its cursor and reports success — and
 * the change never arrives. On the SSE path the answer is two drains because
 * somebody is watching; here nobody is, so the immediate one is dropped and
 * the delay does the whole job. `setInitialDelay` survives process death,
 * which a delayed coroutine would not.
 *
 * Every registered collection is drained rather than the one the message
 * names: wake-ups are coalesced per club on the server, so the named entity is
 * merely the first of a possible burst — and a drain of an unchanged
 * collection costs one small request.
 */
@HiltWorker
class PushSyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted parameters: WorkerParameters,
    private val drain: WakeupDrain,
) : CoroutineWorker(context, parameters) {

    override suspend fun doWork(): Result {
        drain.drainAll()
        // Always success: a failed drain is this wake-up's loss, not a debt.
        // The next change pushes again, and opening the app syncs anyway.
        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "push-wakeup-sync"

        /** Call from the messaging service. Cheap and idempotent. */
        fun enqueue(context: Context) {
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                // KEEP: a drain already waiting will see whatever this wake-up
                // announced — it syncs everything either way.
                ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<PushSyncWorker>()
                    .setInitialDelay(SETTLE_DELAY_MS, TimeUnit.MILLISECONDS)
                    .setConstraints(
                        Constraints.Builder()
                            .setRequiredNetworkType(NetworkType.CONNECTED)
                            .build(),
                    )
                    .build(),
            )
        }
    }
}

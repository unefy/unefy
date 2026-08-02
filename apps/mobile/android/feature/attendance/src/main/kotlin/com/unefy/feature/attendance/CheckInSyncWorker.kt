package com.unefy.feature.attendance

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Drains the check-in queue as soon as there is a connection, app or no app.
 *
 * The gap this closes: syncing only when the scanner is opened means a
 * supervisor who pockets their phone at the end of the evening leaves the
 * evening's check-ins sitting on it. WorkManager keeps the job across process
 * death and reboots and starts it the moment the network constraint is met, so
 * the queue drains on the drive home rather than at the next training session.
 *
 * Enqueued whenever something is buffered, as unique work — one pending drain
 * is enough however many rows went in.
 */
@HiltWorker
class CheckInSyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted parameters: WorkerParameters,
    private val queue: CheckInQueue,
) : CoroutineWorker(context, parameters) {

    override suspend fun doWork(): Result {
        queue.sync()

        // Retry while anything is left. Some rows are refusals the server will
        // never accept, so this would otherwise back off forever on work that
        // cannot succeed — but a row still here after a drain is more likely to
        // be one the connection dropped on, and WorkManager's backoff is
        // exponential rather than a busy loop.
        return if (queue.isEmpty()) Result.success() else Result.retry()
    }

    companion object {
        private const val WORK_NAME = "attendance-check-in-sync"

        /** Call after buffering. Cheap and idempotent — the work is unique. */
        fun enqueue(context: Context) {
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                // KEEP, not REPLACE: a drain already waiting will pick up
                // whatever was added since, and replacing it would restart the
                // backoff each time another person is scanned.
                ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<CheckInSyncWorker>()
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

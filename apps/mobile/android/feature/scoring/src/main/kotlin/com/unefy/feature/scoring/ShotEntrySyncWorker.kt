package com.unefy.feature.scoring

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
import kotlinx.coroutines.flow.first

/**
 * Sends recorded series once there is a connection, app open or not.
 *
 * The same reasoning as the check-in queue: a range is a basement, and syncing
 * only while the recording screen happens to be open would leave an evening's
 * results on the phone until somebody thinks to open the app again. WorkManager
 * survives process death and reboots, so the queue drains on the drive home.
 *
 * Retries are safe by construction — every series carries a client-generated id
 * that the server treats as an idempotency key, so a replay after a half-failed
 * send is the same series, not a second one.
 */
@HiltWorker
class ShotEntrySyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted parameters: WorkerParameters,
    private val repository: ScoringRepository,
) : CoroutineWorker(context, parameters) {

    override suspend fun doWork(): Result {
        repository.drainQueue()
        val remaining = repository.pendingCount().first()
        return if (remaining == 0) Result.success() else Result.retry()
    }

    companion object {
        private const val WORK_NAME = "scoring-shot-entry-sync"

        /** Call after recording. Cheap and idempotent — the work is unique. */
        fun enqueue(context: Context) {
            WorkManager.getInstance(context).enqueueUniqueWork(
                WORK_NAME,
                // KEEP rather than REPLACE: a drain already waiting picks up
                // whatever was queued since, and replacing it would restart the
                // backoff every time another series is saved.
                ExistingWorkPolicy.KEEP,
                OneTimeWorkRequestBuilder<ShotEntrySyncWorker>()
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

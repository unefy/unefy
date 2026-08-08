package com.unefy.feature.attendance

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.util.concurrent.TimeUnit

/**
 * Fetches a fresh check-in seed on a schedule, app open or not.
 *
 * The only job in this app that runs because time passed rather than because
 * something happened, and the seed is the one thing that needs it: it goes
 * stale on the calendar, not on any event the server could announce. A member
 * who does not open the app for days would otherwise arrive at the range — the
 * one place with no signal — holding a code the server has stopped accepting.
 *
 * Twelve hours rather than twenty-four, because the interval is a floor and not
 * a promise. Under Doze and app-standby a rarely-used app's periodic work is
 * deferred, batched with whatever else the system is running, and on some
 * vendors' battery managers deferred further still; asking twice per period is
 * what makes one landing inside a period likely rather than hoped for. Two
 * requests a day, and only when the stored seed has actually run out.
 */
@HiltWorker
class SeedRefreshWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted parameters: WorkerParameters,
    private val keeper: SeedKeeper,
) : CoroutineWorker(context, parameters) {

    override suspend fun doWork(): Result {
        keeper.refreshIfExpired()
        // Always success. A missed refresh is this run's loss and not a debt:
        // the next period comes around, and the app refreshes on its own the
        // moment somebody opens it with a connection.
        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "attendance-seed-refresh"
        private const val INTERVAL_HOURS = 12L

        fun schedule(context: Context) {
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                // KEEP: the request is identical every time, so there is
                // nothing an update could carry. This call is only ever "make
                // sure it exists", which is what KEEP says.
                ExistingPeriodicWorkPolicy.KEEP,
                PeriodicWorkRequestBuilder<SeedRefreshWorker>(INTERVAL_HOURS, TimeUnit.HOURS)
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

package com.unefy.app

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.unefy.feature.attendance.CheckInSyncWorker
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

/**
 * Also the WorkManager configuration host.
 *
 * Workers are constructed by WorkManager, not by Hilt, so one that needs
 * injected dependencies — the check-in sync worker needs the queue — only works
 * if WorkManager is told to build them through Hilt's factory. That means
 * configuring it here and turning off its default automatic initialiser in the
 * manifest, otherwise it initialises itself first and never sees this.
 */
@HiltAndroidApp
class UnefyApplication : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder().setWorkerFactory(workerFactory).build()

    override fun onCreate() {
        super.onCreate()

        // Unconditionally, because a force stop — which several OEM launchers
        // make a one-tap affair — cancels scheduled work, and the check-ins it
        // would have sent exist on this phone and nowhere else. Unique work, so
        // this cannot pile up, and the worker exits immediately when the queue
        // is empty.
        CheckInSyncWorker.enqueue(this)
    }
}

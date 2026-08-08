package com.unefy.feature.attendance

import com.unefy.core.push.BackgroundSyncObserver
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Rides along on a push wake-up to top up the seed.
 *
 * The cheapest refresh there is: the device is already awake, already has a
 * connection the system considered good enough to deliver on, and has already
 * proved it has a session. Nothing here schedules anything of its own — a club
 * with any activity at all keeps its members' seeds current for free, and the
 * periodic worker exists for the phones where no wake-up ever arrives.
 *
 * In `afterDrain` rather than `beforeDrain`, which is for observers snapshotting
 * what their diff will compare against. Nothing here needs the drain's result;
 * it just has no business delaying it.
 */
@Singleton
class SeedWakeupObserver @Inject constructor(
    private val keeper: SeedKeeper,
) : BackgroundSyncObserver {

    override suspend fun beforeDrain() = Unit

    override suspend fun afterDrain() = keeper.refreshIfExpired()
}

@Module
@InstallIn(SingletonComponent::class)
abstract class SeedWakeupObserverModule {
    @Binds
    @IntoSet
    abstract fun bindSeedWakeupObserver(impl: SeedWakeupObserver): BackgroundSyncObserver
}

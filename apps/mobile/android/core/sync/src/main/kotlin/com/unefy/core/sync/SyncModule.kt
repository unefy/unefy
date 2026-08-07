package com.unefy.core.sync

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.Multibinds

/**
 * Declares the collection set, so an app with none still builds.
 *
 * Without this, `Set<SyncCollection>` is only a valid injection point once some
 * module contributes to it — and a build variant or test that leaves every feature
 * out would fail to compile for a reason that reads as unrelated.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class SyncModule {
    @Multibinds
    abstract fun collections(): Set<SyncCollection>

    /** Same reason as [collections]: an app with no writable feature must build. */
    @Multibinds
    abstract fun writeHandlers(): Set<PendingWriteHandler>

    @Binds
    abstract fun bindWriteQueue(impl: DefaultWriteQueue): WriteQueue

    @Binds
    abstract fun bindActiveTenant(impl: SessionActiveTenant): ActiveTenant

    @Binds
    abstract fun bindSyncCoordinator(impl: DefaultSyncCoordinator): SyncCoordinator

    @Binds
    abstract fun bindSyncEngine(impl: DeltaSyncEngine): SyncEngine

    @Binds
    abstract fun bindChangeStream(impl: SseChangeStream): ChangeStream

    @Binds
    abstract fun bindConnectivityMonitor(impl: AndroidConnectivityMonitor): ConnectivityMonitor
}

package com.unefy.core.database

import androidx.room.withTransaction
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Runs a block as one database transaction.
 *
 * An interface so the sync engine can demand atomicity without depending on Room.
 * Two things fall out of that: `core:sync` stays free of a persistence framework,
 * and its tests can substitute a transactor that simply calls the block — which
 * is how the engine's control flow is testable on the JVM at all.
 *
 * What it is for: a page of changes and the cursor that accounts for it must land
 * together or not at all. See [SyncCursorEntity].
 */
interface SyncTransaction {
    suspend fun <T> immediate(block: suspend () -> T): T
}

@Singleton
class RoomSyncTransaction @Inject constructor(
    private val database: UnefyDatabase,
) : SyncTransaction {
    override suspend fun <T> immediate(block: suspend () -> T): T =
        database.withTransaction { block() }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class SyncTransactionModule {
    @Binds
    abstract fun bindSyncTransaction(impl: RoomSyncTransaction): SyncTransaction
}

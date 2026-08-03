package com.unefy.feature.events

import com.unefy.core.database.SyncCursorDao
import com.unefy.core.database.SyncedEventDao
import com.unefy.core.model.Event
import com.unefy.core.push.BackgroundSyncObserver
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import dagger.multibindings.IntoSet
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.first

/**
 * What the user actually sees. An interface so the diff logic above it is a
 * JVM test away — the Android implementation is a thin notification builder.
 */
fun interface NewEventAlerts {
    fun show(events: List<Event>)
}

/**
 * Turns a background drain into "Neuer Termin" notifications.
 *
 * The content never travels: the wake-up carried ids, the drain pulled the
 * rows through the role-checked sync endpoint, and this diff renders locally
 * from the mirror. Google relayed nothing but "something changed".
 *
 * Three guards, each against a concrete way this would misfire:
 *
 * - **Bootstrap.** The first drain after sign-in delivers the whole calendar;
 *   announcing every existing event as new would be the worst first
 *   impression a notification can make. Only a mirror that was already
 *   complete *before* the drain can tell new from backfilled.
 * - **Upcoming only.** A backdated or historical event is calendar hygiene,
 *   not news.
 * - **Foreground never sees this.** The observer only runs on the background
 *   worker's drain — in the foreground the list itself shows the change.
 */
@Singleton
class EventsNotifier @Inject constructor(
    private val events: SyncedEventDao,
    private val cursors: SyncCursorDao,
    private val alerts: NewEventAlerts,
    private val clock: EventsClock,
) : BackgroundSyncObserver {

    private var knownIds: Set<String> = emptySet()
    private var mirrorWasComplete = false

    override suspend fun beforeDrain() {
        mirrorWasComplete =
            cursors.get(EventSyncCollection.COLLECTION)?.bootstrapComplete == true
        knownIds = if (mirrorWasComplete) {
            events.all().first().map { it.id }.toSet()
        } else {
            emptySet()
        }
    }

    override suspend fun afterDrain() {
        if (!mirrorWasComplete) return

        val now = clock.nowIso()
        val fresh = events.all().first()
            .filter { it.id !in knownIds && it.startsAt > now }
            .map { it.toDomain() }

        if (fresh.isNotEmpty()) alerts.show(fresh)
    }
}

@Module
@InstallIn(SingletonComponent::class)
abstract class EventsNotifierModule {
    @Binds
    @IntoSet
    abstract fun bindEventsNotifier(impl: EventsNotifier): BackgroundSyncObserver

    @Binds
    abstract fun bindNewEventAlerts(impl: AndroidNewEventAlerts): NewEventAlerts
}

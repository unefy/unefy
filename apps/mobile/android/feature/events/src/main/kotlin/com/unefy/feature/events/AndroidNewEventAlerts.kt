package com.unefy.feature.events

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.unefy.core.designsystem.theme.UnefyFormat
import com.unefy.core.model.Event
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The Android half of [NewEventAlerts]: one channel, one notification per new
 * event, a single summary once a batch would turn into a stack. Tapping opens
 * the app; the events list is one tab away and already up to date, because
 * the drain ran before this did.
 *
 * Quietly does nothing without permission: `POST_NOTIFICATIONS` is asked for
 * once at startup (see MainActivity), and a refusal means the user said no —
 * the sync itself is unaffected.
 */
@Singleton
class AndroidNewEventAlerts @Inject constructor(
    @ApplicationContext private val context: Context,
) : NewEventAlerts {

    override fun show(events: List<Event>) {
        // Inline rather than a helper, so lint's flow analysis sees the gate
        // in front of every notify() below.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }
        ensureChannel()

        val manager = NotificationManagerCompat.from(context)
        if (events.size > MAX_INDIVIDUAL) {
            manager.notify(SUMMARY_ID, summary(events.size))
            return
        }
        events.forEach { event ->
            manager.notify(event.id.hashCode(), notification(event))
        }
    }

    private fun notification(event: Event) = builder()
        .setContentTitle(context.getString(R.string.events_notification_new))
        .setContentText(
            listOfNotNull(
                if (event.allDay) UnefyFormat.date(event.startsAt) else UnefyFormat.dateTime(event.startsAt),
                event.title,
            ).joinToString(" – "),
        )
        .build()

    private fun summary(count: Int) = builder()
        .setContentTitle(context.getString(R.string.events_notification_new_many, count))
        .setContentText(context.getString(R.string.events_notification_new_many_body))
        .build()

    private fun builder(): NotificationCompat.Builder =
        NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification_event)
            .setAutoCancel(true)
            .setContentIntent(openApp())

    private fun openApp(): PendingIntent? {
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName)
            ?: return null
        return PendingIntent.getActivity(
            context,
            0,
            launch,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun ensureChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.events_notification_channel),
            NotificationManager.IMPORTANCE_DEFAULT,
        )
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private companion object {
        const val CHANNEL_ID = "events"
        val SUMMARY_ID = "events-summary".hashCode()

        /** Past this many at once, a stack of cards says less than one line. */
        const val MAX_INDIVIDUAL = 3
    }
}

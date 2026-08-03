package com.unefy.core.push

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * The doorbell's back door: what rings when the app is not looking.
 *
 * A wake-up is a silent data message carrying ids and nothing else, so there
 * is no notification to show and no permission to ask for. The payload is not
 * even parsed: the worker drains every registered collection anyway, because
 * server-side coalescing means the named entity is only the first of a
 * possible burst. A message therefore does exactly one thing — enqueue the
 * delayed drain. Sign-in is checked in the worker, authorisation on every
 * sync request; a wake-up carries neither and never deletes anything.
 *
 * Foreground messages land here too and enqueue the same worker. That is
 * deliberate redundancy, not a conflict: in the foreground the SSE stream
 * already delivered the hint and synced, so the worker's later drain finds
 * everything already applied and costs a few no-op requests.
 */
@AndroidEntryPoint
class UnefyMessagingService : FirebaseMessagingService() {

    @Inject
    lateinit var registrar: PushRegistrar

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onMessageReceived(message: RemoteMessage) {
        PushSyncWorker.enqueue(applicationContext)
    }

    override fun onNewToken(token: String) {
        // The old token is dead the moment this fires; re-registering moves the
        // server row to the new one. Signed out, the registrar does nothing and
        // the token is picked up at the next sign-in.
        scope.launch { registrar.register(token) }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }
}

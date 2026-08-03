package com.unefy.core.sync

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import androidx.core.content.getSystemService
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.distinctUntilChanged

/**
 * Whether the device currently has a usable network.
 *
 * The reason it exists: without it, the only thing that triggers a sync is the
 * user doing something. Coming out of a basement or off a plane would leave the
 * app showing whatever it had, indefinitely, with no gesture to fix it — and the
 * change stream cannot help, because reconnecting it is exactly what needs
 * triggering.
 *
 * An interface because the implementation needs a `Context` and the coordinator's
 * rules are worth testing without one — the same reason `CheckInQueue` takes its
 * scheduler as an interface.
 */
fun interface ConnectivityMonitor {
    fun isOnline(): Flow<Boolean>
}

/**
 * `NET_CAPABILITY_VALIDATED` rather than merely "connected": a clubhouse Wi-Fi
 * behind a captive portal is connected and routes nothing, and treating it as
 * online means a burst of requests that all fail.
 */
@Singleton
class AndroidConnectivityMonitor @Inject constructor(
    @ApplicationContext private val context: Context,
) : ConnectivityMonitor {

    override fun isOnline(): Flow<Boolean> = channelFlow {
        val manager = context.getSystemService<ConnectivityManager>()
        if (manager == null) {
            // No ConnectivityManager should be impossible. Claiming "offline"
            // would disable syncing altogether, so the safer wrong answer is
            // "online" — requests then fail on their own and report properly.
            send(true)
            awaitClose {}
            return@channelFlow
        }

        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onCapabilitiesChanged(
                network: Network,
                capabilities: NetworkCapabilities,
            ) {
                trySend(capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED))
            }

            override fun onLost(network: Network) {
                trySend(false)
            }

            override fun onUnavailable() {
                trySend(false)
            }
        }

        // The current state, before any callback fires. Without it a device that
        // is already online when the app starts would wait for a network change
        // that may never come.
        send(
            manager.activeNetwork
                ?.let(manager::getNetworkCapabilities)
                ?.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) == true,
        )

        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        manager.registerNetworkCallback(request, callback)

        awaitClose { manager.unregisterNetworkCallback(callback) }
    }.distinctUntilChanged()
}

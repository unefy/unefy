package com.unefy.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.unefy.core.sync.SyncCoordinator
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.launch

/**
 * Single activity. Navigation 3 owns the back stack from here down; this class
 * stays thin by design — see the module rules in apps/mobile/CLAUDE.md.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var syncCoordinator: SyncCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Edge-to-edge is the default on current targetSdk, not an opt-in.
        enableEdgeToEdge()

        // The change stream and the syncs it triggers live exactly as long as
        // somebody is looking at the app.
        //
        // `repeatOnLifecycle` rather than `ProcessLifecycleOwner`: this app has one
        // activity, so the two mean the same thing here, and this needs no extra
        // dependency. If a second entry point ever appears, lifecycle-process is
        // the upgrade.
        //
        // Stopping in the background is honest rather than lazy. Android kills
        // long-lived sockets there anyway, so a stream held open would be a stream
        // that silently is not delivering. Background freshness needs push, which
        // is FCM and a later phase; on return from the background a delta sync
        // costs one round trip and feels immediate.
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                syncCoordinator.run()
            }
        }

        setContent { UnefyRoot() }
    }
}

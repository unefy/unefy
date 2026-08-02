package com.unefy.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint

/**
 * Single activity. Navigation 3 owns the back stack from here down; this class
 * stays thin by design — see the module rules in apps/mobile/CLAUDE.md.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Edge-to-edge is the default on current targetSdk, not an opt-in.
        enableEdgeToEdge()

        setContent { UnefyRoot() }
    }
}

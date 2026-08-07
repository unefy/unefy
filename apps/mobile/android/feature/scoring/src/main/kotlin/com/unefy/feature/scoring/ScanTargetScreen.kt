package com.unefy.feature.scoring

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.compose.CameraXViewfinder
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.layout.ContentScale
import com.unefy.core.designsystem.component.TargetCanvas
import com.unefy.core.model.scoring.ShotSeriesDraft
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyDetailScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import com.unefy.core.model.scoring.TargetGeometry

/**
 * Photograph a target, and show what was recognised.
 *
 * While the viewfinder is live there is a circle to place the target inside.
 * That guide is not decoration: the backstop behind a target is itself full of
 * dark bullet holes, and restricting the search to what the user framed is what
 * keeps the detection off it (ml/NOTES-real-targets.md).
 *
 * Once a photo is taken the located mark is outlined and the squared-up crop is
 * shown. Nothing is uploaded — recognition is entirely on-device.
 */
@Composable
fun ScanTargetRoute(
    geometry: TargetGeometry,
    onBack: () -> Unit,
    onAccept: (TargetPhoto) -> Unit,
    viewModel: ScanTargetViewModel = hiltViewModel(),
) {
    LaunchedEffect(geometry) { viewModel.setGeometry(geometry) }
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    ScanTargetScreen(
        state = state,
        onBack = onBack,
        onCapture = viewModel::capture,
        onRetake = viewModel::retake,
        onAccept = { state.photo?.let(onAccept) },
        bindCamera = viewModel::bindToCamera,
    )
}

@Composable
fun ScanTargetScreen(
    state: ScanTargetUiState,
    onBack: () -> Unit = {},
    onCapture: () -> Unit = {},
    onRetake: () -> Unit = {},
    onAccept: () -> Unit = {},
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit =
        { _, _ -> },
) {
    val context = LocalContext.current
    var granted by rememberSaveable {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    val requestPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted = it }

    UnefyDetailScaffold(
        collapsedTitle = stringResource(R.string.scan_title),
        onBack = onBack,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = UnefySpacing.screen),
            verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm),
        ) {
            when {
                !granted -> {
                    UnefyCenteredState(
                        title = stringResource(R.string.scan_permission_title),
                        body = stringResource(R.string.scan_permission_body),
                        action = {
                            Button(onClick = { requestPermission.launch(Manifest.permission.CAMERA) }) {
                                Text(stringResource(R.string.scan_permission_grant))
                            }
                        },
                    )
                }

                state.photo != null ->
                    ReviewPhoto(state.photo, state.geometry, onRetake, onAccept)

                else -> {
                    val frozen = state.captured
                    if (frozen != null) {
                        // The shot is taken: show it standing still. A live
                        // viewfinder here reads as "keep holding the phone on
                        // the target", which is exactly what nobody has to do
                        // any more.
                        Image(
                            bitmap = frozen.asImageBitmap(),
                            contentDescription = stringResource(R.string.scan_result_description),
                            modifier = Modifier.fillMaxWidth().aspectRatio(3f / 4f),
                            contentScale = ContentScale.Crop,
                        )
                    } else {
                        Viewfinder(state, bindCamera)
                    }

                    if (state.notFound) {
                        Text(
                            text = stringResource(R.string.scan_not_found),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                    Text(
                        text = stringResource(
                            when {
                                state.capturing -> R.string.scan_capturing
                                state.sighting == null -> R.string.scan_searching
                                !state.sighting.quad.closeEnough -> R.string.scan_closer
                                else -> R.string.scan_holding
                            },
                        ),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    // The user takes the picture. The detection only advises.
                    Button(
                        onClick = onCapture,
                        enabled = !state.capturing,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            stringResource(
                                if (state.capturing) R.string.scan_capturing
                                else R.string.scan_capture,
                            ),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun Viewfinder(
    state: ScanTargetUiState,
    bindCamera: suspend (android.content.Context, androidx.lifecycle.LifecycleOwner) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) { bindCamera(context.applicationContext, lifecycleOwner) }

    // A buzz the moment it locks on, so the phone can be held over a target on a
    // bench without watching the screen.
    val haptics = LocalHapticFeedback.current
    LaunchedEffect(state.locked) {
        if (state.locked) haptics.performHapticFeedback(HapticFeedbackType.LongPress)
    }

    Box(
        modifier = Modifier.fillMaxWidth().aspectRatio(1f),
        contentAlignment = Alignment.Center,
    ) {
        state.surfaceRequest?.let { request ->
            CameraXViewfinder(surfaceRequest = request, modifier = Modifier.fillMaxSize())
        }

        // The sheet the app is actually seeing, outlined. Not a fixed ring to
        // aim into — that was the awkward part — and not the aiming mark, whose
        // ellipse was too unstable at preview resolution to be anything but
        // confusing. A rectangle around the paper says plainly "I have it", and
        // it turns green when the shot is worth taking.
        Canvas(Modifier.fillMaxSize()) {
            val sighting = state.sighting ?: return@Canvas

            // CameraXViewfinder fills its box and crops the overflow — it does
            // not letterbox. Mapping as though it letterboxed (minOf) drew the
            // outline too small and off to one side.
            val scale = maxOf(
                size.width / sighting.frameWidth,
                size.height / sighting.frameHeight,
            )
            val offsetX = (size.width - sighting.frameWidth * scale) / 2f
            val offsetY = (size.height - sighting.frameHeight * scale) / 2f
            fun map(point: Pair<Int, Int>) = Offset(
                offsetX + point.first * scale,
                offsetY + point.second * scale,
            )

            val quad = sighting.quad
            val path = Path().apply {
                val start = map(quad.topLeft)
                moveTo(start.x, start.y)
                listOf(quad.topRight, quad.bottomRight, quad.bottomLeft).forEach {
                    val p = map(it)
                    lineTo(p.x, p.y)
                }
                close()
            }

            // Red until the shot is worth taking, green once it is. The colour
            // is the whole message: it says "I have the target, and close
            // enough" without the user having to interpret an outline.
            drawPath(
                path = path,
                color = if (sighting.usable) Color(0xFF31C36B) else Color(0xFFE0342A),
                style = Stroke(width = 3.dp.toPx()),
            )
        }
    }
}

@Composable
private fun ReviewPhoto(
    photo: TargetPhoto,
    geometry: TargetGeometry,
    onRetake: () -> Unit,
    onAccept: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(UnefySpacing.sm)) {
        // What was found, drawn on the sheet, before the photo is accepted.
        // Standing in front of the target is the cheapest moment to notice that
        // half the shots are missing — a retake costs nothing here and a lot
        // once the series is being entered.
        val found = remember(photo, geometry) {
            photo.hits.foldIndexed(
                ShotSeriesDraft(geometry = geometry, caliberMm = geometry.defaultCaliberMm),
            ) { index, draft, hit -> draft.place("preview-$index", hit.x, hit.y) }
        }
        TargetCanvas(
            geometry = geometry,
            shots = found.shots,
            showRingValues = false,
            photo = photo.rectified.asImageBitmap(),
            zoomable = true,
        )

        // What was found, before the photo is accepted: the shooter is standing
        // in front of the sheet and can still retake it, which is the only
        // moment a wrong count is cheap to fix.
        Text(
            text = if (photo.hits.isEmpty()) {
                stringResource(R.string.scan_hits_none)
            } else {
                pluralStringResource(R.plurals.scan_hits_found, photo.hits.size, photo.hits.size)
            },
            style = MaterialTheme.typography.bodyMedium,
        )

        if (photo.oblique) {
            // The affine rectification drifts once the sheet is badly squashed.
            // Measured over 142 club photos the worst was 0.96 circular, so this
            // should be rare — but it is a warning, not a refusal.
            Text(
                text = stringResource(R.string.scan_oblique),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(UnefySpacing.sm)) {
            Button(onClick = onAccept, modifier = Modifier.fillMaxWidth(0.6f)) {
                Text(stringResource(R.string.scan_use))
            }
            OutlinedButton(onClick = onRetake) {
                Text(stringResource(R.string.scan_retake))
            }
        }
    }
}


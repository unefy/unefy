package com.unefy.feature.scoring

import android.content.Context
import android.graphics.Bitmap
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import android.util.Size
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.SurfaceRequest
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.lifecycle.awaitInstance
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.SheetQuad
import com.unefy.core.model.scoring.TargetGeometrySeed
import com.unefy.core.model.scoring.TargetLocator
import dagger.hilt.android.lifecycle.HiltViewModel
import java.util.concurrent.Executors
import javax.inject.Inject
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ScanTargetUiState(
    val surfaceRequest: SurfaceRequest? = null,
    /** The sheet the preview is seeing right now, for the framing outline. */
    val sighting: Sighting? = null,
    val capturing: Boolean = false,
    /**
     * The shot just taken, shown while it is being analysed.
     *
     * A live viewfinder during the second the analysis takes says "keep
     * holding" — so people do, and then wonder whether it worked. A frozen
     * frame says the photo is in the bag and the phone can come down.
     */
    val captured: Bitmap? = null,
    /** Set once a photo has been taken and analysed. */
    val photo: TargetPhoto? = null,
    /** A photo was taken but no target could be found in it. */
    val notFound: Boolean = false,
    val geometry: TargetGeometry = TargetGeometrySeed.DEFAULT,
) {
    /** The outline is green and the shot is worth taking. */
    val locked: Boolean get() = sighting?.usable == true
}

/**
 * A sheet seen in the viewfinder — the outline, and how settled it is.
 *
 * The frame size travels with it: analysis runs on a small frame in the sensor's
 * own orientation, and the overlay has to scale that onto the preview.
 */
data class Sighting(
    val quad: SheetQuad,
    val frameWidth: Int,
    val frameHeight: Int,
    val stableFrames: Int,
) {
    /**
     * Worth photographing: the sheet fills enough of the frame and has stopped
     * moving. Turns the outline green — it does not fire the shutter. Taking the
     * picture stays a decision, because only the user knows whether this is the
     * target they meant.
     */
    val usable: Boolean get() = quad.closeEnough && stableFrames >= STEADY_FRAMES

    companion object {
        /** Short: this only suppresses flicker while panning, it fires nothing. */
        const val STEADY_FRAMES = 3
    }
}

/**
 * Photographing a target and squaring it up.
 *
 * The camera use cases live here rather than in the composable, following
 * `ScannerViewModel` in feature:attendance: the `SurfaceRequest` travels through
 * the UI state and the screen only renders it. Binding and unbinding must happen
 * on the main thread, which is what the `withContext` in [bindToCamera] is for.
 *
 * The live pass looks for the SHEET, not the aiming mark.
 *
 * An earlier version tracked the mark and was unusable: a small ellipse fitted
 * to a 480x360 preview frame jitters and squashes, so the viewfinder showed a
 * wandering shape and the shutter fired at nothing in particular. The sheet is a
 * large high-contrast rectangle — steady in the same frame, and a quadrilateral
 * cannot deform into nonsense the way an ellipse can. The precise work still
 * happens on the full-resolution still afterwards; this only frames the shot and
 * decides when it is worth taking.
 *
 * Recognition itself is [TargetPhotoAnalyzer] — pure geometry, no model, and no
 * network. Nothing leaves the device.
 */
@HiltViewModel
class ScanTargetViewModel @Inject constructor(
    private val scans: ScanStore,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ScanTargetUiState())
    val uiState: StateFlow<ScanTargetUiState> = _uiState.asStateFlow()

    /** Analysis is CPU-bound over a few million pixels; it must not block the UI. */
    private val analysisDispatcher: CoroutineDispatcher = Dispatchers.Default

    private val captureExecutor = Executors.newSingleThreadExecutor()

    /** One thread: frames are dropped rather than queued, so one is enough. */
    private val analysisExecutor = Executors.newSingleThreadExecutor()

    private val previewUseCase = Preview.Builder().build().apply {
        setSurfaceProvider { request -> _uiState.update { it.copy(surfaceRequest = request) } }
    }

    /**
     * Small on purpose: finding a bright rectangle needs no detail, and a frame
     * at this size costs a few milliseconds. KEEP_ONLY_LATEST drops frames
     * rather than queueing them, so the outline never lags behind the camera.
     */
    private val analysisUseCase = ImageAnalysis.Builder()
        .setResolutionSelector(
            ResolutionSelector.Builder()
                .setResolutionStrategy(
                    ResolutionStrategy(
                        Size(480, 360),
                        ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER,
                    ),
                )
                .build(),
        )
        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
        .build()

    private val captureUseCase = ImageCapture.Builder()
        // The target is a still, flat object under whatever light the range has;
        // quality is worth more than shutter latency here.
        .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
        .build()

    init {
        analysisUseCase.setAnalyzer(analysisExecutor, ::onFrame)
    }

    fun setGeometry(geometry: TargetGeometry) = _uiState.update { it.copy(geometry = geometry) }

    /**
     * One preview frame. Runs on the analysis executor, never the main thread.
     *
     * Closing the frame in a `finally` is not optional: hold one and CameraX
     * starves — no further frames arrive and the preview freezes.
     */
    private fun onFrame(image: ImageProxy) {
        try {
            if (_uiState.value.capturing || _uiState.value.photo != null) return
            // Rotate before analysing, exactly as the still capture does.
            // Analysis frames arrive in the SENSOR's orientation — landscape,
            // while the preview is portrait — so coordinates taken from an
            // unrotated frame land somewhere else entirely on screen. The
            // outline used to sit small and offset for precisely this reason.
            val bitmap = runCatching { image.toBitmap() }.getOrNull()
                ?.rotated(image.imageInfo.rotationDegrees) ?: return
            // The outline is the crop, not the sheet: it is built from the
            // aiming mark exactly as the rectified picture is, so what is drawn
            // on screen is the region the detector will actually be handed.
            // Tracing the sheet's own edge put a green frame around the whole
            // backstop — see TargetFit.cropOutline for why it cannot work in
            // grey.
            val quad = TargetLocator.findCropOutline(
                bitmap.grayscale(),
                bitmap.width,
                bitmap.height,
                _uiState.value.geometry.blackFraction,
            )

            _uiState.update { state ->
                val previous = state.sighting
                val stable = when {
                    quad == null -> 0
                    previous == null -> 1
                    // "The same sheet", not "the same pixels": a hand-held phone
                    // never repeats a position exactly, and demanding it would
                    // mean the shutter never fires.
                    moved(previous.quad, quad, bitmap.width) -> 1
                    else -> previous.stableFrames + 1
                }
                state.copy(
                    sighting = quad?.let {
                        Sighting(it, bitmap.width, bitmap.height, stable)
                    },
                )
            }

        } finally {
            image.close()
        }
    }

    private fun moved(previous: SheetQuad, current: SheetQuad, frameWidth: Int): Boolean {
        val tolerance = frameWidth * 0.05
        val corners = listOf(
            previous.topLeft to current.topLeft,
            previous.topRight to current.topRight,
            previous.bottomRight to current.bottomRight,
            previous.bottomLeft to current.bottomLeft,
        )
        return corners.any { (a, b) ->
            kotlin.math.hypot(
                (a.first - b.first).toDouble(),
                (a.second - b.second).toDouble(),
            ) > tolerance
        }
    }

    suspend fun bindToCamera(context: Context, lifecycleOwner: LifecycleOwner) {
        val provider = ProcessCameraProvider.awaitInstance(context)
        withContext(Dispatchers.Main.immediate) {
            provider.bindToLifecycle(
                lifecycleOwner,
                CameraSelector.DEFAULT_BACK_CAMERA,
                previewUseCase,
                analysisUseCase,
                captureUseCase,
            )
            try {
                awaitCancellation()
            } finally {
                withContext(NonCancellable) { provider.unbindAll() }
            }
        }
    }

    fun capture() {
        if (_uiState.value.capturing) return
        _uiState.update { it.copy(capturing = true, notFound = false) }

        captureUseCase.takePicture(
            captureExecutor,
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val bitmap = runCatching { image.toBitmap() }.getOrNull()
                    val rotation = image.imageInfo.rotationDegrees
                    image.close()
                    if (bitmap == null) {
                        _uiState.update { it.copy(capturing = false, notFound = true) }
                        return
                    }
                    val upright = bitmap.rotated(rotation)
                    _uiState.update { it.copy(captured = upright) }
                    onPhoto(upright)
                }

                override fun onError(exception: ImageCaptureException) {
                    _uiState.update { it.copy(capturing = false, notFound = true) }
                }
            },
        )
    }

    private fun onPhoto(bitmap: Bitmap) {
        viewModelScope.launch {
            val result = withContext(analysisDispatcher) {
                scans.write(ScanStore.Kind.PHOTO, bitmap)
                TargetPhotoAnalyzer.analyze(bitmap, _uiState.value.geometry)
                    ?.also { scans.write(ScanStore.Kind.RECTIFIED, it.rectified) }
            }
            _uiState.update {
                it.copy(
                    capturing = false,
                    captured = null,
                    photo = result,
                    notFound = result == null,
                )
            }
        }
    }

    /** Discard the photo and go back to the viewfinder. */
    fun retake() = _uiState.update {
        it.copy(photo = null, captured = null, notFound = false, sighting = null)
    }

    override fun onCleared() {
        analysisUseCase.clearAnalyzer()
        analysisExecutor.shutdown()
        captureExecutor.shutdown()
        super.onCleared()
    }
}

/** Undo the sensor rotation, so the target is upright before it is measured. */
private fun Bitmap.rotated(degrees: Int): Bitmap {
    if (degrees == 0) return this
    val matrix = android.graphics.Matrix().apply { postRotate(degrees.toFloat()) }
    return Bitmap.createBitmap(this, 0, 0, width, height, matrix, true)
}

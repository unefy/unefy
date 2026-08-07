package com.unefy.core.designsystem.component

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.toSize
import com.unefy.core.designsystem.theme.UnefyTheme
import com.unefy.core.model.scoring.PlacedShot
import com.unefy.core.model.scoring.ShotSeriesDraft
import com.unefy.core.model.scoring.TargetGeometry
import com.unefy.core.model.scoring.TargetGeometrySeed
import kotlin.math.hypot
import kotlin.math.roundToInt

/**
 * Colours of a printed paper target.
 *
 * The one place in the app that does not take its colours from the theme, and
 * deliberately so: these are physical properties of an object the user is
 * holding, not UI semantics. A target whose black mark followed the app's dark
 * mode would be unrecognisable. They live here as named constants so no call
 * site writes a literal — the rule the design system actually cares about.
 *
 * Values sampled from a BDS/DSB Scheibe Nr. 5.
 */
private object TargetPalette {
    val Sheet = Color(0xFFF2EDD3)
    val Black = Color(0xFF23231F)
    /** Ring 10 is printed light inside the black mark on the standard targets. */
    val InnerTen = Color(0xFFF2EDD3)
    val RingLineOnSheet = Color(0x66000000)
    val RingLineOnBlack = Color(0x80FFFFFF)
    val NumberOnSheet = Color(0xCC000000)
    val NumberOnBlack = Color(0xE6FFFFFF)
    /**
     * Shots are red, not the near-black of a real hole. On paper a hole is
     * dark, but the aiming mark is dark too — black shots inside the black were
     * all but invisible, which defeats the point of drawing them. Red reads on
     * cream and on black alike.
     */
    val Shot = Color(0xFFE0342A)
    val ShotRim = Color(0x73000000)
    /** Selection is a white ring, so it cannot be confused with the shot itself. */
    val ShotSelected = Color(0xFFFFFFFF)
    /** Ring lines drawn over a photo — must read on paper and on the black alike. */
    val RingOverPhoto = Color(0xCC1E88E5)
}

/** Shared with the rectified crop — see [TargetGeometry.FRAME_TO_SCORING]. */
private val SHEET_TO_SCORING = TargetGeometry.FRAME_TO_SCORING.toFloat()

private const val MIN_ZOOM = 1f
private const val MAX_ZOOM = 8f

/**
 * The magnifier shown while a shot is being dragged.
 *
 * A fingertip covers about a centimetre of screen, which at any useful zoom is
 * several rings — so the one thing the shooter cannot see while placing a shot
 * is the shot. The loupe puts that patch above the finger, magnified again, with
 * a crosshair on the exact point being set. Photo editors and text selection on
 * both platforms do the same thing for the same reason.
 */
private val LOUPE_RADIUS = 54.dp
private const val LOUPE_ZOOM = 2.5f

/**
 * How close a finger has to land to grab a shot, on SCREEN.
 *
 * It used to be 0.045 of the scoring radius, which on a phone works out at
 * about seven pixels — a third of what a fingertip can reliably hit, and the
 * reason selecting a shot felt impossible. A screen distance is the right unit
 * for a touch target: it stays the same size to the finger at every zoom, while
 * in target coordinates it shrinks as you magnify, which is exactly what
 * zooming in is for.
 */
private val GRAB_RADIUS = 22.dp

/**
 * A shooting target with its shots. Read-only.
 *
 * Coordinates follow the shared convention: normalised to the ring 1 radius,
 * origin at the centre, y pointing down.
 */
@Composable
fun TargetCanvas(
    geometry: TargetGeometry,
    shots: List<PlacedShot>,
    modifier: Modifier = Modifier,
    showRingValues: Boolean = false,
    /**
     * The rectified photograph of the sheet, drawn underneath the rings.
     *
     * Same frame as the drawing, so the two line up without further work — and
     * seeing them line up is itself the check that the rectification landed
     * where it should.
     */
    photo: ImageBitmap? = null,
    /**
     * Allow pinching into the target, as the recording screen does.
     *
     * A group inside the ten ring is a few millimetres across; on a phone that
     * is a handful of pixels, and a recorded series is unreadable without being
     * able to get closer. Double tap returns to the whole sheet.
     */
    zoomable: Boolean = false,
) {
    val measurer = rememberTextMeasurer()
    var zoom by remember { mutableFloatStateOf(MIN_ZOOM) }
    var pan by remember { mutableStateOf(Offset.Zero) }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .clipToBounds()
            .then(
                if (!zoomable) {
                    Modifier
                } else {
                    Modifier.pointerInput(Unit) {
                        // Two gestures, one handler: pinch to magnify, double
                        // tap to come back. Kept apart from the recording
                        // canvas, which additionally has to tell a drag of one
                        // shot from a pan of the whole sheet.
                        val limit = { offered: Offset, factor: Float ->
                            val bound = (factor - 1f) * size.width / 2f
                            Offset(
                                offered.x.coerceIn(-bound, bound),
                                offered.y.coerceIn(-bound, bound),
                            )
                        }
                        awaitEachGesture {
                            awaitFirstDown(requireUnconsumed = false)
                            do {
                                val event = awaitPointerEvent()
                                if (event.changes.count { it.pressed } < 2) continue
                                val next = (zoom * event.calculateZoom())
                                    .coerceIn(MIN_ZOOM, MAX_ZOOM)
                                val focus = event.calculateCentroid(useCurrent = true) -
                                    Offset(size.width / 2f, size.height / 2f)
                                pan = limit(
                                    (pan - focus) * (next / zoom) + focus + event.calculatePan(),
                                    next,
                                )
                                zoom = next
                                if (zoom == MIN_ZOOM) pan = Offset.Zero
                                event.changes.forEach { it.consume() }
                            } while (event.changes.any { it.pressed })
                        }
                    }.pointerInput(Unit) {
                        detectTapGestures(
                            onDoubleTap = {
                                zoom = MIN_ZOOM
                                pan = Offset.Zero
                            },
                        )
                    }
                },
            ),
    ) {
    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .graphicsLayer {
                scaleX = zoom
                scaleY = zoom
                translationX = pan.x
                translationY = pan.y
            },
    ) {
        val scoringRadius = size.minDimension / 2f / SHEET_TO_SCORING
        if (photo != null) {
            drawPhoto(photo)
            drawRingsOnly(geometry, scoringRadius, measurer)
        } else {
            drawTarget(geometry, scoringRadius, measurer)
        }
        shots.forEach { shot ->
            drawShot(
                shot, geometry, scoringRadius, measurer, showRingValues,
                selected = false, outlined = photo != null,
            )
        }
    }
    }
}

/**
 * A target the user can shoot at with their finger.
 *
 * Tap on empty paper places a shot; tap one to select it; drag it to move it.
 * Pinch zooms up to 8× around the fingers, which matters on the air rifle target
 * where the 10 ring is half a millimetre across — see ml/NOTES-real-targets.md.
 *
 * Every edit goes through [ShotSeriesDraft], so the running total on screen is
 * computed by the same engine that will score the series on save.
 */
@Composable
fun InteractiveTargetCanvas(
    draft: ShotSeriesDraft,
    onDraftChange: (ShotSeriesDraft) -> Unit,
    modifier: Modifier = Modifier,
    /** The shot the user is working on, highlighted and offered for deletion. */
    selectedShotId: String? = null,
    onSelectShot: (String?) -> Unit = {},
    /**
     * A rectified photo of the actual target, drawn underneath the rings.
     *
     * When present, the shooter places hits on the real sheet rather than on a
     * drawing, which is far more precise — and the drawn rings on top act as the
     * check that the rectification landed where it should.
     */
    photo: ImageBitmap? = null,
    newShotId: () -> String,
) {
    val measurer = rememberTextMeasurer()
    val haptics = LocalHapticFeedback.current

    // Zoom and pan live here, not in the caller. Passing zoom in as a parameter
    // was a real bug: the gesture coroutine captures its parameters once, so
    // every pinch computed `staleZoom * factor` and snapped back — while pan,
    // being local state, worked. It looked like pinching moved the target.
    var zoom by remember { mutableFloatStateOf(1f) }
    var pan by remember { mutableStateOf(Offset.Zero) }
    var draggingId by remember { mutableStateOf<String?>(null) }
    var dragPoint by remember { mutableStateOf<Offset?>(null) }

    /**
     * A finger held still hides the shot markers.
     *
     * With a photograph underneath, a marker sits exactly on the thing it marks
     * — so the one moment you want to check whether a detected shot really is a
     * hole is the one moment you cannot see the hole. Holding a finger on the
     * sheet takes the markers away for as long as it stays down.
     */
    var peeking by remember { mutableStateOf(false) }

    // The gesture loop must not restart mid-drag, so it is keyed on Unit and
    // reads the moving parts through these instead. Keying it on `draft` meant
    // the coroutine was cancelled on the first move of a shot — the drag died
    // after one frame.
    val currentDraft by rememberUpdatedState(draft)
    val currentSelected by rememberUpdatedState(selectedShotId)
    val onDraftChanged by rememberUpdatedState(onDraftChange)
    val onShotSelected by rememberUpdatedState(onSelectShot)
    val nextShotId by rememberUpdatedState(newShotId)

    /**
     * Screen point → normalised target coordinates, undoing zoom and pan.
     *
     * The canvas is drawn through a `graphicsLayer`, so the pointer arrives in
     * untransformed space and has to be mapped back by hand; using the drawn
     * positions directly would put shots in the wrong place at any zoom > 1.
     */
    fun toTarget(point: Offset, size: Size): Pair<Double, Double> {
        val centre = Offset(size.width / 2f, size.height / 2f)
        val scoringRadius = size.minDimension / 2f / SHEET_TO_SCORING
        val unzoomed = (point - centre - pan) / zoom
        return (unzoomed.x / scoringRadius).toDouble() to (unzoomed.y / scoringRadius).toDouble()
    }

    /**
     * Pan, kept so that the magnified target still covers the viewport.
     *
     * Without this a drag can push the sheet off the screen and there is no way
     * back except zooming out again.
     */
    fun clampPan(offered: Offset, size: Size): Offset {
        val limitX = (zoom - 1f) * size.width / 2f
        val limitY = (zoom - 1f) * size.height / 2f
        return Offset(
            offered.x.coerceIn(-limitX, limitX),
            offered.y.coerceIn(-limitY, limitY),
        )
    }

    // The clip has to sit on a container that does NOT scale. `clip = true`
    // inside the same `graphicsLayer` was the earlier, wrong attempt: it clips
    // in local coordinates and the scale is applied afterwards, so the clipped
    // content was simply magnified past the bounds again — the target still
    // painted over the hint text below it.
    //
    // The viewport stays SQUARE at every zoom. It used to grow taller with the
    // magnification, which quietly broke three things at once: the photo is
    // drawn to fill the box, so it stretched; the rings are drawn off
    // `minDimension`, so they did not, and the two came apart; and the mapping
    // from finger to target changed shape mid-gesture, so shots placed while
    // zoomed in jumped somewhere else when zooming back out. Panning is what
    // reaches the parts a magnified square cannot show.
    Box(
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(1f)
            .clipToBounds()
            // One gesture handler, not three. Three stacked `pointerInput`s were
            // the bug: `detectTransformGestures` sits topmost and claims
            // single-finger movement as a pan, so the drag detector below it
            // never saw a thing and shots could not be moved. A single loop can
            // tell the cases apart — and consuming the events also stops the
            // enclosing scroll container from stealing vertical drags.
            .pointerInput(Unit) {
                awaitEachGesture {
                    val down = awaitFirstDown(requireUnconsumed = false)
                    val canvasSize = size.toSize()
                    val centre = Offset(canvasSize.width / 2f, canvasSize.height / 2f)
                    val (downX, downY) = toTarget(down.position, canvasSize)
                    // The tolerance is a distance on screen, converted here into
                    // target coordinates: dividing by the zoom keeps the grab
                    // area the same size under the finger at any magnification,
                    // which is what lets a magnified view separate two shots
                    // that sit close together.
                    val scoringRadius = canvasSize.minDimension / 2f / SHEET_TO_SCORING
                    val grabInTarget = GRAB_RADIUS.toPx() / scoringRadius / zoom
                    val grabbed = currentDraft.nearest(downX, downY, grabInTarget.toDouble())

                    var movedFar = false
                    var multiTouch = false
                    val downAt = System.currentTimeMillis()

                    while (true) {
                        // A finger held still on the sheet hides the markers, so
                        // the holes underneath can be seen. It has to be done
                        // with a timeout rather than by waiting for an event: a
                        // finger that does not move produces none, and the
                        // gesture would sit here until it lifted.
                        val event = if (!movedFar && !multiTouch && !peeking) {
                            val waited = System.currentTimeMillis() - downAt
                            val remaining = viewConfiguration.longPressTimeoutMillis - waited
                            val next = if (remaining <= 0) null else {
                                withTimeoutOrNull(remaining) { awaitPointerEvent() }
                            }
                            if (next == null) {
                                peeking = true
                                haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                                continue
                            }
                            next
                        } else {
                            awaitPointerEvent()
                        }
                        val pressed = event.changes.filter { it.pressed }
                        if (pressed.isEmpty()) {
                            dragPoint = null
                            break
                        }
                        // While peeking, the gesture is a look and nothing else
                        // — until the finger moves. Anybody about to drag a shot
                        // precisely holds still first to make sure they have it,
                        // and swallowing that drag made the loupe unreachable:
                        // the careful grab became a peek and never came back.
                        if (peeking) {
                            val moved = (pressed.first().position - down.position)
                                .getDistance() > viewConfiguration.touchSlop
                            if (!moved) {
                                pressed.forEach { it.consume() }
                                continue
                            }
                            peeking = false
                        }

                        if (pressed.size >= 2) {
                            // Two fingers is unambiguously zoom/pan.
                            multiTouch = true
                            draggingId = null

                            val ratio = event.calculateZoom()
                            val panDelta = event.calculatePan()
                            val focus = event.calculateCentroid(useCurrent = true) - centre
                            val next = (zoom * ratio).coerceIn(MIN_ZOOM, MAX_ZOOM)
                            // Keep the point under the fingers still, otherwise
                            // the target slides away from wherever you are
                            // trying to look.
                            zoom = next
                            pan = clampPan((pan - focus) * (next / zoom) + focus + panDelta, canvasSize)
                            if (zoom == MIN_ZOOM) pan = Offset.Zero

                            event.changes.forEach { it.consume() }
                            continue
                        }

                        val change = pressed.first()
                        if (!movedFar &&
                            (change.position - down.position).getDistance() >
                            viewConfiguration.touchSlop
                        ) {
                            movedFar = true
                            draggingId = grabbed?.id
                        }

                        if (movedFar) {
                            val id = draggingId
                            when {
                                id != null -> {
                                    change.consume()
                                    dragPoint = change.position
                                    val (x, y) = toTarget(change.position, canvasSize)
                                    onDraftChanged(currentDraft.move(id, x, y))
                                }
                                // One finger pans once zoomed in. It has to
                                // consume the event or the scrolling screen
                                // above takes every vertical drag — which is why
                                // moving the target used to need two fingers.
                                zoom > MIN_ZOOM -> {
                                    change.consume()
                                    pan = clampPan(pan + change.positionChange(), canvasSize)
                                }
                                // At 1x the whole target is visible and there is
                                // nothing to pan, so the drag is left alone and
                                // the page scrolls as usual.
                                else -> Unit
                            }
                        }
                    }

                    if (peeking) {
                        peeking = false
                        return@awaitEachGesture
                    }
                    if (movedFar || multiTouch) {
                        draggingId = null
                        dragPoint = null
                        return@awaitEachGesture
                    }

                    // A tap. On an existing shot it selects it (tap again to
                    // deselect); on empty paper it places a new one. Long-press
                    // used to delete, which was both undiscoverable and awkward
                    // with a phone on a shooting bench — there is a button now.
                    if (grabbed != null) {
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                        onShotSelected(if (grabbed.id == currentSelected) null else grabbed.id)
                    } else if (hypot(downX, downY) <= SHEET_TO_SCORING) {
                        haptics.performHapticFeedback(HapticFeedbackType.LongPress)
                        onShotSelected(null)
                        onDraftChanged(currentDraft.place(nextShotId(), downX, downY))
                    }
                }
            }
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .graphicsLayer {
                    scaleX = zoom
                    scaleY = zoom
                    translationX = pan.x
                    translationY = pan.y
                },
        ) {
            val scoringRadius = size.minDimension / 2f / SHEET_TO_SCORING
            if (photo != null) {
                drawPhoto(photo)
                drawRingsOnly(draft.geometry, scoringRadius, measurer)
            } else {
                drawTarget(draft.geometry, scoringRadius, measurer)
            }
            if (!peeking) {
                draft.shots.forEach { shot ->
                    drawShot(
                        shot = shot,
                        geometry = draft.geometry,
                        scoringRadius = scoringRadius,
                        measurer = measurer,
                        showRingValues = true,
                        selected = shot.id == draggingId || shot.id == selectedShotId,
                        seriesCaliberMm = draft.caliberMm,
                        outlined = photo != null,
                    )
                }
            }
        }

        // The loupe sits OUTSIDE the zooming layer, in screen coordinates, and
        // re-draws the target through the same transform plus its own — drawing
        // it inside would magnify it along with everything else.
        val finger = dragPoint
        if (finger != null) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val scoringRadius = size.minDimension / 2f / SHEET_TO_SCORING
                val radius = LOUPE_RADIUS.toPx()
                val canvasCentre = Offset(size.width / 2f, size.height / 2f)

                // Above the finger, or below it when there is no room up there.
                val above = finger.y > radius * 2.4f
                val centre = Offset(
                    finger.x.coerceIn(radius, size.width - radius),
                    if (above) finger.y - radius * 1.6f else finger.y + radius * 1.6f,
                )

                withTransform({
                    clipPath(Path().apply {
                        addOval(
                            Rect(
                                centre.x - radius, centre.y - radius,
                                centre.x + radius, centre.y + radius,
                            ),
                        )
                    })
                    // Read bottom-up: the target's own zoom and pan first, then
                    // the loupe's magnification about the finger.
                    translate(centre.x - LOUPE_ZOOM * finger.x, centre.y - LOUPE_ZOOM * finger.y)
                    scale(LOUPE_ZOOM, LOUPE_ZOOM, pivot = Offset.Zero)
                    translate(canvasCentre.x * (1f - zoom) + pan.x, canvasCentre.y * (1f - zoom) + pan.y)
                    scale(zoom, zoom, pivot = Offset.Zero)
                }) {
                    if (photo != null) {
                        drawPhoto(photo)
                        drawRingsOnly(draft.geometry, scoringRadius, measurer)
                    } else {
                        drawTarget(draft.geometry, scoringRadius, measurer)
                    }
                    draft.shots.forEach { shot ->
                        drawShot(
                            shot = shot,
                            geometry = draft.geometry,
                            scoringRadius = scoringRadius,
                            measurer = measurer,
                            showRingValues = false,
                            selected = shot.id == draggingId,
                            seriesCaliberMm = draft.caliberMm,
                            outlined = photo != null,
                        )
                    }
                }

                // A crosshair on the exact point, and a rim so the loupe reads as
                // a separate thing rather than as part of the target.
                val arm = radius * 0.22f
                drawLine(TargetPalette.ShotSelected, Offset(centre.x - arm, centre.y),
                    Offset(centre.x + arm, centre.y), strokeWidth = 1.5.dp.toPx())
                drawLine(TargetPalette.ShotSelected, Offset(centre.x, centre.y - arm),
                    Offset(centre.x, centre.y + arm), strokeWidth = 1.5.dp.toPx())
                drawCircle(TargetPalette.ShotRim, radius, centre, style = Stroke(3.dp.toPx()))
                drawCircle(TargetPalette.ShotSelected, radius, centre, style = Stroke(1.5.dp.toPx()))
            }
        }
    }
}

/**
 * The photo, scaled to fill the canvas.
 *
 * It is already rectified and cropped to `CROP_MARGIN` scoring radii, the same
 * framing the drawn target uses, so the two line up without further work.
 */
private fun DrawScope.drawPhoto(photo: ImageBitmap) {
    drawImage(
        image = photo,
        dstSize = IntSize(size.width.toInt(), size.height.toInt()),
    )
}

/**
 * Ring lines and numbers without the paper and the black mark.
 *
 * Over a photo the sheet is already there; drawing it again would hide it. The
 * rings stay, both to read positions against and to show at a glance whether the
 * rectification is aligned with the real target underneath.
 */
private fun DrawScope.drawRingsOnly(
    geometry: TargetGeometry,
    scoringRadius: Float,
    measurer: TextMeasurer,
) {
    val centre = Offset(size.width / 2f, size.height / 2f)
    for (ring in 1..TargetGeometry.RING_COUNT) {
        val radius = (geometry.ringFraction(ring) * scoringRadius).toFloat()
        if (radius < 1f) continue
        drawCircle(
            color = TargetPalette.RingOverPhoto,
            radius = radius,
            center = centre,
            style = Stroke(width = 1.dp.toPx()),
        )
    }
    drawRingNumbers(geometry, scoringRadius, centre, measurer)
}

// --- Drawing ---

private fun DrawScope.drawTarget(
    geometry: TargetGeometry,
    scoringRadius: Float,
    measurer: TextMeasurer,
) {
    val centre = Offset(size.width / 2f, size.height / 2f)

    drawRect(TargetPalette.Sheet)

    val blackRadius = (geometry.blackFraction * scoringRadius).toFloat()
    drawCircle(TargetPalette.Black, radius = blackRadius, center = centre)

    // Ring 10 is printed light inside the black mark. Not decoration: it is the
    // second concentric circle of known diameter that the photo pipeline uses to
    // recover the full homography (ml/NOTES-real-targets.md).
    val tenRadius = (geometry.ringFraction(10) * scoringRadius).toFloat()
    if (geometry.isRingOnBlack(10) && tenRadius > 1f) {
        drawCircle(TargetPalette.InnerTen, radius = tenRadius, center = centre)
    }

    for (ring in 1..TargetGeometry.RING_COUNT) {
        val radius = (geometry.ringFraction(ring) * scoringRadius).toFloat()
        if (radius < 1f) continue
        val onBlack = geometry.isRingOnBlack(ring) && ring != 10
        drawCircle(
            color = if (onBlack) TargetPalette.RingLineOnBlack else TargetPalette.RingLineOnSheet,
            radius = radius,
            center = centre,
            style = Stroke(width = 1.dp.toPx() * 0.7f),
        )
    }

    drawRingNumbers(geometry, scoringRadius, centre, measurer)
}

/**
 * Ring numbers at four positions, as they are printed. Rings 1..9 only — the 10
 * has no room and carries no number on a real sheet.
 */
private fun DrawScope.drawRingNumbers(
    geometry: TargetGeometry,
    scoringRadius: Float,
    centre: Offset,
    measurer: TextMeasurer,
) {
    val fontSize = (scoringRadius * 0.055f).coerceIn(7f, 15f)

    for (ring in 1..9) {
        val outer = geometry.ringFraction(ring)
        val inner = geometry.ringFraction(ring + 1)
        val mid = ((outer + inner) / 2 * scoringRadius).toFloat()
        if (mid < fontSize) continue

        val onBlack = geometry.isRingOnBlack(ring)
        val layout = measurer.measure(
            text = ring.toString(),
            style = TextStyle(
                fontSize = fontSize.toSp(),
                color = if (onBlack) TargetPalette.NumberOnBlack else TargetPalette.NumberOnSheet,
            ),
        )
        val half = Offset(layout.size.width / 2f, layout.size.height / 2f)

        listOf(
            Offset(centre.x - mid, centre.y),
            Offset(centre.x + mid, centre.y),
            Offset(centre.x, centre.y - mid),
            Offset(centre.x, centre.y + mid),
        ).forEach { position ->
            drawText(layout, topLeft = position - half)
        }
    }
}

private fun DrawScope.drawShot(
    shot: PlacedShot,
    geometry: TargetGeometry,
    scoringRadius: Float,
    measurer: TextMeasurer,
    showRingValues: Boolean,
    selected: Boolean,
    seriesCaliberMm: Double? = null,
    /**
     * Draw the marker as an outline with the hole showing through it.
     *
     * Over a photograph a filled dot covers exactly the thing it marks: the
     * hole is the evidence, and hiding it defeats the purpose of putting the
     * photo there. A ring at true caliber with a small centre point says the
     * same — where the shot is, and how wide — while leaving the hole visible.
     * Over the drawn target there is nothing underneath, so a filled dot reads
     * better and stays.
     */
    outlined: Boolean = false,
) {
    // A shot that missed the sheet has no place on it. It is carried at a fixed
    // position past the frame purely so it scores zero, and drawing that
    // position would claim a location nobody measured — the shot list is where
    // a miss belongs, and it says so there in words.
    if (shot.isMiss) return

    val centre = Offset(size.width / 2f, size.height / 2f)
    val position = centre + Offset(
        (shot.x * scoringRadius).toFloat(),
        (shot.y * scoringRadius).toFloat(),
    )

    // The hole at its true size, so a group looks on screen the way it looks on
    // paper. The floor is deliberately tiny: at 7.dp a 9 mm hole came out three
    // times too wide on the 25 m target and made every group look worse than it
    // was — and the marker does not need to be big to be grabbed, because
    // [GRAB_RADIUS] is a separate, much larger hit area.
    val caliber = shot.caliberMm ?: seriesCaliberMm ?: geometry.defaultCaliberMm
    val trueRadius = (caliber / 2 / geometry.scoringRadiusMm * scoringRadius).toFloat()
    val radius = maxOf(trueRadius, 2.dp.toPx())

    if (selected) {
        drawCircle(
            color = TargetPalette.ShotSelected,
            radius = radius + 6.dp.toPx(),
            center = position,
            style = Stroke(width = 2.dp.toPx()),
        )
    }
    if (outlined) {
        // A dark hairline outside the red one: on a photograph the sheet is
        // cream in some places and near-black in others, and a single colour
        // disappears into one of them.
        drawCircle(
            color = TargetPalette.ShotRim,
            radius = radius + 1.dp.toPx(),
            center = position,
            style = Stroke(width = 2.5.dp.toPx()),
        )
        drawCircle(
            color = TargetPalette.Shot,
            radius = radius + 1.dp.toPx(),
            center = position,
            style = Stroke(width = 1.5.dp.toPx()),
        )
        // The centre, because the ring says how wide the shot is and this says
        // where it is — which is the number the ring value is computed from.
        drawCircle(TargetPalette.Shot, radius = 1.dp.toPx(), center = position)
    } else {
        drawCircle(TargetPalette.Shot, radius = radius, center = position)

        // A hairline for definition where red meets the light 10 ring. Drawn
        // centred on the radius, so on a true-scale 9 mm marker a fixed 1.dp
        // stroke ate most of the dot and the shot rendered as an empty ring —
        // hence the scaling and the floor.
        if (radius > 4.dp.toPx()) {
            drawCircle(
                color = TargetPalette.ShotRim,
                radius = radius,
                center = position,
                style = Stroke(width = (radius * 0.18f).coerceAtMost(1.dp.toPx())),
            )
        }
    }

    if (showRingValues && radius > 9.dp.toPx()) {
        val layout = measurer.measure(
            text = shot.ring.toString(),
            style = TextStyle(
                fontSize = (radius * 0.85f).toSp(),
                color = TargetPalette.NumberOnBlack,
            ),
        )
        drawText(
            layout,
            topLeft = position - Offset(layout.size.width / 2f, layout.size.height / 2f),
        )
    }
}

private fun Float.toSp() = (this / 1f).roundToInt().sp

// --- Previews ---

@Preview(showBackground = true)
@Composable
private fun TargetCanvasPreview() {
    val geometry = TargetGeometrySeed.PRECISION_25M
    UnefyTheme {
        TargetCanvas(
            geometry = geometry,
            shots = listOf(
                PlacedShot("1", 0.02, -0.03, 10),
                PlacedShot("2", -0.12, 0.08, 9),
                PlacedShot("3", 0.31, 0.19, 7),
            ),
            showRingValues = true,
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun AirRifleTargetPreview() {
    UnefyTheme {
        TargetCanvas(
            geometry = TargetGeometrySeed.AIR_RIFLE_10M,
            shots = listOf(PlacedShot("1", 0.05, 0.02, 9)),
        )
    }
}

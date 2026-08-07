package com.unefy.feature.scoring

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The part of [ScanStore] a recording screen needs.
 *
 * Separate from the class so the screen's tests can run on the plain JVM: the
 * store itself is built on `Context` and `Bitmap`, neither of which exists
 * outside an instrumented run, and a ViewModel test has no business needing a
 * device to construct its dependencies.
 */
interface SeriesScans {
    fun load(seriesId: String, kind: ScanStore.Kind): Bitmap?

    fun attach(seriesId: String)
}

/**
 * The photographs behind a recorded series, kept on the device.
 *
 * Two of them per series: the photo as taken, and the rectified crop the shots
 * were placed on. Both earn their place twice over — a shooter wants to see the
 * sheet again next to the numbers, and every stored pair is a training example
 * for the hit detector, already squared up and already corrected by the person
 * who fired the shots (ml/README.md, "Die Strecke mit Modell").
 *
 * They never leave the device on their own. Uploading them is a separate
 * decision for whoever runs the club's server, not a side effect of recording.
 */
@Singleton
class ScanStore @Inject constructor(
    @ApplicationContext private val context: Context,
) : SeriesScans {
    private val directory: File?
        get() = context.getExternalFilesDir(FOLDER)

    /** The last scan, before it belongs to a series. */
    fun latest(kind: Kind): File? = directory?.resolve(kind.latestName)?.takeIf { it.isFile }

    fun write(kind: Kind, bitmap: Bitmap) {
        val target = directory?.resolve(kind.latestName) ?: return
        runCatching {
            target.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, it) }
        }
    }

    /**
     * Attach the last scan to a series.
     *
     * Copied rather than moved: the same photograph may carry a second series
     * for the second shooter on the same sheet, which is ordinary practice
     * (ml/NOTES-real-targets.md §1b).
     */
    override fun attach(seriesId: String) {
        val dir = directory ?: return
        for (kind in Kind.entries) {
            val source = dir.resolve(kind.latestName).takeIf { it.isFile } ?: continue
            runCatching { source.copyTo(dir.resolve(kind.nameFor(seriesId)), overwrite = true) }
        }
        prune()
    }

    fun of(seriesId: String, kind: Kind): File? =
        directory?.resolve(kind.nameFor(seriesId))?.takeIf { it.isFile }

    override fun load(seriesId: String, kind: Kind): Bitmap? =
        of(seriesId, kind)?.let { BitmapFactory.decodeFile(it.path) }

    /**
     * Keep the newest [KEEP_SERIES] series and drop the rest.
     *
     * A pair is about two and a half megabytes, so a season of weekly shooting
     * would quietly fill a phone. The cap is generous enough that nobody meets
     * it in a session and small enough that nobody notices the storage.
     */
    private fun prune() {
        val dir = directory ?: return
        val byId = dir.listFiles()
            .orEmpty()
            .filter { file -> Kind.entries.none { file.name == it.latestName } }
            // Before the LAST dash: the series id is a UUID and has dashes of
            // its own, so cutting at the first one would lump unrelated series
            // together and delete the wrong photographs.
            .groupBy { it.name.substringBeforeLast('-') }
        byId.entries
            .sortedByDescending { (_, files) -> files.maxOf { it.lastModified() } }
            .drop(KEEP_SERIES)
            .forEach { (_, files) -> files.forEach { it.delete() } }
    }

    enum class Kind(private val suffix: String) {
        /** The photograph as the camera took it, rotated upright. */
        PHOTO("photo"),

        /** The same sheet squared up: what the shots were placed on. */
        RECTIFIED("rectified"),
        ;

        val latestName: String get() = "last-$suffix.jpg"

        fun nameFor(seriesId: String): String = "$seriesId-$suffix.jpg"
    }

    private companion object {
        const val FOLDER = "scans"
        const val QUALITY = 92
        const val KEEP_SERIES = 60
    }
}

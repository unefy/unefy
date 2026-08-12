package com.unefy.feature.documents

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.unefy.core.designsystem.R as DesignR
import com.unefy.core.designsystem.component.UNEFY_STATE_FILL
import com.unefy.core.designsystem.component.UnefyCenteredState
import com.unefy.core.designsystem.component.UnefyListScaffold
import com.unefy.core.designsystem.theme.UnefySpacing
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import com.unefy.core.network.ApiError
import com.unefy.core.network.ApiResult

sealed interface DocumentViewUiState {
    data object Loading : DocumentViewUiState

    data class Content(
        /** One bitmap per page, in order. */
        val pages: List<ImageBitmap>,
        /** Where the bytes were written, for handing the file to another app. */
        val file: File,
    ) : DocumentViewUiState

    data class Failure(val error: ApiError?) : DocumentViewUiState
}

/**
 * A document, rendered inside the app.
 *
 * Rendered here rather than handed to whatever PDF viewer the phone happens to
 * have: on a stock Android device that is often nothing at all, and a
 * certificate that opens on one member's phone and produces "no app can do
 * this" on another's is not a feature the club can rely on. Sharing it out
 * stays available for the times somebody wants it in their mail or their files.
 *
 * The bytes are written to the cache before rendering because [PdfRenderer]
 * needs a seekable descriptor — and the file is then the same one the share
 * sheet hands over, so there is exactly one copy on disk and the system may
 * reclaim it.
 */
@HiltViewModel
class DocumentViewModel @Inject constructor(
    private val repository: DocumentsRepository,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow<DocumentViewUiState>(DocumentViewUiState.Loading)
    val uiState: StateFlow<DocumentViewUiState> = _uiState.asStateFlow()

    private var loaded: String? = null

    fun load(documentId: String, own: Boolean) {
        if (loaded == documentId) return
        loaded = documentId
        _uiState.value = DocumentViewUiState.Loading

        viewModelScope.launch {
            when (val result = repository.pdf(documentId, own)) {
                is ApiResult.Success -> _uiState.value = withContext(Dispatchers.IO) {
                    runCatching { render(documentId, result.data) }
                        .getOrElse { DocumentViewUiState.Failure(null) }
                }

                is ApiResult.Failure ->
                    _uiState.value = DocumentViewUiState.Failure(result.error)
            }
        }
    }

    /**
     * Bytes to pages. Off the main thread — a two-page A4 render is tens of
     * milliseconds of bitmap work, which is a dropped frame either way.
     */
    private fun render(documentId: String, bytes: ByteArray): DocumentViewUiState {
        val directory = File(context.cacheDir, CACHE_DIRECTORY).apply { mkdirs() }
        val file = File(directory, "$documentId.pdf")
        file.writeBytes(bytes)

        val pages = mutableListOf<ImageBitmap>()
        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor ->
            // try/finally rather than `use`: PdfRenderer and its Page only
            // implement AutoCloseable from API 33, and this app runs from 31.
            // `use` would compile against the newer SDK and fail on the device.
            val renderer = PdfRenderer(descriptor)
            try {
                for (index in 0 until renderer.pageCount) {
                    val page = renderer.openPage(index)
                    try {
                        val height = PAGE_WIDTH_PX * page.height / page.width
                        val bitmap = Bitmap.createBitmap(
                            PAGE_WIDTH_PX,
                            height,
                            Bitmap.Config.ARGB_8888,
                        )
                        // A page is drawn onto whatever is already there, and a
                        // fresh bitmap is transparent — without this the text
                        // sits on nothing and reads as black on black in dark
                        // mode. The paper is white in both themes because it is
                        // paper, not a surface.
                        bitmap.eraseColor(Color.WHITE)
                        page.render(
                            bitmap,
                            null,
                            null,
                            PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY,
                        )
                        pages += bitmap.asImageBitmap()
                    } finally {
                        page.close()
                    }
                }
            } finally {
                renderer.close()
            }
        }
        return DocumentViewUiState.Content(pages = pages, file = file)
    }

    private companion object {
        const val CACHE_DIRECTORY = "documents"

        /** Roughly A4 at 150 dpi — legible when zoomed, one page per 8 MB. */
        const val PAGE_WIDTH_PX = 1240
    }
}

@Composable
fun DocumentViewRoute(
    documentId: String,
    title: String,
    /** A plain member has their own route for this; the board's would be a 403. */
    own: Boolean,
    onBack: () -> Unit,
    viewModel: DocumentViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(documentId, own) { viewModel.load(documentId, own) }
    DocumentViewScreen(state = state, title = title, onBack = onBack)
}

@Composable
fun DocumentViewScreen(
    state: DocumentViewUiState,
    title: String,
    onBack: () -> Unit = {},
) {
    val context = LocalContext.current

    UnefyListScaffold(
        title = title,
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    painter = painterResource(DesignR.drawable.ic_arrow_back),
                    contentDescription = stringResource(R.string.documents_back),
                )
            }
        },
        actions = {
            if (state is DocumentViewUiState.Content) {
                IconButton(onClick = { share(context, state.file, title) }) {
                    Icon(
                        painter = painterResource(DesignR.drawable.ic_share),
                        contentDescription = stringResource(R.string.documents_share),
                    )
                }
            }
        },
    ) {
        when (state) {
            DocumentViewUiState.Loading -> Unit

            is DocumentViewUiState.Failure -> item("error") {
                UnefyCenteredState(
                    title = stringResource(R.string.documents_open_failed_title),
                    body = stringResource(R.string.documents_open_failed_body),
                    modifier = Modifier.fillParentMaxHeight(UNEFY_STATE_FILL),
                )
            }

            is DocumentViewUiState.Content -> items(state.pages.size, key = { "page-$it" }) { index ->
                val page = state.pages[index]
                Surface(
                    color = androidx.compose.ui.graphics.Color.White,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.padding(
                        horizontal = UnefySpacing.sm,
                        vertical = UnefySpacing.sm,
                    ),
                ) {
                    Image(
                        bitmap = page,
                        contentDescription = null,
                        contentScale = ContentScale.FillWidth,
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(page.width.toFloat() / page.height),
                    )
                }
            }
        }
    }
}

/**
 * Hands the file to another app — mail, files, print.
 *
 * A content URI with a one-off read grant, never a `file://` path: the latter
 * throws on every Android since 7, and the grant dies with the receiving app's
 * task rather than leaving a member's certificate readable to anything that
 * asks.
 */
private fun share(context: Context, file: File, title: String) {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.documents", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "application/pdf"
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_SUBJECT, title)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, title))
}

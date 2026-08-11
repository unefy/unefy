"""A QR code as its bare module matrix.

The PDFs draw their QR with reportlab's widget straight onto the page. A web
page cannot do that, and the two obvious alternatives are both worse than they
look: rasterising server-side needs a native backend reportlab does not ship,
and adding an encoder to the frontend adds a dependency for something we can
already compute.

So the browser gets the matrix and draws squares. No image, no new package,
and nothing server-made is injected into the page as markup.
"""

from reportlab.graphics.barcode import qrencoder


def qr_matrix(value: str) -> list[str]:
    """Encode `value` and return one string of "0"/"1" per row.

    Error correction M — the middle setting, and the one reportlab uses for the
    codes on the documents. A QR on a screen that somebody photographs from a
    metre away does not need the redundancy of a printed label.
    """
    code = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    code.addData(value)
    code.make()
    size = int(code.getModuleCount())
    return [
        "".join("1" if code.isDark(row, column) else "0" for column in range(size))
        for row in range(size)
    ]

import base64
import io
import fitz
from PIL import Image, ImageDraw

PAGE_PADDING_RATIO = 0.15  # extra page-height added above/below the matched quote, for context
ZOOM = 1.5
BOX_COLOR = (179, 38, 28)
BOX_WIDTH = 2


def render_highlighted_pages(file_bytes: bytes, citations: list[dict]) -> dict:
    """
    citations: [{"key": ..., "page": int, "quote": str}, ...]
    Returns {key: base64_png} - one image per citation, not per page, so each
    fact/red flag gets its own crop scoped to just its own quote. Falls back to
    the full page, unboxed, when that specific quote can't be located (fuzzy
    OCR text, paraphrased slightly, etc.) - so there's still something to see.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = {}

    for c in citations:
        page_num = c["page"]
        if page_num < 1 or page_num > len(doc):
            continue

        page = doc[page_num - 1]
        rects = _find_rects(page, c["quote"])
        images[c["key"]] = _render_cropped(page, rects) if rects else _render_full_page(page)

    doc.close()
    return images


def _render_cropped(page, rects: list) -> str:
    """Renders just the region around the matched rects (plus padding), then
    draws the boxes on the resulting IMAGE - never on the PDF page itself, so
    citations sharing a page never bleed boxes into each other."""
    bounds = rects[0]
    for rect in rects[1:]:
        bounds |= rect

    padding = page.rect.height * PAGE_PADDING_RATIO
    clip = fitz.Rect(
        page.rect.x0,
        max(page.rect.y0, bounds.y0 - padding),
        page.rect.x1,
        min(page.rect.y1, bounds.y1 + padding),
    )

    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=clip)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(image)

    for rect in rects:
        box = (
            (rect.x0 - clip.x0) * ZOOM,
            (rect.y0 - clip.y0) * ZOOM,
            (rect.x1 - clip.x0) * ZOOM,
            (rect.y1 - clip.y0) * ZOOM,
        )
        draw.rectangle(box, outline=BOX_COLOR, width=BOX_WIDTH)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _render_full_page(page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM))
    return base64.b64encode(pix.tobytes("png")).decode()


def _find_rects(page, quote: str) -> list:
    """AI-generated quotes sometimes drift slightly from the literal PDF text,
    so if the full quote doesn't match, try shrinking it down word by word
    until something is found (or give up and draw nothing)."""
    rects = page.search_for(quote)
    if rects:
        return rects

    words = quote.split()
    for length in (10, 6, 4):
        if len(words) > length:
            rects = page.search_for(" ".join(words[:length]))
            if rects:
                return rects

    return []
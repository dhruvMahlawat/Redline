import base64
import fitz

PAGE_PADDING_RATIO = 0.15  # extra page-height added above/below the matched quote, for context


def render_highlighted_pages(file_bytes: bytes, citations: list[dict]) -> dict:
    """
    citations: [{"page": int, "quote": str}, ...]
    Returns {page_number: base64_png} for every page referenced. When the quote
    can be located, renders a tight crop around it (with a red box) instead of
    the whole page - faster to scan, and it's obvious what you're looking at.
    Falls back to the full page, unboxed, when the quote can't be found (fuzzy
    OCR text, paraphrased slightly, etc.) - so there's still something to see.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_needed = {c["page"] for c in citations if c.get("page")}
    images = {}

    for page_num in pages_needed:
        if page_num < 1 or page_num > len(doc):
            continue

        page = doc[page_num - 1]
        page_citations = [c for c in citations if c.get("page") == page_num]

        rects = []
        for c in page_citations:
            rects.extend(_find_rects(page, c["quote"]))

        if rects:
            images[page_num] = _render_cropped(page, rects)
        else:
            images[page_num] = _render_full_page(page)

    doc.close()
    return images


def _render_cropped(page, rects: list) -> str:
    """Draws boxes around every matched rect, then crops to their combined
    bounding box plus padding, instead of returning the whole page."""
    shape = page.new_shape()
    for rect in rects:
        shape.draw_rect(rect)
    shape.finish(color=(0.7, 0.15, 0.11), width=1.5)
    shape.commit()

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

    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), clip=clip)
    return base64.b64encode(pix.tobytes("png")).decode()


def _render_full_page(page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
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
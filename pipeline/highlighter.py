import base64
import fitz


def render_highlighted_pages(file_bytes: bytes, citations: list[dict]) -> dict:
    """
    citations: [{"page": int, "quote": str}, ...]
    Returns {page_number: base64_png} for every page referenced, with a red box
    drawn around the quote wherever it can be found on that page. If the quote
    can't be located (paraphrased slightly, OCR text, etc.), the page is still
    rendered - just without a box - so there's always something to look at.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_needed = {c["page"] for c in citations if c.get("page")}
    images = {}

    for page_num in pages_needed:
        if page_num < 1 or page_num > len(doc):
            continue

        page = doc[page_num - 1]
        shape = page.new_shape()
        drew_a_box = False

        for c in citations:
            if c.get("page") != page_num:
                continue
            for rect in _find_rects(page, c["quote"]):
                shape.draw_rect(rect)
                drew_a_box = True

        if drew_a_box:
            shape.finish(color=(0.7, 0.15, 0.11), width=1.5)
            shape.commit()

        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        images[page_num] = base64.b64encode(pix.tobytes("png")).decode()

    doc.close()
    return images


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

import re
import io
import fitz  # pymupdf
import pytesseract
from PIL import Image

MIN_TEXT_LENGTH_BEFORE_OCR = 20  # a page with less text than this is probably a scanned image


def parse_pdf(file_bytes: bytes) -> dict:
    """
    Takes raw PDF bytes, returns:
    {
        "full_text": "...",       # the complete document, unmodified - what the AI should read
        "clauses": [...]          # best-effort section split, used for display/page tracking only
    }

    Clause splitting is heuristic (regex-based) and can misfire on unusual layouts -
    it should never be the thing that decides what content the AI gets to see.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    full_text = ""
    page_breaks = []  # (char_index_where_page_starts, page_number)

    for page_num, page in enumerate(doc, start=1):
        page_breaks.append((len(full_text), page_num))
        page_text = page.get_text()

        if len(page_text.strip()) < MIN_TEXT_LENGTH_BEFORE_OCR:
            page_text = _ocr_page(page)

        full_text += page_text

    doc.close()

    clauses = _split_into_clauses(full_text, page_breaks)
    return {"full_text": full_text, "clauses": clauses, "page_breaks": page_breaks}


def _ocr_page(page) -> str:
    """Renders a page to an image and reads it with tesseract - for scanned
    leases that have no real text layer at all."""
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom, OCR reads small text more reliably at higher res
    image = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(image)


def _split_into_clauses(text: str, page_breaks: list[tuple[int, int]]) -> list[dict]:
    # first try: numbered sections, e.g. "5. Security Deposit"
    numbered_pattern = re.compile(r"^\s*(\d{1,2})[\.\)]\s+([A-Z][A-Za-z /&-]{2,60})\s*$", re.MULTILINE)
    matches = list(numbered_pattern.finditer(text))

    if matches:
        return _build_clauses(matches, text, page_breaks, numbered=True)

    # a lot of real templates don't number sections at all - they just put a short
    # title-case heading alone on its own line ("Rent", "Security Deposit", ...).
    # every word capitalized is what tells this apart from a normal sentence.
    heading_pattern = re.compile(r"^([A-Z][a-z]*(?:\s[A-Z][a-z]*){0,3})\s*$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))

    if matches:
        return _build_clauses(matches, text, page_breaks, numbered=False)

    # neither pattern found anything - don't fail, just hand back the whole doc
    return [{"clause_number": None, "title": "Full Document", "text": text.strip(), "page": 1}]


def _build_clauses(matches, text: str, page_breaks: list[tuple[int, int]], numbered: bool) -> list[dict]:
    clauses = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if not body:
            continue

        clauses.append({
            "clause_number": match.group(1) if numbered else None,
            "title": (match.group(2) if numbered else match.group(1)).strip(),
            "text": body,
            "page": page_for_index(match.start(), page_breaks),
        })

    return clauses


def page_for_index(char_index: int, page_breaks: list[tuple[int, int]]) -> int:
    page = 1
    for start_index, page_num in page_breaks:
        if char_index >= start_index:
            page = page_num
        else:
            break
    return page

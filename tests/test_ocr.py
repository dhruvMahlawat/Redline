import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import fitz
from PIL import Image, ImageDraw
from pipeline.parser import parse_pdf


def make_scanned_pdf(text: str) -> bytes:
    """Builds a PDF with the text drawn onto an image and NO real text layer -
    simulates a scanned document, the case OCR is meant to catch."""
    img = Image.new("RGB", (600, 150), color="white")
    ImageDraw.Draw(img).text((20, 20), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="png")

    doc = fitz.open()
    page = doc.new_page(width=600, height=150)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc.tobytes()


def test_ocr_recovers_text_from_image_only_pdf():
    pdf = make_scanned_pdf("Monthly Rent $1,600")
    result = parse_pdf(pdf)
    assert "1,600" in result["full_text"]


def test_normal_text_pdf_does_not_go_through_ocr():
    # a page with a real text layer should just use get_text() directly -
    # OCR should only kick in when there's basically nothing extractable
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Monthly Rent $2,000", fontsize=10)
    result = parse_pdf(doc.tobytes())
    assert "2,000" in result["full_text"]

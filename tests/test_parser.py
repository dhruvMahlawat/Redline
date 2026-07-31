import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz
from pipeline.parser import parse_pdf, page_for_index


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=10)
    return doc.tobytes()


def test_numbered_clauses_split_correctly():
    pdf = make_pdf("1. Rent\nRent is $1,000.\n\n2. Deposit\nDeposit is $1,000.")
    result = parse_pdf(pdf)
    titles = [c["title"] for c in result["clauses"]]
    assert titles == ["Rent", "Deposit"]


def test_unnumbered_headings_split_correctly():
    pdf = make_pdf("Rent\nRent is $1,000.\n\nDeposit\nDeposit is $1,000.")
    result = parse_pdf(pdf)
    titles = [c["title"] for c in result["clauses"]]
    assert titles == ["Rent", "Deposit"]


def test_all_caps_title_does_not_get_treated_as_a_heading():
    # this was a real bug - "RESIDENTIAL LEASE AGREEMENT" used to get matched
    # as a section heading, which corrupted the full document text
    pdf = make_pdf("RESIDENTIAL LEASE AGREEMENT\nRent\nRent is $1,000.")
    result = parse_pdf(pdf)
    assert "RESIDENTIAL LEASE AGREEMENT" in result["full_text"]
    titles = [c["title"] for c in result["clauses"]]
    assert "RESIDENTIAL LEASE AGREEMENT" not in titles


def test_full_text_preserves_labels_next_to_values():
    # this was the actual data-loss bug: labels were getting stripped from
    # values when a heading and its value sat on adjacent lines
    pdf = make_pdf("Monthly Rent\n$1,250")
    result = parse_pdf(pdf)
    assert "Monthly Rent" in result["full_text"]
    assert "$1,250" in result["full_text"]


def test_falls_back_to_whole_document_when_no_headings_found():
    pdf = make_pdf("just some plain sentences with no headings at all in them.")
    result = parse_pdf(pdf)
    assert len(result["clauses"]) == 1
    assert result["clauses"][0]["title"] == "Full Document"


def test_page_for_index_finds_the_right_page():
    page_breaks = [(0, 1), (100, 2), (250, 3)]
    assert page_for_index(50, page_breaks) == 1
    assert page_for_index(150, page_breaks) == 2
    assert page_for_index(300, page_breaks) == 3

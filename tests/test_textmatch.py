import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.textmatch import find_quote


def test_exact_quote_is_found():
    doc = "Tenant shall pay a security deposit of $1,250."
    found, index = find_quote("Tenant shall pay a security deposit of $1,250.", doc)
    assert found
    assert doc[index:index + 10] == "Tenant sha"


def test_quote_with_pdf_style_line_wrap_is_still_found():
    doc = "Tenant shall pay a security\ndeposit of $1,250, refundable within 21 days."
    found, _ = find_quote("Tenant shall pay a security deposit of $1,250", doc)
    assert found


def test_invented_quote_is_not_found():
    doc = "Tenant shall pay a security deposit of $1,250."
    found, index = find_quote("Tenant must pay a pet deposit of $500 per animal.", doc)
    assert not found
    assert index == -1


def test_short_quote_needs_high_overlap_not_just_any_overlap():
    doc = "The tenant agrees to keep the unit clean at all times."
    # shares some words but isn't actually the same claim
    found, _ = find_quote("The landlord agrees to fix the unit within 30 days.", doc)
    assert not found

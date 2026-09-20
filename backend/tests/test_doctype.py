"""
Tests for backend/ai/doctype.py. The header texts below are copied from the REAL attachments in the dataset.

    python -m pytest backend/tests -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from ai.doctype import detect_doc_type, wrong_kind  # noqa: E402

REAL_HEADERS = {
    "SI": [
        "SHIPPING INSTRUCTION\n========================================\n\nShipper: APRIL FAR EAST (M) SDN BHD",  # txt
        "=== SHEET: S.I. ===\nASIA PACIFIC PAPERBOARD TRADING PTE LTD\nBL INSTRUCTION | 3154303911\nSHIPPER | ASIA PACIFIC",  # xlsx
        "--- page 1 ---\nBILL OF LADING INSTRUCTION\nB/L NUMBER: OOLU3584143842 BOOKING NO. PSGSE4981829\nShipper APRIL",  # pdf
    ],
    "BL": [
        "BILL OF LADING (DRAFT)\n========================================\n\nSHIPPER: APRIL FAR EAST (M) SDN BHD",  # txt
        "=== SHEET: BL ===\nASIA PACIFIC PAPERBOARD TRADING PTE LTD\nBILL OF LADING | 3154303911\nShipper (Principal or Seller) | X",  # xlsx
        "BILL OF LADING (DRAFT)\nB/L NO.(提单号): SIN616928451\nShipper (Principal or Seller) (发货人) | APRIL",  # docx
        "--- page 1 ---\nBILL OF LADING (DRAFT)\nB/L NUMBER: OOLU3584143842 BOOKING NO. PSGSE4981829",  # pdf
    ],
}


@pytest.mark.parametrize("kind", ["SI", "BL"])
def test_real_headers_are_recognised(kind):
    for text in REAL_HEADERS[kind]:
        assert detect_doc_type(text) == kind, text[:60]


@pytest.mark.parametrize(
    "text, kind",
    [
        ("COMMERCIAL INVOICE\n========\nInvoice No.: 5250078266", "COMMERCIAL_INVOICE"),
        ("PACKING LIST\n========\nShipper: ASIA PACIFIC PAPERBOARD TRADING PTE LTD", "PACKING_LIST"),
        ("CERTIFICATE OF ORIGIN\n========\nExporter: APRIL FAR EAST (M) SDN BHD", "CERTIFICATE_OF_ORIGIN"),
        ("some text without any recognisable header", "UNKNOWN"),
        ("", "UNKNOWN"),
    ],
)
def test_other_documents_are_recognised(text, kind):
    assert detect_doc_type(text) == kind


def test_wrong_documents_in_the_bl_slot_are_reported():  # emails 501-505
    assert wrong_kind("COMMERCIAL INVOICE\nInvoice No.: 1", "BL") == "Commercial Invoice"
    assert wrong_kind("PACKING LIST\nShipper: X", "BL") == "Packing List"
    assert wrong_kind("CERTIFICATE OF ORIGIN\nExporter: X", "BL") == "Certificate of Origin"


def test_swapped_slots_are_reported():
    assert wrong_kind(REAL_HEADERS["BL"][0], "SI") == "Bill of Lading"
    assert wrong_kind(REAL_HEADERS["SI"][2], "BL") == "Shipping Instruction"


def test_correct_documents_and_unknown_headers_are_not_blocked():
    for text in REAL_HEADERS["SI"]:
        assert wrong_kind(text, "SI") is None
    for text in REAL_HEADERS["BL"]:
        assert wrong_kind(text, "BL") is None
    assert wrong_kind("no recognisable header here", "BL") is None  # benefit of the doubt: let the extractor try

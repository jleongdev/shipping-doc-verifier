"""
doctype.py - decide what KIND of document a text is (Shipping Instruction, Bill of Lading, invoice, ...)
from its header. NO AI and no API call, so it is free, instant and testable.

The real data uses several headers for the same kind of document:
    SI:  "SHIPPING INSTRUCTION" (txt) | "BL INSTRUCTION" (xlsx) | "BILL OF LADING INSTRUCTION" (pdf)
    BL:  "BILL OF LADING (DRAFT)" (txt / pdf / docx) | "BILL OF LADING | <number>" (xlsx)
and some BL slots contain something else entirely (COMMERCIAL INVOICE, PACKING LIST, CERTIFICATE OF ORIGIN).

    from ai.doctype import detect_doc_type, wrong_kind
    wrong_kind(text, "BL")   # -> "Packing List" if the BL slot holds a packing list, else None
"""
import re

_SI = re.compile(r"\b(?:SHIPPING|BILL\s+OF\s+LADING|B/?L)\s+INSTRUCTIONS?\b")
_BL = re.compile(r"\bBILL\s+OF\s+LADING\b")
_OTHER = [
    ("COMMERCIAL_INVOICE", re.compile(r"\bCOMMERCIAL\s+INVOICE\b")),
    ("PACKING_LIST", re.compile(r"\bPACKING\s+LIST\b")),
    ("CERTIFICATE_OF_ORIGIN", re.compile(r"\bCERTIFICATE\s+OF\s+ORIGIN\b")),
]
LABELS = {
    "SI": "Shipping Instruction",
    "BL": "Bill of Lading",
    "COMMERCIAL_INVOICE": "Commercial Invoice",
    "PACKING_LIST": "Packing List",
    "CERTIFICATE_OF_ORIGIN": "Certificate of Origin",
    "UNKNOWN": "unknown document",
}
_MARKER = re.compile(r"^(=== SHEET:|--- page \d+ ---)")  # separators added by readers.py
HEADER_LINES = 8  # how many non-empty lines at the top to look at


def detect_doc_type(text: str) -> str:
    """'SI', 'BL', 'COMMERCIAL_INVOICE', 'PACKING_LIST', 'CERTIFICATE_OF_ORIGIN' or 'UNKNOWN'."""
    lines = [line.strip().upper() for line in text.splitlines() if line.strip() and not _MARKER.match(line.strip())]
    for line in lines[:HEADER_LINES]:
        if _SI.search(line):  # checked first: "BILL OF LADING INSTRUCTION" also contains "BILL OF LADING"
            return "SI"
        if _BL.search(line):
            return "BL"
        for kind, pattern in _OTHER:
            if pattern.search(line):
                return kind
    return "UNKNOWN"


def wrong_kind(text: str, expected: str):
    """
    The label of the document found (e.g. 'Packing List') if this text is a KNOWN kind of document that is not
    the expected one ('SI' or 'BL'). None if it is the expected kind - or if we simply do not recognise the
    header (then we give the extractor the benefit of the doubt).
    """
    kind = detect_doc_type(text)
    if kind in (expected, "UNKNOWN"):
        return None
    return LABELS[kind]

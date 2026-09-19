"""
compare.py - compare the 7 fields of a Shipping Instruction (SI) against a draft Bill of Lading (BL).

DESIGN RULE: there is NO AI in this file. The AI reads the documents (extract.py);
plain Python decides what counts as "the same". Every decision is testable and explainable.

Every field ends up in one of three states:
    match     - same after ignoring formatting noise (case, punctuation, "Sdn Bhd" vs "Sdn. Bhd.", ...)
    mismatch  - a real difference (SI: 3 containers / BL: 4)
    review    - we can't be sure (value missing, names almost identical, ...) -> a human decides

Input : two dicts shaped like extract_fields() returns:
            {"shipper": {"value": "...", "evidence": "..."}, ...}
Output: a dict whose keys line up with Role 1's schemas.EmailResult, so the pipeline can do
            EmailResult(email_id=..., category="document_comparison", **compare(si, bl))
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Must stay in sync with schemas.FIELDS and extract.FIELD_TYPES (tests/test_compare.py checks this).
FIELDS = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)
COMPANY_FIELDS = ("shipper", "consignee", "notify_party")
PORT_FIELDS = ("port_of_loading", "port_of_discharge")

MATCH, MISMATCH, REVIEW = "match", "mismatch", "review"

# --- Knobs to tune after you see the self-eval scoreboard -----------------------------------
NEAR_MATCH_THRESHOLD = 0.90  # two names at least this similar (but not equal) -> human review
WEIGHT_TOLERANCE_KG = 0.5    # weights closer than this are "the same" (absorbs lb/MT rounding)
RELATED_PORT_NAME_SIMILARITY = 0.6  # same port code + names this similar -> review, else mismatch


# =============================================================================================
# Small helpers
# =============================================================================================
def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _clean(value):
    """None for missing/blank values, otherwise the value with surrounding spaces removed."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _as_text(value):
    """Text form of a value for FieldCheck (whose si_value / bl_value are strings)."""
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else f"{value:.2f}"
    return str(value)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# =============================================================================================
# Company names: shipper, consignee, notify party
# =============================================================================================
# Different spellings of the same legal suffix -> one canonical form. A starting list: extend it
# when the scoreboard or your hand-checks show a new variant.
_TOKEN_CANON = {
    "LIMITED": "LTD",
    "COMPANY": "CO",
    "CORPORATION": "CORP",
    "INCORPORATED": "INC",
    "BERHAD": "BHD",
    "SENDIRIAN": "SDN",
    "PRIVATE": "PVT",
    "PTE": "PVT",
}


_ORDER_PREFIX = re.compile(r"^\s*TO\s+(?:THE\s+)?ORDER(?:\s+OF)?\b[\s:.-]*")


def normalize_company(name) -> str:
    """'Sunrise Electronics Sdn. Bhd.' and 'SUNRISE ELECTRONICS SDN BHD' -> the same string."""
    text = _strip_accents(str(name)).upper()
    without_order = _ORDER_PREFIX.sub("", text)  # 'TO THE ORDER OF: X' is the consignee label, not part of the name
    if without_order.strip():  # ...but a bare 'TO ORDER' is kept as it is
        text = without_order
    text = text.replace("&", " AND ")
    text = re.sub(r"\b([A-Z])\.(?=[A-Z]\b)", r"\1", text)  # L.L.C. -> LLC
    text = re.sub(r"[\W_]+", " ", text)  # punctuation -> space (keeps letters of any script)
    return " ".join(_TOKEN_CANON.get(token, token) for token in text.split())


def compare_company(si_value, bl_value):
    a, b = normalize_company(si_value), normalize_company(bl_value)
    if a == b:
        return MATCH, None
    if _similarity(a, b) >= NEAR_MATCH_THRESHOLD:
        return REVIEW, "names are almost identical but not the same - check for a typo"
    return MISMATCH, None


_SAME_AS_WORDS = {"SAME", "CONSIGNEE", "AS CONSIGNEE", "AS PER CONSIGNEE"}


def is_same_as_consignee(value) -> bool:
    """True for 'SAME AS CONSIGNEE', 'Same as above', 'as per consignee', ..."""
    text = " ".join(re.sub(r"[^A-Z ]", " ", str(value).upper()).split())
    return text.startswith("SAME AS") or text in _SAME_AS_WORDS


# =============================================================================================
# Ports: port of loading, port of discharge
# =============================================================================================
_LOCODE_IN_PARENS = re.compile(r"\(\s*([A-Z]{2}[A-Z0-9]{3})\s*\)")  # e.g. (MYPKG), (PECLL)


def port_locode(text):
    """The UN/LOCODE port code written in brackets, e.g. 'PORT KLANG (MYPKG)' -> 'MYPKG'."""
    match = _LOCODE_IN_PARENS.search(str(text).upper())
    return match.group(1) if match else None


def normalize_port_name(text) -> str:
    """'PORT KLANG (WESTPORT), MALAYSIA (MYPKG)' -> 'PORT KLANG'; 'Port of Singapore' -> 'SINGAPORE'."""
    t = _strip_accents(str(text)).upper()
    t = re.sub(r"\([^)]*\)", " ", t)  # drop (WESTPORT), (MYPKG)
    t = t.split(",")[0]  # drop the ", MALAYSIA" part
    t = re.sub(r"[^\w\s]+", " ", t)
    t = " ".join(t.split())
    return re.sub(r"^PORT OF ", "", t)


def _bare(text) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


def compare_port(si_value, bl_value):
    """
    Names AND codes must agree. A code alone never proves a match: real BLs have shown two totally
    different ports carrying the same code (MOMBASA vs TUTICORIN, both '(KEMBA)').
    """
    code_a, code_b = port_locode(si_value), port_locode(bl_value)
    name_a, name_b = normalize_port_name(si_value), normalize_port_name(bl_value)

    # One side gives only a bare code, e.g. 'MYPKG' against 'PORT KLANG (MYPKG)'.
    if code_a and _bare(bl_value) == code_a:
        return MATCH, None
    if code_b and _bare(si_value) == code_b:
        return MATCH, None

    if name_a == name_b:
        if code_a and code_b and code_a != code_b:
            return REVIEW, f"port codes differ ({code_a} vs {code_b}) but the names are the same"
        return MATCH, None

    # From here on the port NAMES differ.
    words_a, words_b = set(name_a.split()), set(name_b.split())
    contained = bool(words_a) and bool(words_b) and (words_a <= words_b or words_b <= words_a)

    if code_a and code_b and code_a == code_b:
        # Conflicting evidence: same code, different names.
        if contained or _similarity(name_a, name_b) >= RELATED_PORT_NAME_SIMILARITY:
            return REVIEW, f"same port code ({code_a}) but the names differ ('{name_a}' vs '{name_b}')"
        return MISMATCH, f"different ports, although both carry the code {code_a}"
    if contained:
        return REVIEW, "one port name contains the other (e.g. 'KLANG' vs 'PORT KLANG') - confirm it is the same port"
    return MISMATCH, None


# =============================================================================================
# Numbers: container count, gross weight
# =============================================================================================
def compare_count(si_value, bl_value):
    try:
        a, b = int(round(float(si_value))), int(round(float(bl_value)))
    except (TypeError, ValueError):
        return REVIEW, "container count is not a number"
    return (MATCH, None) if a == b else (MISMATCH, None)


def compare_weight(si_value, bl_value):
    try:
        a, b = float(si_value), float(bl_value)
    except (TypeError, ValueError):
        return REVIEW, "gross weight is not a number"
    if abs(a - b) <= WEIGHT_TOLERANCE_KG:
        return MATCH, None
    if a > 0 and b > 0 and (abs(a / b - 1000) < 0.01 or abs(b / a - 1000) < 0.01):
        return REVIEW, "values differ by exactly 1000x - probably a unit or thousands-separator issue (MT vs kg)"
    return MISMATCH, None


# =============================================================================================
# The main entry point
# =============================================================================================
def _value(document: dict, field: str):
    entry = document.get(field)
    if isinstance(entry, dict):  # normal shape: {"value": ..., "evidence": ...}
        entry = entry.get("value")
    return _clean(entry)  # (a bare value is tolerated too)


def _has_any_value(document) -> bool:
    return bool(document) and any(_value(document, f) is not None for f in FIELDS)


def _compare_field(field: str, si_value, bl_value):
    if si_value is None and bl_value is None:
        return REVIEW, "value missing from both documents"
    if si_value is None:
        return REVIEW, "value missing from the SI"
    if bl_value is None:
        return REVIEW, "value missing from the BL"
    if field in COMPANY_FIELDS:
        return compare_company(si_value, bl_value)
    if field in PORT_FIELDS:
        return compare_port(si_value, bl_value)
    if field == "container_count":
        return compare_count(si_value, bl_value)
    return compare_weight(si_value, bl_value)


def compare(si: dict | None, bl: dict | None) -> dict:
    """
    Compare the 7 fields. Returns:
        mismatch_found  True  = at least one definite mismatch
                        False = everything matches
                        None  = no definite mismatch, but something needs a human (see needs_review)
        needs_review    True when any field is uncertain or a document could not be read
        review_reason   plain-English reason(s), or None
        fields          one {"field", "si_value", "bl_value", "match"} per field (same shape as schemas.FieldCheck)
        statuses        {field: "match" | "mismatch" | "review"}   <- use this to tell mismatch from uncertain
        notes           {field: why it needs review}
    """
    if not _has_any_value(si) or not _has_any_value(bl):
        # A real SI/BL never has ALL fields empty, so this means the document was unreadable
        # or the extraction failed. Say that once, instead of listing seven "missing" fields.
        missing = " and ".join(name for name, doc in (("SI", si), ("BL", bl)) if not _has_any_value(doc))
        return {
            "mismatch_found": None,
            "needs_review": True,
            "review_reason": f"{missing} could not be read (no fields were extracted) - retry, or check the file by hand.",
            "fields": [],
            "statuses": {},
            "notes": {},
        }

    fields, statuses, notes = [], {}, {}
    for field in FIELDS:
        si_value, bl_value = _value(si, field), _value(bl, field)
        cmp_si, cmp_bl = si_value, bl_value

        # "Notify party: SAME AS CONSIGNEE" must be replaced by the actual consignee name before comparing.
        if field == "notify_party":
            if si_value is not None and is_same_as_consignee(si_value):
                cmp_si = _value(si, "consignee")
            if bl_value is not None and is_same_as_consignee(bl_value):
                cmp_bl = _value(bl, "consignee")

        status, note = _compare_field(field, cmp_si, cmp_bl)
        statuses[field] = status
        if note:
            notes[field] = note
        fields.append(
            {
                "field": field,
                "si_value": _as_text(si_value),
                "bl_value": _as_text(bl_value),
                "match": status == MATCH,
            }
        )

    if MISMATCH in statuses.values():
        mismatch_found = True
    elif REVIEW in statuses.values():
        mismatch_found = None
    else:
        mismatch_found = False

    review_fields = [f for f in FIELDS if statuses[f] == REVIEW]
    return {
        "mismatch_found": mismatch_found,
        "needs_review": bool(review_fields),
        "review_reason": "; ".join(f"{f}: {notes[f]}" for f in review_fields) or None,
        "fields": fields,
        "statuses": statuses,
        "notes": notes,
    }
"""
verdict.py - turn ONE email's result into the exact dict the scoreboard (sample_submission.json) expects.
NO AI in here: it is a set of plain rules, so every decision is visible and easy to change.

    from ai.verdict import to_scoreboard
    entry = to_scoreboard(record)
    # {"category": "BL_COMPARISON", "status": "MISMATCH", "review_reason": None,
    #  "has_defect": True, "defect_fields": ["consignee"]}

`record` is one entry of batch_summary.json (written by experiments/run_all.py):
    status         "ok" | "mismatch" | "review" | "error" | "skipped"
    review_code    "missing_attachment" | "unreadable" | "wrong_doc_type" | "missing_value" | None
    statuses       {field: "match" | "mismatch" | "review"}
    fields         [{"field", "si_value", "bl_value", "match"}, ...]

Priority when several things are true at once (first rule that applies wins):
    1. document-level problem (missing attachment / wrong document / unreadable)  -> NEEDS_REVIEW
    2. a required value is missing from either document                          -> NEEDS_REVIEW, missing_value
    3. at least one field differs                                                -> MISMATCH
    4. otherwise                                                                 -> OK
"""
from .compare import FIELDS

CATEGORY = "BL_COMPARISON"

DOC_LEVEL_CODES = ("missing_attachment", "wrong_doc_type", "unreadable")

# Judgment calls, kept here so they are easy to flip after seeing the scoreboard:
KEEP_DEFECTS_WHEN_REVIEWING = False  # NEEDS_REVIEW entries report has_defect=False / defect_fields=[]
AMBIGUOUS_FIELDS_COUNT_AS_DEFECTS = True  # e.g. two names that are almost identical: report them as differing


def _entry(status, review_reason=None, defect_fields=(), category=CATEGORY):
    return {
        "category": category,
        "status": status,
        "review_reason": review_reason,
        "has_defect": bool(defect_fields),
        "defect_fields": list(defect_fields),
    }


def to_scoreboard(record: dict, category: str = CATEGORY) -> dict:
    status = record.get("status")
    code = record.get("review_code")

    # 1. document-level problems
    if status in ("review", "error", "skipped") and code in DOC_LEVEL_CODES:
        return _entry("NEEDS_REVIEW", code, category=category)
    if status in ("error", "skipped"):  # e.g. API failure or unsupported file type: cannot decide -> needs a human
        return _entry("NEEDS_REVIEW", "unreadable", category=category)

    fields = record.get("fields") or []
    statuses = record.get("statuses") or {}
    differing = [f for f in FIELDS if statuses.get(f) == "mismatch"]
    ambiguous = [f for f in FIELDS if statuses.get(f) == "review"]
    missing = [row["field"] for row in fields if row["si_value"] is None or row["bl_value"] is None]
    defects = [f for f in FIELDS if f in differing or (AMBIGUOUS_FIELDS_COUNT_AS_DEFECTS and f in ambiguous and f not in missing)]

    # 2. a required value is missing
    if missing:
        return _entry("NEEDS_REVIEW", "missing_value", defects if KEEP_DEFECTS_WHEN_REVIEWING else (), category)
    # 3. real differences
    if defects:
        return _entry("MISMATCH", None, defects, category)
    # 4. all seven fields match
    return _entry("OK", None, (), category)

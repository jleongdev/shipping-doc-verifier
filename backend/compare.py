from .schemas import FIELDS

_NUMERIC = {"container_count", "gross_weight_kg"}


def _norm(field: str, value):
    """Normalize a value so trivial formatting differences don't count as mismatches."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if field in _NUMERIC:
        s = s.replace(",", "").replace("kg", "").strip()
        try:
            return str(float(s))          # "3"->"3.0", "12,450"->"12450.0", "3.0"->"3.0"
        except ValueError:
            return s
    return " ".join(s.split())            # collapse internal whitespace for text fields


def compare_fields(si: dict, bl: dict):
    """Compare the 7 fields between SI and BL.
    Returns (status, has_defect, defect_fields, review_reason)."""
    defect_fields = []
    for f in FIELDS:
        sv, bv = _norm(f, si.get(f)), _norm(f, bl.get(f))
        if sv is None and bv is None:
            continue                       # both absent → nothing to compare
        if sv is None or bv is None:
            # present on one side, missing on the other → can't decide this field
            return "NEEDS_REVIEW", None, [], "missing_value"
        if sv != bv:
            defect_fields.append(f)
    if defect_fields:
        return "MISMATCH", True, defect_fields, None
    return "OK", False, [], None

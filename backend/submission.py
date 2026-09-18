from .schemas import EmailResult

def build_submission(results: list[EmailResult]) -> dict:
    """One object keyed by email_id. TODO: match sample_submission.json keys exactly."""
    out = {}
    for r in results:
        entry = {"category": r.category}
        if r.category == "document_comparison":
            entry["mismatch_found"] = r.mismatch_found
            entry["mismatched_fields"] = [c.field for c in r.fields if not c.match]
        out[r.email_id] = entry
    return out

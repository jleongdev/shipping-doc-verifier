"""Builds the self-evaluation submission from pipeline results.

Matches sample_submission.json: one JSON object keyed by email_id, every email
present, all five keys on each entry, key order identical to the sample.
"""

import json
from .schemas import EmailResult


def build_submission(results: list[EmailResult]) -> dict:
    """Convert pipeline results into the exact submission shape."""
    submission: dict[str, dict] = {}
    for r in results:
        submission[r.email_id] = {
            "category": r.category,
            "status": r.status,
            "review_reason": r.review_reason,
            "defect_fields": list(r.defect_fields or []),
            "has_defect": r.has_defect,
        }
    return submission


def write_submission(results: list[EmailResult], path: str = "submission.json") -> dict:
    """Build the submission and write it to `path`. Returns the payload."""
    submission = build_submission(results)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(submission, f, indent=2)
    return submission

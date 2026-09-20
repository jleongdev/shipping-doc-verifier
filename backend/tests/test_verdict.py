"""
Tests for backend/ai/verdict.py: our results -> the scoreboard's exact vocabulary
(status OK | MISMATCH | NEEDS_REVIEW, review_reason wrong_doc_type | missing_attachment | unreadable | missing_value).

    python -m pytest backend/tests -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from ai import verdict  # noqa: E402
from ai.compare import FIELDS, compare  # noqa: E402
from ai.verdict import to_scoreboard  # noqa: E402

BASE = dict(shipper="ACME SDN BHD", consignee="BETA LTD", notify_party="BETA LTD", port_of_loading="PORT KLANG (MYPKG)",
            port_of_discharge="CALLAO, PERU (PECLL)", container_count=1, gross_weight_kg=21577)


def doc(**over):
    return {k: {"value": v, "evidence": ""} for k, v in {**BASE, **over}.items()}


def record_from(si, bl):
    """What run_all.py stores for an email that was extracted and compared."""
    r = compare(si, bl)
    flagged = [f for f in FIELDS if r["statuses"][f] == "mismatch"]
    missing = [x["field"] for x in r["fields"] if x["si_value"] is None or x["bl_value"] is None]
    status = "mismatch" if flagged and not missing else ("review" if r["needs_review"] else "ok")
    return {"status": status, "flagged": flagged, "review_code": "missing_value" if missing else None,
            "statuses": r["statuses"], "fields": r["fields"]}


def test_identical_documents_are_ok():
    assert to_scoreboard(record_from(doc(), doc())) == {
        "category": "BL_COMPARISON", "status": "OK", "review_reason": None, "has_defect": False, "defect_fields": []}


def test_differences_become_mismatch_with_the_fields_in_the_standard_order():
    entry = to_scoreboard(record_from(doc(), doc(container_count=2, consignee="OTHER CORP")))
    assert entry["status"] == "MISMATCH"
    assert entry["has_defect"] is True
    assert entry["defect_fields"] == ["consignee", "container_count"]
    assert entry["review_reason"] is None


def test_missing_value_needs_review():
    entry = to_scoreboard(record_from(doc(), doc(notify_party=None)))
    assert (entry["status"], entry["review_reason"]) == ("NEEDS_REVIEW", "missing_value")
    assert entry["has_defect"] is False and entry["defect_fields"] == []


def test_missing_value_wins_over_a_mismatch():
    entry = to_scoreboard(record_from(doc(), doc(notify_party=None, container_count=2)))
    assert (entry["status"], entry["review_reason"]) == ("NEEDS_REVIEW", "missing_value")


def test_document_level_problems_use_the_readme_codes():
    for code in ("missing_attachment", "wrong_doc_type", "unreadable"):
        entry = to_scoreboard({"status": "review", "review_code": code})
        assert (entry["status"], entry["review_reason"], entry["has_defect"]) == ("NEEDS_REVIEW", code, False)


def test_api_error_or_unsupported_file_is_needs_review_not_a_guess():
    for status in ("error", "skipped"):
        entry = to_scoreboard({"status": status, "review_code": None})
        assert (entry["status"], entry["review_reason"]) == ("NEEDS_REVIEW", "unreadable")


def test_ambiguous_field_counts_as_a_defect_by_default():
    record = record_from(doc(shipper="SUNRISE ELECTRONICS SDN BHD"), doc(shipper="SUNRISE ELECTRONIC SDN BHD"))
    assert record["statuses"]["shipper"] == "review"
    entry = to_scoreboard(record)
    assert (entry["status"], entry["defect_fields"]) == ("MISMATCH", ["shipper"])


def test_ambiguous_fields_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(verdict, "AMBIGUOUS_FIELDS_COUNT_AS_DEFECTS", False)
    record = record_from(doc(shipper="SUNRISE ELECTRONICS SDN BHD"), doc(shipper="SUNRISE ELECTRONIC SDN BHD"))
    assert to_scoreboard(record)["status"] == "OK"


def test_keys_match_sample_submission_exactly():
    assert set(to_scoreboard(record_from(doc(), doc()))) == {"category", "status", "review_reason", "has_defect", "defect_fields"}

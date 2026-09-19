"""
Tests for backend/ai/compare.py.  Run from the project root:

    python -m pytest backend/tests -v

Each test says what a human checker would conclude. When you meet a new tricky case in the real
data, add it here FIRST (watch it fail), then fix compare.py until it passes.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/  ->  `import ai...`, `import schemas`

from ai import compare as compare_module  # noqa: E402
from ai.compare import (  # noqa: E402
    FIELDS,
    compare,
    compare_company,
    compare_port,
    compare_weight,
    is_same_as_consignee,
    normalize_company,
    normalize_port_name,
)
from ai.extract import FIELD_TYPES  # noqa: E402

# The real values from email_001 (SI and BL agree on all 7 fields).
EMAIL_001 = {
    "shipper": "APRIL FAR EAST (M) SDN BHD",
    "consignee": "MOORIM SP CO., LTD",
    "notify_party": "UAB NOVAKOPA",
    "port_of_loading": "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)",
    "port_of_discharge": "CALLAO, PERU (PECLL)",
    "container_count": 1,
    "gross_weight_kg": 21577,
}


def doc(**overrides):
    """Build an extraction result like extract_fields() returns, starting from email_001."""
    values = {**EMAIL_001, **overrides}
    return {name: {"value": value, "evidence": f"<text for {name}>"} for name, value in values.items()}


def statuses(si, bl):
    return compare(si, bl)["statuses"]


# --- the basics ------------------------------------------------------------------------------
def test_identical_documents_report_no_mismatch():
    result = compare(doc(), doc())
    assert result["mismatch_found"] is False
    assert result["needs_review"] is False
    assert result["review_reason"] is None
    assert all(result["statuses"][f] == "match" for f in FIELDS)


def test_brief_example_only_container_count_is_flagged():
    """From the brief: SI 3 containers / 22,000 kg vs BL 4 containers / 22,000 kg."""
    result = compare(doc(container_count=3, gross_weight_kg=22000), doc(container_count=4, gross_weight_kg=22000))
    assert result["mismatch_found"] is True
    flagged = [f for f in FIELDS if result["statuses"][f] == "mismatch"]
    assert flagged == ["container_count"]
    count = next(f for f in result["fields"] if f["field"] == "container_count")
    assert (count["si_value"], count["bl_value"], count["match"]) == ("3", "4", False)


def test_wrong_weight_is_flagged():
    assert statuses(doc(), doc(gross_weight_kg=21557))["gross_weight_kg"] == "mismatch"


def test_different_port_is_flagged():
    bl = doc(port_of_discharge="BUENAVENTURA, COLOMBIA (COBUN)")
    assert statuses(doc(), bl)["port_of_discharge"] == "mismatch"


# --- company names: formatting noise must NOT raise a false alarm ------------------------------
@pytest.mark.parametrize(
    "si_name, bl_name",
    [
        ("Sunrise Electronics Sdn Bhd", "SUNRISE ELECTRONICS SDN. BHD."),
        ("Pacific Retail Pte Ltd", "Pacific Retail Pte. Ltd."),
        ("MOORIM SP CO., LTD", "Moorim SP Company Limited"),
        ("Smith & Sons Trading", "SMITH AND SONS TRADING"),
        ("Gulf Traders L.L.C.", "GULF TRADERS LLC"),
        ("APRIL FAR EAST (M) SDN BHD", "  April  Far East (M)  Sdn Bhd "),
        ("Société Générale Shipping", "SOCIETE GENERALE SHIPPING"),
    ],
)
def test_company_formatting_differences_are_a_match(si_name, bl_name):
    assert compare_company(si_name, bl_name)[0] == "match"


def test_truly_different_company_is_a_mismatch():
    assert compare_company("MOORIM SP CO., LTD", "HANIL TRADING CO., LTD")[0] == "mismatch"


def test_near_identical_name_goes_to_human_review_not_mismatch():
    status, note = compare_company("SUNRISE ELECTRONICS SDN BHD", "SUNRISE ELECTRONIC SDN BHD")
    assert status == "review"
    assert "typo" in note


def test_normalize_company_examples():
    assert normalize_company("MOORIM SP CO., LTD") == "MOORIM SP CO LTD"
    assert normalize_company("Pacific Retail Pte. Ltd.") == "PACIFIC RETAIL PVT LTD"


# --- notify party: "same as consignee" ---------------------------------------------------------
@pytest.mark.parametrize("text", ["SAME AS CONSIGNEE", "Same as consignee.", "same as above", "AS PER CONSIGNEE", "Consignee"])
def test_same_as_consignee_is_recognised(text):
    assert is_same_as_consignee(text)


def test_same_as_consignee_is_resolved_before_comparing():
    si = doc(notify_party="SAME AS CONSIGNEE")  # consignee: MOORIM SP CO., LTD
    bl = doc(notify_party="Moorim SP Co., Ltd")
    assert statuses(si, bl)["notify_party"] == "match"


def test_same_as_consignee_but_bl_lists_someone_else_is_a_mismatch():
    si = doc(notify_party="SAME AS CONSIGNEE")
    bl = doc(notify_party="UAB NOVAKOPA")
    assert statuses(si, bl)["notify_party"] == "mismatch"


# --- ports -------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "si_port, bl_port",
    [
        ("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)", "PORT KLANG"),
        ("Port Klang, Malaysia", "PORT KLANG"),
        ("PORT KLANG (MYPKG)", "MYPKG"),
        ("Port of Singapore", "SINGAPORE"),
        ("CALLAO, PERU (PECLL)", "Callao"),
    ],
)
def test_port_formatting_differences_are_a_match(si_port, bl_port):
    assert compare_port(si_port, bl_port)[0] == "match"


def test_port_name_contained_in_the_other_needs_review():
    assert compare_port("KLANG", "PORT KLANG")[0] == "review"


def test_same_port_name_but_different_codes_needs_review():
    assert compare_port("PORT KLANG (MYPKG)", "PORT KLANG (MYPKW)")[0] == "review"


# Regression tests from REAL data: a shared port code must never hide a different port name.
def test_email_013_same_code_but_different_port_is_a_mismatch():
    status, note = compare_port("MOMBASA, KENYA (KEMBA)", "TUTICORIN, INDIA (KEMBA)")
    assert status == "mismatch"
    assert "KEMBA" in note


def test_email_025_same_code_but_different_port_is_a_mismatch():
    assert compare_port("FREMANTLE, AUSTRALIA (AUFRE)", "BUSAN, SOUTH KOREA (AUFRE)")[0] == "mismatch"


def test_same_port_code_with_related_names_needs_review():
    assert compare_port("SINGAPORE (SGSIN)", "SINGAPORE PORT (SGSIN)")[0] == "review"


def test_different_codes_and_different_names_is_a_mismatch():
    assert compare_port("CALLAO, PERU (PECLL)", "BUENAVENTURA, COLOMBIA (COBUN)")[0] == "mismatch"


def test_email_025_full_result_flags_port_and_container_count():
    si = doc(port_of_discharge="FREMANTLE, AUSTRALIA (AUFRE)", container_count=6)
    bl = doc(port_of_discharge="BUSAN, SOUTH KOREA (AUFRE)", container_count=5)
    result = compare(si, bl)
    flagged = [f for f in FIELDS if result["statuses"][f] == "mismatch"]
    assert flagged == ["port_of_discharge", "container_count"]


def test_email_004_to_the_order_of_a_different_party_is_a_mismatch():
    assert compare_company("EAST BRIGHT FZ-LLC", "TO THE ORDER OF UAB NOVAKOPA")[0] == "mismatch"


def test_normalize_port_name():
    assert normalize_port_name("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)") == "PORT KLANG"


# --- weight ------------------------------------------------------------------------------------
def test_weight_int_and_float_match():
    assert compare_weight(22000, 22000.0)[0] == "match"


def test_weight_rounding_from_pounds_is_not_a_mismatch():
    assert compare_weight(21999.9, 22000)[0] == "match"  # 48,502 lb = 21,999.9 kg


def test_weight_off_by_1000x_goes_to_review():
    assert compare_weight(22, 22000)[0] == "review"


# --- uncertainty: never guess ---------------------------------------------------------------------
def test_missing_value_needs_review_not_a_match_or_mismatch():
    result = compare(doc(), doc(notify_party=None))
    assert result["statuses"]["notify_party"] == "review"
    assert result["needs_review"] is True
    assert result["mismatch_found"] is None  # undecided: a human must look
    assert "notify_party" in result["review_reason"]


def test_definite_mismatch_and_uncertain_field_are_both_reported():
    result = compare(doc(), doc(container_count=2, notify_party=None))
    assert result["mismatch_found"] is True
    assert result["needs_review"] is True


def test_unreadable_document_needs_review_and_does_not_crash():
    for si, bl in [(None, doc()), (doc(), {}), (None, None)]:
        result = compare(si, bl)
        assert result["needs_review"] is True
        assert result["mismatch_found"] is None
        assert result["fields"] == []


def test_blank_strings_count_as_missing():
    assert statuses(doc(), doc(shipper="   "))["shipper"] == "review"


# --- plumbing: does the output fit the team's schemas.py? ---------------------------------------
def test_field_lists_agree_everywhere():
    import schemas

    assert tuple(schemas.FIELDS) == FIELDS
    assert tuple(FIELD_TYPES) == FIELDS


def test_result_fits_role_1s_email_result_schema():
    import schemas

    result = compare(doc(), doc(container_count=2))
    email_result = schemas.EmailResult(email_id="email_001", category="document_comparison", **result)
    assert email_result.mismatch_found is True
    assert len(email_result.fields) == 7
    assert compare_module.MISMATCH == "mismatch"


# --- regression from real data: email_013's BL came back with every field empty ------------------------
def test_document_with_no_extracted_fields_is_reported_as_unreadable():
    empty = {name: {"value": None, "evidence": None} for name in FIELDS}
    result = compare(doc(), empty)
    assert result["needs_review"] is True
    assert result["mismatch_found"] is None  # never "No mismatch detected" for a document we could not read
    assert result["fields"] == []
    assert result["review_reason"].startswith("BL could not be read")


def test_both_documents_empty_names_both():
    empty = {name: {"value": None, "evidence": None} for name in FIELDS}
    assert compare(empty, empty)["review_reason"].startswith("SI and BL could not be read")


def test_bare_values_instead_of_value_objects_are_tolerated():
    flat = dict(EMAIL_001)  # {"shipper": "APRIL ...", ...} with no {"value": ...} wrapper
    assert compare(flat, doc())["mismatch_found"] is False


# --- regression from real data: email_004 ("To the Order of" is a consignee label in this dataset) ------
def test_to_the_order_of_prefix_is_label_noise_when_the_party_is_the_same():
    assert compare_company("TO THE ORDER OF: UAB NOVAKOPA", "UAB NOVAKOPA")[0] == "match"


def test_bare_to_order_is_not_erased():
    assert normalize_company("TO ORDER") == "TO ORDER"


def test_email_004_full_result_flags_consignee_and_notify_party_only():
    si = doc(shipper="APRIL FAR EAST (M) SDN BHD", consignee="EAST BRIGHT FZ-LLC", notify_party="EAST BRIGHT FZ-LLC",
             port_of_loading="NANTONG, CHINA (CNNTG)", port_of_discharge="KARACHI, PAKISTAN (PKKHI)",
             container_count=6, gross_weight_kg=131058)
    bl = doc(shipper="APRIL FAR EAST (M) SDN BHD", consignee="TO THE ORDER OF: UAB NOVAKOPA", notify_party="UAB NOVAKOPA",
             port_of_loading="NANTONG, CHINA (CNNTG)", port_of_discharge="KARACHI, PAKISTAN (PKKHI)",
             container_count=6, gross_weight_kg=131058)
    result = compare(si, bl)
    assert [f for f in FIELDS if result["statuses"][f] == "mismatch"] == ["consignee", "notify_party"]
    assert result["needs_review"] is False
"""
Tests for the retry / clean-up logic in backend/ai/extract.py.
A FAKE Claude client is used, so these tests cost nothing and never touch the internet.

    python -m pytest backend/tests -v
"""
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from ai import extract  # noqa: E402

GOOD = {
    "shipper": {"value": "ACME SDN BHD", "evidence": "Shipper: ACME SDN BHD"},
    "consignee": {"value": "BETA LTD", "evidence": "Consignee: BETA LTD"},
    "notify_party": {"value": None, "evidence": None},  # a document may legitimately lack a field
    "port_of_loading": {"value": "PORT KLANG (MYPKG)", "evidence": "POL: PORT KLANG (MYPKG)"},
    "port_of_discharge": {"value": "CALLAO (PECLL)", "evidence": "POD: CALLAO (PECLL)"},
    "container_count": {"value": 1, "evidence": "1 x 40'HC"},
    "gross_weight_kg": {"value": 21577, "evidence": "21,577 KG"},
}
EMPTY = {name: {"value": None, "evidence": None} for name in extract.FIELD_TYPES}


class FakeClient:
    """Stands in for anthropic.Anthropic(). `replies` are the tool inputs to return, in order (None = no tool_use block)."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.messages = self  # so that fake.messages.create(...) works

    def create(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        content = [] if reply is None else [SimpleNamespace(type="tool_use", input=reply)]
        return SimpleNamespace(content=content, stop_reason="end_turn", usage=SimpleNamespace(output_tokens=7))


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda seconds: None)


def use(monkeypatch, replies):
    fake = FakeClient(replies)
    monkeypatch.setattr(extract, "_get_client", lambda: fake)
    return fake


def test_good_answer_is_returned_after_one_call(monkeypatch):
    fake = use(monkeypatch, [GOOD])
    result = extract.extract_fields("text", "SI")
    assert fake.calls == 1
    assert result["shipper"]["value"] == "ACME SDN BHD"


def test_document_missing_some_fields_is_accepted_without_retry(monkeypatch):
    fake = use(monkeypatch, [GOOD])  # notify_party is null, which is legitimate
    result = extract.extract_fields("text", "BL")
    assert fake.calls == 1
    assert result["notify_party"]["value"] is None


def test_empty_answer_is_retried_and_the_second_answer_is_used(monkeypatch):
    """The email_013 situation: first response has every field empty."""
    fake = use(monkeypatch, [EMPTY, GOOD])
    result = extract.extract_fields("text", "BL")
    assert fake.calls == 2
    assert result["consignee"]["value"] == "BETA LTD"


def test_missing_tool_block_is_retried(monkeypatch):
    fake = use(monkeypatch, [None, GOOD])
    assert extract.extract_fields("text", "BL")["shipper"]["value"] == "ACME SDN BHD"
    assert fake.calls == 2


def test_gives_up_after_max_attempts_and_returns_an_all_empty_result(monkeypatch):
    fake = use(monkeypatch, [EMPTY] * extract.MAX_ATTEMPTS)
    result = extract.extract_fields("text", "BL")
    assert fake.calls == extract.MAX_ATTEMPTS
    assert not extract.has_any_value(result)
    assert set(result) == set(extract.FIELD_TYPES)  # same shape as always, so compare() can flag it


def test_bare_values_are_wrapped_into_the_standard_shape(monkeypatch):
    use(monkeypatch, [{"shipper": "ACME SDN BHD", "container_count": 2}])
    result = extract.extract_fields("text", "SI")
    assert result["shipper"] == {"value": "ACME SDN BHD", "evidence": None}
    assert result["container_count"]["value"] == 2
    assert result["consignee"] == {"value": None, "evidence": None}  # absent field filled in


def test_pauses_between_retries_but_not_after_the_last_attempt(monkeypatch):
    pauses = []
    monkeypatch.setattr(extract.time, "sleep", pauses.append)
    use(monkeypatch, [EMPTY, EMPTY, EMPTY])
    extract.extract_fields("text", "BL")
    assert pauses == [extract.RETRY_PAUSE_SECONDS * 1, extract.RETRY_PAUSE_SECONDS * 2]


def test_failure_warning_says_what_claude_returned(monkeypatch, caplog):
    use(monkeypatch, [EMPTY, GOOD])
    with caplog.at_level(logging.WARNING, logger="ai.extract"):
        extract.extract_fields("text", "BL")
    assert "stop_reason=end_turn" in caplog.text
    assert "attempt 1 of" in caplog.text
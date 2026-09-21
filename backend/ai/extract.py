# ai/extract.py  (role 3 owns this — hardened for the compare step)
from .claude import complete_json
from ..schemas import FIELDS

_SYSTEM = f"""Extract these shipping fields from the document text: {FIELDS}.
The SI and BL often label the same field differently — align by MEANING, not header text
(e.g. "Load Port" -> port_of_loading, "Exporter" -> shipper, "Notify" -> notify_party).

Reply ONLY as JSON with those exact keys. Rules:
- Copy text values verbatim (trimmed).
- container_count: just the integer as a string, e.g. "3".
- gross_weight_kg: just the numeric kg as a string, no units or thousands separators, e.g. "12450.5".
- Use null if a field is genuinely absent. Never guess."""


def extract_fields(doc_text: str) -> dict:
    data = complete_json(_SYSTEM, doc_text, max_tokens=1024)
    # Guarantee all 7 keys exist, clean values, drop anything unexpected.
    return {f: _clean(data.get(f)) for f in FIELDS}


def _clean(value):
    if value is None:
        return None
    s = str(value).strip()
    return s or None

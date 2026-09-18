# ai/extract.py  (role 3 owns this)
from .claude import complete_json
from ..schemas import FIELDS

_SYSTEM = f"""Extract these shipping fields from the document text: {FIELDS}.
Normalize synonym labels (e.g. "Load Port" -> port_of_loading).
Reply ONLY as JSON with those exact keys; use null if a field is absent."""

def extract_fields(doc_text: str) -> dict:
    return complete_json(_SYSTEM, doc_text, max_tokens=1024)

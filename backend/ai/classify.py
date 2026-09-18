# ai/classify.py  (role 2 owns this)
from .claude import complete_json, MODEL_CHEAP

_SYSTEM = """Classify a shipping-ops email into exactly one category:
document_comparison, new_si_request, invoice_query, general_message, spam.
Reply ONLY as JSON: {"category": "...", "confidence": 0.0, "reason": "..."}"""

def classify_email(subject: str, body: str) -> dict:
    return complete_json(_SYSTEM, f"Subject: {subject}\n\n{body}", model=MODEL_CHEAP, max_tokens=256)

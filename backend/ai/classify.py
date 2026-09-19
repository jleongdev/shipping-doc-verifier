import math

from .claude import complete_json, MODEL_CHEAP


ALLOWED_CATEGORIES = {
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
}


_SYSTEM = """You classify shipping-operations emails into exactly one category.

Allowed categories:

1. BL_COMPARISON
   - The sender wants a draft Bill of Lading (BL) checked, confirmed, verified,
     or compared against a Shipping Instruction (SI).
   - Includes requests to review or confirm draft BL details.

2. SI_REQUEST
   - The email requests, provides, updates, or discusses a Shipping Instruction (SI).
   - The main intent is obtaining or handling the SI, not comparing SI vs BL.

3. INVOICE_QUERY
   - The email is mainly about invoices, billing, charges, payment, freight charges,
     cancellation of invoices, GR, detention, demurrage, or other billing issues.

4. GENERAL
   - Normal operational communication that does not fit the categories above.
   - Includes updates, reminders, reports, notifications, HR/general messages.

5. SPAM
   - Phishing, scams, fake prizes, suspicious promotions, fraudulent requests,
     or clearly irrelevant unsolicited email.

Important rules:
- Classify based on the main actionable intent of the newest email message.
- Do not let signatures, quoted email history, warning banners, or unrelated boilerplate
  override the current message's intent.
- Choose exactly one category.
- The category MUST be one of: BL_COMPARISON, SI_REQUEST, INVOICE_QUERY, GENERAL, SPAM
  (exact uppercase spelling).
- confidence must be a number from 0.0 to 1.0.
- If two categories seem possible, choose the one that best represents what the sender
  currently wants the recipient to do.

Reply ONLY with valid JSON in this exact structure:
{"category": "...", "confidence": 0.0, "reason": "..."}
"""


def classify_email(subject: str, body: str) -> dict:
    result = complete_json(
        _SYSTEM,
        f"Subject: {subject}\n\n{body}",
        model=MODEL_CHEAP,
        max_tokens=256
    )

    category = result.get("category")
    confidence = result.get("confidence", 0.0)

    if category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"Invalid category returned by model: {category}"
        )

    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.0

    # Reject NaN and Infinity.
    if not math.isfinite(confidence):
        confidence = 0.0

    # Clamp normal numeric values to 0.0–1.0.
    confidence = max(0.0, min(1.0, confidence))

    result["category"] = category
    result["confidence"] = confidence

    return result
from .schemas import EmailResult, FieldCheck, FIELDS
from .ai.classify import classify_email
from .ai.extract import extract_fields

CONFIDENCE_FLOOR = 0.6   # below this -> send to human review


def _norm(v):
    return " ".join(str(v).strip().lower().split()) if v is not None else None


def _compare(si: dict, bl: dict) -> list[FieldCheck]:
    checks = []
    for f in FIELDS:
        sv, bv = si.get(f), bl.get(f)
        matched = sv is not None and bv is not None and _norm(sv) == _norm(bv)
        checks.append(FieldCheck(field=f, si_value=str(sv) if sv is not None else None,
                                 bl_value=str(bv) if bv is not None else None, match=matched))
    return checks


def process_email(email: dict, inbox) -> EmailResult:
    """Run one email end-to-end. Never crashes the batch: on failure it flags
    the email for human review with the reason (the brief rewards this)."""
    email_id = email["email_id"]   # TODO: confirm key name against the real data
    try:
        c = classify_email(email.get("subject", ""), email.get("body", ""))
        category, confidence = c["category"], float(c.get("confidence", 1.0))

        # Only comparison requests continue past classification
        if category != "document_comparison":
            return EmailResult(email_id=email_id, category=category, confidence=confidence,
                               needs_review=confidence < CONFIDENCE_FLOOR,
                               review_reason="low classification confidence" if confidence < CONFIDENCE_FLOOR else None)

        # TODO: confirm how the email points to its SI vs BL attachments
        si_text = inbox.read_text(email["si_path"])
        bl_text = inbox.read_text(email["bl_path"])
        si, bl = extract_fields(si_text), extract_fields(bl_text)

        checks = _compare(si, bl)
        # If any field couldn't be read from either doc, escalate instead of guessing
        unreadable = [c.field for c in checks if c.si_value is None or c.bl_value is None]
        return EmailResult(
            email_id=email_id, category=category, confidence=confidence,
            mismatch_found=any(not c.match for c in checks),
            fields=checks,
            needs_review=bool(unreadable) or confidence < CONFIDENCE_FLOOR,
            review_reason=(f"missing fields: {unreadable}" if unreadable else None),
        )
    except Exception as e:
        # Fail visibly -> human review, don't drop the email
        return EmailResult(email_id=email.get("email_id", "unknown"),
                           category="general_message", needs_review=True,
                           review_reason="processing error", error=str(e))


def process_all(inbox) -> list[EmailResult]:
    return [process_email(email, inbox) for email in inbox]

import json
from pathlib import Path
from .schemas import EmailResult, FIELDS
from .ai.classify import classify_email
from .ai.extract import extract_fields   # role 3 — swap in when ready


# ---------- find an email's SI and BL attachments ----------

def _attachment_names(email: dict) -> list[str]:
    """Pull attachment paths off an email record.
    TODO: confirm the real key by opening one inbox/email_XXX.json, then simplify."""
    for key in ("attachments", "attachment_paths", "files", "docs"):
        val = email.get(key)
        if val:
            out = []
            for a in val:
                out.append(a if isinstance(a, str)
                           else (a.get("path") or a.get("filename") or a.get("name")))
            return [p for p in out if p]
    return []

def _role_of(name: str):
    """SI or BL? Bundle names them email_004_SI.txt / email_004_BL.txt."""
    stem = Path(name).stem.lower()
    if stem.endswith("si") or "_si" in stem or "shipping_instruction" in stem:
        return "SI"
    if stem.endswith("bl") or "_bl" in stem or "bill_of_lading" in stem:
        return "BL"
    return None

def find_si_bl(email: dict):
    si = bl = None
    for name in _attachment_names(email):
        role = _role_of(name)
        if role == "SI" and si is None: si = name
        if role == "BL" and bl is None: bl = name
    # Fallback to the bundle naming convention if the record didn't list them
    eid = email.get("email_id", "")
    return si or f"attachments/{eid}_SI.txt", bl or f"attachments/{eid}_BL.txt"


# ---------- read an attachment into text ----------

def read_document(inbox, path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return json.dumps(json.loads(inbox.read_text(path)), indent=2)
    # .txt now; extend to excel/pdf/docx in the advanced stage
    return inbox.read_text(path)


# ---------- compare + orchestrate ----------

_NUMERIC = {"container_count", "gross_weight_kg"}

def _norm(field, value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if field in _NUMERIC:
        s = s.replace(",", "").replace("kg", "").strip()
        try:
            return str(float(s))
        except ValueError:
            return s
    return " ".join(s.split())


def _stub_extract(text: str) -> dict:
    """TEMPORARY until role 3's extract_fields lands."""
    return {f: None for f in FIELDS}

def process_email(email: dict, inbox) -> EmailResult:
    email_id = email.get("email_id", "unknown")
    try:
        c = classify_email(email.get("subject", ""), email.get("body", ""))
        category, confidence = c["category"], float(c.get("confidence", 1.0))

        if category != "BL_COMPARISON":
            return EmailResult(email_id=email_id, category=category, confidence=confidence)

        si_path, bl_path = find_si_bl(email)
        try:
            si_text = read_document(inbox, si_path)
            bl_text = read_document(inbox, bl_path)
        except Exception:
            return EmailResult(email_id=email_id, category=category, confidence=confidence,
                               status="NEEDS_REVIEW", review_reason="missing_attachment")

        si = extract_fields(si_text)
        bl = extract_fields(bl_text)

        missing = [f for f in FIELDS if si.get(f) is None or bl.get(f) is None]
        if missing:
            return EmailResult(email_id=email_id, category=category, confidence=confidence,
                               status="NEEDS_REVIEW", review_reason="missing_value")

        defects = [f for f in FIELDS if _norm(f, si[f]) != _norm(f, bl[f])]
        if defects:
            return EmailResult(email_id=email_id, category=category, confidence=confidence,
                               status="MISMATCH", has_defect=True, defect_fields=defects)
        return EmailResult(email_id=email_id, category=category, confidence=confidence,
                           status="OK", has_defect=False)

    except Exception as e:
        return EmailResult(email_id=email_id, category="GENERAL",
                           status="NEEDS_REVIEW", review_reason="unreadable", error=str(e))

def process_all(inbox) -> list[EmailResult]:
    return [process_email(email, inbox) for email in inbox]

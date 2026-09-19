"""
try_extract.py - run extract + compare on one or more emails and print what a human checker would want to see.

Run it from the project root (the shipping-doc-verifier folder):

    python backend/experiments/try_extract.py                              # first email that has attachments
    python backend/experiments/try_extract.py email_004                    # one email
    python backend/experiments/try_extract.py email_004 email_009 email_013   # several emails
"""
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths + imports that work no matter where you run the script from.
# This file lives at <ROOT>/backend/experiments/try_extract.py. Python only searches the script's
# own folder for imports, so we add backend/ to the search path (for loader, schemas, ai.*).
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # shipping-doc-verifier/
DATA_DIR = ROOT / "data"
sys.path.insert(0, str(ROOT / "backend"))

import anthropic  # noqa: E402
from ai.compare import FIELDS, compare  # noqa: E402  (backend/ai/compare.py)
from ai.extract import MODEL, extract_fields  # noqa: E402  (backend/ai/extract.py)
from dotenv import load_dotenv  # noqa: E402
from loader import Inbox  # noqa: E402  (backend/loader.py)

_key_before = os.environ.get("ANTHROPIC_API_KEY")  # a key already set in Windows, if any
load_dotenv(ROOT / ".env", override=True)  # the key in .env wins over anything already set
if not os.getenv("ANTHROPIC_API_KEY"):
    sys.exit(
        "ANTHROPIC_API_KEY not found.\n"
        f"Check that {ROOT / '.env'} exists and contains a line like:\n"
        "ANTHROPIC_API_KEY=sk-ant-your-key-here"
    )


def describe_key() -> None:
    """Print a safe summary of the key in use (start, end, length) and warn about common mistakes."""
    key = os.environ["ANTHROPIC_API_KEY"]
    print(f"API key in use: {key[:10]}...{key[-4:]}  (length {len(key)})   model: {MODEL}")
    if _key_before and _key_before != key:
        print("  note: a DIFFERENT key is also set in your Windows environment variables; the one from .env is used.")
    if "your-key" in key.lower() or "here" in key.lower():
        print("  WARNING: this looks like the placeholder from .env.example, not a real key.")
    elif not key.startswith("sk-ant-"):
        print("  WARNING: Anthropic API keys start with 'sk-ant-'. This one does not.")
    elif len(key) < 60:
        print("  WARNING: this is much shorter than a real key. It was probably cut off when copying.")


def pick_attachment(attachments: list, tag: str):
    """Return the attachment path whose filename ends in _SI or _BL (e.g. email_001_SI.txt)."""
    for path in attachments:
        if f"_{tag}." in path.upper():
            return path
    return None


def show_value(text_si, text_bl, status) -> str:
    if text_si == text_bl:
        return f"{text_si}"
    if status == "match":
        return f"SI '{text_si}' / BL '{text_bl}'   (formatting difference ignored)"
    return f"SI '{text_si}' / BL '{text_bl}'"


def check_email(inbox: Inbox, email_id: str) -> None:
    email = inbox.get(email_id)
    print("\n" + "=" * 78)
    print(f"{email['email_id']}  |  {email['subject']}")

    si_path = pick_attachment(email["attachments"], "SI")
    bl_path = pick_attachment(email["attachments"], "BL")
    if not si_path or not bl_path:
        print("  skipped: this email does not have BOTH an SI and a BL attachment.")
        return
    # Only plain-text files for now. Some emails have .xlsx / .docx / .pdf - we add those later.
    for path in (si_path, bl_path):
        if not path.lower().endswith(".txt"):
            print(f"  skipped: {path} is not a .txt file yet.")
            return

    si = extract_fields(inbox.read_text(si_path), "SI")
    bl = extract_fields(inbox.read_text(bl_path), "BL")
    result = compare(si, bl)

    labels = {"match": "OK", "mismatch": "DIFF", "review": "REVIEW"}
    for row in result["fields"]:
        f = row["field"]
        status = result["statuses"][f]
        print(f"  [{labels[status]:<6}] {f}: {show_value(row['si_value'], row['bl_value'], status)}")
        if result["notes"].get(f):
            print(f"           why: {result['notes'][f]}")
        if status != "match":
            print(f"           SI evidence: {(si.get(f) or {}).get('evidence')}")
            print(f"           BL evidence: {(bl.get(f) or {}).get('evidence')}")

    print()
    flagged = [f for f in FIELDS if result["statuses"][f] == "mismatch"]
    if flagged:
        print(f"  RESULT: mismatch found in: {', '.join(flagged)}")
    if result["needs_review"]:
        print(f"  RESULT: NEEDS HUMAN REVIEW - {result['review_reason']}")
    if not flagged and not result["needs_review"]:
        print("  RESULT: No mismatch detected.")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="  ! %(message)s")  # shows extraction retries
    inbox = Inbox(str(DATA_DIR))

    inbox_dir = DATA_DIR / "inbox"
    email_files = sorted(inbox_dir.glob("email_*.json")) if inbox_dir.is_dir() else []
    if not email_files:
        sys.exit(f"No email_*.json files found in {inbox_dir}. data/ must contain inbox/ and attachments/ directly.")

    ids = [arg.removesuffix(".json") for arg in sys.argv[1:]]
    if not ids:
        first = next((e for e in inbox if e["attachments"]), None)
        if first is None:
            sys.exit("None of the emails in data/inbox has attachments. Something is wrong with the dataset.")
        ids = [first["email_id"]]
    unknown = [i for i in ids if not (inbox_dir / f"{i}.json").exists()]
    if unknown:
        examples = ", ".join(f.stem for f in email_files[:5])
        sys.exit(f"No such email: {', '.join(unknown)}. Some that exist: {examples}")

    describe_key()
    for email_id in ids:
        try:
            check_email(inbox, email_id)
        except anthropic.AuthenticationError:
            sys.exit("Anthropic rejected the API key (401). Fix the key in .env, save the file, and run again.")
        except anthropic.APIError as err:
            print(f"  API call failed for {email_id}: {err}")


if __name__ == "__main__":
    main()
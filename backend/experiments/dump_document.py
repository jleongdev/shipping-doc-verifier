"""
dump_document.py - print the plain text that the readers see in an email's attachments. FREE: no API calls.

    python backend/experiments/dump_document.py email_005 email_059
    python backend/experiments/dump_document.py email_005 --full      # do not cut long documents
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ai.readers import ReaderError, read_document  # noqa: E402
from loader import Inbox  # noqa: E402

LIMIT = 3000


def main() -> None:
    args = sys.argv[1:]
    full = "--full" in args
    ids = [a.removesuffix(".json") for a in args if not a.startswith("--")]
    if not ids:
        sys.exit("Usage: python backend/experiments/dump_document.py email_005 [email_059 ...] [--full]")
    inbox = Inbox(str(ROOT / "data"))
    for email_id in ids:
        try:
            email = inbox.get(email_id)
        except FileNotFoundError:
            print(f"\n{email_id}: no such email")
            continue
        print("\n" + "=" * 78)
        print(f"{email['email_id']}  |  {email['subject']}")
        if not email["attachments"]:
            print("  (no attachments)")
        for path in email["attachments"]:
            print(f"\n----- {path} -----")
            try:
                text = read_document(inbox.read_bytes(path), path)
            except ReaderError as err:
                print(f"  CANNOT READ: {err}")
                continue
            if not text.strip():
                print("  (no text found - probably a scanned image)")
                continue
            print(text if full or len(text) <= LIMIT else text[:LIMIT] + f"\n... [{len(text) - LIMIT} more characters, use --full]")


if __name__ == "__main__":
    main()
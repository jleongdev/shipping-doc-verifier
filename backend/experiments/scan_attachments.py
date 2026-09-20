"""
scan_attachments.py - look at EVERY attachment and list the odd ones. FREE: no API calls.

    python backend/experiments/scan_attachments.py

It reports files that are empty / unreadable / garbled / the wrong kind of document
(e.g. a BL slot that does not contain a Bill of Lading), so we can decide how to label them
(wrong_doc_type, unreadable, ...) from real evidence instead of guessing.
"""
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from ai.doctype import LABELS, detect_doc_type  # noqa: E402
from ai.readers import SUPPORTED_SUFFIXES, ReaderError, pdf_page_info, read_document  # noqa: E402
from loader import Inbox  # noqa: E402

LABEL_LINE = re.compile(r"^\s*[^:\n|]{2,60}[:|]\s*\S", re.M)  # "Shipper: X" or "Shipper | X"
PREVIEWS = 8  # how many odd files get a text preview; the rest are listed in one line each


MARKER = re.compile(r"^(=== SHEET:|--- page \d+ ---)")  # separators added by readers.py, not part of the document


def first_lines(text: str, n: int) -> list:
    lines = [line.strip() for line in text.splitlines() if line.strip() and not MARKER.match(line.strip())]
    return lines[:n]


def problems(tag: str, text: str) -> list:
    found = []
    if not text.strip():
        return ["no text at all (empty file or scanned image)"]
    if len(text.strip()) < 150:
        found.append(f"very short ({len(text.strip())} characters)")
    junk = sum(1 for c in text if not (c.isprintable() or c in "\n\r\t"))
    if junk / len(text) > 0.05:
        found.append(f"garbled ({junk / len(text):.0%} unprintable characters)")
    if tag in ("SI", "BL"):
        kind = detect_doc_type(text)
        if kind == "UNKNOWN":
            found.append("header not recognised (unknown kind of document)")
        elif kind != tag:
            found.append(f"wrong_doc_type: the {tag} slot holds a {LABELS[kind]}")
    if len(LABEL_LINE.findall(text)) < 5:
        found.append("fewer than 5 'label: value' lines")
    return found


def main() -> None:
    inbox = Inbox(str(ROOT / "data"))
    emails = inbox.emails()
    total, by_type, headers, odd = 0, Counter(), {"SI": Counter(), "BL": Counter()}, []

    for email in emails:
        for path in email["attachments"]:
            total += 1
            suffix = Path(path).suffix.lower()
            by_type[suffix] += 1
            tag = "SI" if "_SI." in path.upper() else "BL" if "_BL." in path.upper() else "??"
            if suffix not in SUPPORTED_SUFFIXES:
                odd.append((email["email_id"], path, ["unsupported file type"], ""))
                continue
            try:
                text = read_document(inbox.read_bytes(path), path)
            except ReaderError as err:
                odd.append((email["email_id"], path, [f"cannot open: {err}"], ""))
                continue
            if tag in headers and text.strip():
                headers[tag][(first_lines(text, 1) or [""])[0][:60]] += 1
            issues = problems(tag, text)
            if not text.strip() and suffix == ".pdf":
                info = pdf_page_info(inbox.read_bytes(path))
                issues = [f"no text layer: PDF with {info[0]} page(s) and {info[1]} embedded image(s)" + (" -> looks like a scan" if info[1] else " -> looks blank")] if info else issues
            if issues:
                odd.append((email["email_id"], path, issues, "\n".join("      | " + l[:110] for l in first_lines(text, 8))))

    print(f"Scanned {total} attachments in {len(emails)} emails.  By type: " + ", ".join(f"{k} x{v}" for k, v in by_type.most_common()))
    for tag in ("SI", "BL"):
        print(f"\nFirst line of {tag} files:")
        for line, count in headers[tag].most_common(8):
            print(f"  {count:>4} x {line}")

    print(f"\n=== ODD FILES ({len(odd)}) ===")
    for number, (email_id, path, issues, preview) in enumerate(odd, start=1):
        if number <= PREVIEWS:
            print(f"\n{path}")
            for issue in issues:
                print(f"    ! {issue}")
            if preview:
                print(preview)
        else:
            if number == PREVIEWS + 1:
                print("\n--- the rest, one line each ---")
            print(f"{path}: {'; '.join(issues)}")


if __name__ == "__main__":
    main()

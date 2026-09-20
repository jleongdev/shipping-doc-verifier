"""
run_all.py - run the whole SI-vs-BL check on EVERY email that has attachments (txt, xlsx, docx, pdf)
and print a summary you can act on.

Run it from the project root (the shipping-doc-verifier folder):

    python backend/experiments/run_all.py --limit 10     # try 10 emails first
    python backend/experiments/run_all.py                # everything
    python backend/experiments/run_all.py --refresh      # ignore the cache and ask Claude again
    python backend/experiments/run_all.py --workers 2    # gentler on rate limits (default 4)

For each email, in this order (the first problem found decides the result):
    1. an SI or BL attachment is missing            -> NEEDS REVIEW  (missing_attachment)   no API call
    2. a file cannot be opened / has no text        -> NEEDS REVIEW  (unreadable)           no API call
    3. the SI or BL slot holds another document
       (invoice, packing list, ...)                 -> NEEDS REVIEW  (wrong_doc_type)       no API call
    4. otherwise: Claude extracts the 7 fields, plain Python compares them.

Claude's answers are cached in backend/experiments/cache/ (one small file per email), so re-running after you
change compare.py costs nothing. The cache is keyed on the model, the prompt and the document text: DON'T edit
the prompt in ai/extract.py unless you can afford to re-ask everything. Failed extractions are never cached.
Results are saved to backend/experiments/cache/batch_summary.json (used by build_submission.py).
"""
import argparse
import hashlib
import json
import logging
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # shipping-doc-verifier/
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "backend" / "experiments" / "cache"
sys.path.insert(0, str(ROOT / "backend"))

import anthropic  # noqa: E402
from ai.compare import FIELDS, compare  # noqa: E402
from ai.doctype import wrong_kind  # noqa: E402
from ai.extract import MODEL, SYSTEM_PROMPT, TOOL, extract_fields, has_any_value  # noqa: E402
from ai.readers import SUPPORTED_SUFFIXES, ReaderError, read_document  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from loader import Inbox  # noqa: E402

load_dotenv(ROOT / ".env", override=True)
if not os.getenv("ANTHROPIC_API_KEY"):
    sys.exit(f"ANTHROPIC_API_KEY not found. Check {ROOT / '.env'}.")


def pick_attachment(attachments: list, tag: str):
    for path in attachments:
        if f"_{tag}." in path.upper():
            return path
    return None


def fingerprint(si_text: str, bl_text: str) -> str:
    """Changes whenever the model, the prompt, the tool schema or the documents change."""
    blob = json.dumps([MODEL, SYSTEM_PROMPT, TOOL, si_text, bl_text], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def plan(emails: list) -> tuple[list, list]:
    """Split emails with attachments into (to process, skipped because of an unsupported file type)."""
    ready, skipped = [], []
    for email in emails:
        if not email["attachments"]:
            continue
        si_path = pick_attachment(email["attachments"], "SI")
        bl_path = pick_attachment(email["attachments"], "BL")
        present = [p for p in (si_path, bl_path) if p]
        bad = sorted({Path(p).suffix.lower() for p in present if not p.lower().endswith(SUPPORTED_SUFFIXES)})
        if bad:
            skipped.append((email["email_id"], "unsupported file type (" + ", ".join(bad) + ")"))
        else:
            ready.append((email, si_path, bl_path))  # a missing SI/BL is handled in process()
    return ready, skipped


def review(record: dict, code: str, detail: str) -> dict:
    record.update(status="review", flagged=[], review_code=code, review_detail=detail)
    return record


def process(inbox: Inbox, email: dict, si_path, bl_path, refresh: bool) -> dict:
    email_id = email["email_id"]
    record = {"email_id": email_id, "subject": email["subject"], "cached": False, "review_code": None, "review_detail": None}

    # 1. missing attachment
    absent = [name for name, path in (("SI", si_path), ("BL", bl_path)) if not path]
    if absent:
        return review(record, "missing_attachment", f"no {' or '.join(absent)} attachment on this email")

    # 2. can the files be opened, do they contain text?
    try:
        si_text = read_document(inbox.read_bytes(si_path), si_path)
        bl_text = read_document(inbox.read_bytes(bl_path), bl_path)
    except ReaderError as err:
        return review(record, "unreadable", str(err))
    empty = [name for name, text in (("SI", si_text), ("BL", bl_text)) if not text.strip()]
    if empty:
        return review(record, "unreadable", f"{' and '.join(empty)} has no text (scanned image?)")

    # 3. is each slot really the kind of document it should be?
    for name, text in (("SI", si_text), ("BL", bl_text)):
        found = wrong_kind(text, name)
        if found:
            return review(record, "wrong_doc_type", f"the {name} attachment is a {found}, not a {'Shipping Instruction' if name == 'SI' else 'Bill of Lading'}")

    # 4. extract (or reuse the cached answer) and compare
    try:
        fp = fingerprint(si_text, bl_text)
        cache_file = CACHE_DIR / f"{email_id}.json"
        si = bl = None
        if not refresh and cache_file.exists():
            saved = json.loads(cache_file.read_text(encoding="utf-8"))
            if saved.get("fingerprint") == fp:
                si, bl, record["cached"] = saved["si"], saved["bl"], True
        if si is None:
            si = extract_fields(si_text, "SI")
            bl = extract_fields(bl_text, "BL")
            if has_any_value(si) and has_any_value(bl):  # never cache a failed extraction
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = cache_file.with_suffix(".tmp")
                tmp.write_text(json.dumps({"fingerprint": fp, "si": si, "bl": bl}, indent=1), encoding="utf-8")
                tmp.replace(cache_file)

        result = compare(si, bl)
        flagged = [f for f in FIELDS if result["statuses"].get(f) == "mismatch"]
        missing = [row["field"] for row in result["fields"] if row["si_value"] is None or row["bl_value"] is None]
        if not result["fields"]:  # nothing extracted from a document that opened fine
            return review(record, "unreadable", result["review_reason"])
        if missing:
            code = "missing_value"
        else:
            code = None
        record.update(
            status="mismatch" if flagged and not missing else ("review" if result["needs_review"] else "ok"),
            flagged=flagged,
            review_code=code,
            review_detail=result["review_reason"],
            statuses=result["statuses"],
            fields=result["fields"],
        )
    except anthropic.AuthenticationError:
        raise  # every other email would fail the same way: stop the whole run
    except anthropic.APIError as err:
        record.update(status="error", flagged=[], review_detail=f"API call failed: {err}")
    return record


def wrap(ids: list, width: int = 88) -> str:
    lines, line = [], "   "
    for item in ids:
        if len(line) + len(item) + 2 > width:
            lines.append(line.rstrip(", "))
            line = "   "
        line += item + ", "
    lines.append(line.rstrip(", "))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SI-vs-BL check on every email with attachments.")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N emails")
    parser.add_argument("--refresh", action="store_true", help="ignore cached extractions")
    parser.add_argument("--workers", type=int, default=4, help="parallel API calls (default 4)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="  ! %(message)s")
    inbox = Inbox(str(DATA_DIR))
    emails = inbox.emails()
    if not emails:
        sys.exit(f"No emails found in {DATA_DIR / 'inbox'}.")

    ready, skipped = plan(emails)
    if args.limit:
        ready = ready[: args.limit]
    print(f"{len(emails)} emails in the inbox | {len(ready)} to process now | {len(skipped)} skipped | model: {MODEL}")

    records, done = [], 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(process, inbox, e, si, bl, args.refresh) for e, si, bl in ready]
        try:
            for future in as_completed(futures):
                records.append(future.result())
                done += 1
                if done % 10 == 0 or done == len(futures):
                    print(f"  ... {done}/{len(futures)} done")
        except anthropic.AuthenticationError:
            for f in futures:
                f.cancel()
            sys.exit("Anthropic rejected the API key (401). Fix .env and run again.")

    records.sort(key=lambda r: r["email_id"])
    by_status = {s: [r for r in records if r["status"] == s] for s in ("mismatch", "review", "error", "ok")}
    cached = sum(r["cached"] for r in records)

    print(f"\n=== MISMATCH FOUND ({len(by_status['mismatch'])}) ===")
    for r in by_status["mismatch"]:
        print(f"  {r['email_id']}  {', '.join(r['flagged'])}")

    print(f"\n=== NEEDS HUMAN REVIEW ({len(by_status['review'])}) ===")
    for r in by_status["review"]:
        also = f"   [also differs: {', '.join(r['flagged'])}]" if r["flagged"] else ""
        print(f"  {r['email_id']}  {r['review_code'] or 'ambiguous'}: {r['review_detail']}{also}")

    print(f"\n=== ERRORS ({len(by_status['error'])})  - fix the cause and run again: only these are retried ===")
    for detail, count in Counter(r["review_detail"] for r in by_status["error"]).most_common():
        ids = [r["email_id"] for r in by_status["error"] if r["review_detail"] == detail]
        print(f"  {count} x {detail[:230]}")
        print(wrap(ids))

    print(f"\n=== NO MISMATCH DETECTED ({len(by_status['ok'])}) ===")
    if by_status["ok"]:
        print(wrap([r["email_id"] for r in by_status["ok"]]))

    print(f"\n=== SKIPPED ({len(skipped)}) ===")
    for reason, count in Counter(reason for _, reason in skipped).most_common():
        print(f"  {count} x {reason}")
        print(wrap([eid for eid, why in skipped if why == reason]))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    summary = {r["email_id"]: {k: v for k, v in r.items() if k not in ("email_id", "cached")} for r in records}
    for eid, why in skipped:
        summary[eid] = {"status": "skipped", "flagged": [], "review_code": None, "review_detail": why}
    (CACHE_DIR / "batch_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")

    print(
        f"\nTotals: {len(by_status['mismatch'])} mismatch | {len(by_status['review'])} review | "
        f"{len(by_status['error'])} errors | {len(by_status['ok'])} ok | {cached}/{len(records)} answers came from the cache"
    )
    print(f"Saved: {CACHE_DIR / 'batch_summary.json'}")


if __name__ == "__main__":
    main()

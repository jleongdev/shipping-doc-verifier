"""
run_all.py - run extract + compare on EVERY email that has an SI and a BL, then print a summary you can act on.

Run it from the project root (the shipping-doc-verifier folder):

    python backend/experiments/run_all.py --limit 10     # try 10 emails first (recommended)
    python backend/experiments/run_all.py                # everything
    python backend/experiments/run_all.py --refresh      # ignore the cache and ask Claude again
    python backend/experiments/run_all.py --workers 2    # gentler on rate limits (default 4)

Claude's answers are cached in backend/experiments/cache/ (one small file per email). Re-running after you
change compare.py is instant and free. The cache refreshes by itself when the model, the prompt or the
document text changes. Emails whose extraction failed are NOT cached, so the next run retries them.
Add this line to .gitignore:   backend/experiments/cache/
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
from ai.extract import MODEL, SYSTEM_PROMPT, TOOL, extract_fields, has_any_value  # noqa: E402
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
    """Split emails with attachments into (ready to process, skipped with a reason)."""
    ready, skipped = [], []
    for email in emails:
        if not email["attachments"]:
            continue
        si_path = pick_attachment(email["attachments"], "SI")
        bl_path = pick_attachment(email["attachments"], "BL")
        if not si_path or not bl_path:
            skipped.append((email["email_id"], "missing SI or BL attachment"))
        elif not (si_path.lower().endswith(".txt") and bl_path.lower().endswith(".txt")):
            kinds = sorted({Path(p).suffix.lower() for p in (si_path, bl_path) if not p.lower().endswith(".txt")})
            skipped.append((email["email_id"], "not plain text yet (" + ", ".join(kinds) + ")"))
        else:
            ready.append((email, si_path, bl_path))
    return ready, skipped


def process(inbox: Inbox, email: dict, si_path: str, bl_path: str, refresh: bool) -> dict:
    email_id = email["email_id"]
    record = {"email_id": email_id, "subject": email["subject"], "cached": False}
    try:
        si_text, bl_text = inbox.read_text(si_path), inbox.read_text(bl_path)
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
        record.update(
            status="mismatch" if flagged else ("review" if result["needs_review"] else "ok"),
            flagged=flagged,
            review_reason=result["review_reason"],
            statuses=result["statuses"],
            fields=result["fields"],
        )
    except anthropic.AuthenticationError:
        raise  # every other email would fail the same way: stop the whole run
    except anthropic.APIError as err:
        record.update(status="error", flagged=[], review_reason=f"API call failed: {err}")
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
    parser = argparse.ArgumentParser(description="Run extract + compare on every SI/BL pair.")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N ready emails")
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
        extra = f"   (also needs review: {r['review_reason']})" if r["review_reason"] else ""
        print(f"  {r['email_id']}  {', '.join(r['flagged'])}{extra}")

    print(f"\n=== NEEDS HUMAN REVIEW ({len(by_status['review'])}) ===")
    for r in by_status["review"]:
        print(f"  {r['email_id']}  {r['review_reason']}")

    print(f"\n=== ERRORS ({len(by_status['error'])})  - run again to retry only these ===")
    for r in by_status["error"]:
        print(f"  {r['email_id']}  {r['review_reason']}")

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
        summary[eid] = {"status": "skipped", "flagged": [], "review_reason": why}
    (CACHE_DIR / "batch_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")

    print(
        f"\nTotals: {len(by_status['mismatch'])} mismatch | {len(by_status['review'])} review | "
        f"{len(by_status['error'])} errors | {len(by_status['ok'])} ok | {cached}/{len(records)} answers came from the cache"
    )
    print(f"Saved: {CACHE_DIR / 'batch_summary.json'}")


if __name__ == "__main__":
    main()
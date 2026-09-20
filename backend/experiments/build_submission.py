"""
build_submission.py - turn the batch results into the scoreboard's submission format, and optionally submit them.
FREE: it only reads what run_all.py already saved (no Claude calls).

    python backend/experiments/build_submission.py
        -> writes backend/experiments/cache/submission_partial.json and prints a summary

    python backend/experiments/build_submission.py --server http://HOST:8080
        -> ALSO submits it to the scoring server and prints the score

"PARTIAL" because this only fills in the emails that run_all.py processed (the SI/BL emails). Every other email
keeps the placeholder from sample_submission.json (GENERAL / OK) until Role 2's classifier supplies real categories.
So the overall score will be low: look at the defect-related numbers, which is what this part of the pipeline controls.
This file is NOT the team's final submission.json (that is Role 1's job).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "backend" / "experiments" / "cache"
sys.path.insert(0, str(ROOT / "backend"))

from ai.verdict import to_scoreboard  # noqa: E402
from loader import Inbox  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build (and optionally submit) a partial submission from the batch results.")
    parser.add_argument("--server", help="scoring server URL, e.g. http://localhost:8080")
    args = parser.parse_args()

    summary_file = CACHE_DIR / "batch_summary.json"
    if not summary_file.exists():
        sys.exit("No batch_summary.json yet. Run:  python backend/experiments/run_all.py")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))

    sample_file = ROOT / "data" / "sample_submission.json"
    if not sample_file.exists():
        sys.exit(f"Cannot find {sample_file}")
    submission = json.loads(sample_file.read_text(encoding="utf-8"))  # every email_id, with placeholder entries

    counts = Counter()
    unknown = [eid for eid in summary if eid not in submission]
    for email_id, record in summary.items():
        if email_id in submission:
            entry = to_scoreboard(record)
            submission[email_id] = entry
            counts[(entry["status"], entry["review_reason"])] += 1

    out = CACHE_DIR / "submission_partial.json"
    out.write_text(json.dumps(submission, indent=2), encoding="utf-8")

    print(f"{len(submission)} emails in the submission | {sum(counts.values())} filled in from the batch results\n")
    for (status, reason), count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4} x {status}" + (f" ({reason})" if reason else ""))
    errors = [eid for eid, r in summary.items() if r["status"] == "error"]
    if errors:
        print(f"\n! {len(errors)} emails had API errors and are reported as NEEDS_REVIEW/unreadable for now. "
              f"Re-run run_all.py once credits are back, then build again.")
    if unknown:
        print(f"! {len(unknown)} results are for email_ids that are not in sample_submission.json (ignored): {unknown[:5]}")
    print(f"\nSaved: {out}")

    if args.server:
        print(f"\nSubmitting to {args.server} ...")
        result = Inbox(args.server).submit(submission)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

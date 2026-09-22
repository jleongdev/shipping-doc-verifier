import os, json
from backend.loader import Inbox
from backend.pipeline import process_email
from backend.submission import write_submission

inbox = Inbox("data")
emails = list(inbox)
results = []

for i, email in enumerate(emails, 1):
    results.append(process_email(email, inbox))
    print(f"Email {i}/{len(emails)} done", flush=True)

# Save the cache so /results (the dashboard) is instant and costs nothing to reload
os.makedirs("cache", exist_ok=True)
with open("cache/results.json", "w") as f:
    json.dump([r.model_dump() for r in results], f, indent=2)
print(f"✅ Cached {len(results)} results to cache/results.json", flush=True)

payload = write_submission(results, "submission.json")
print(f"✅ Wrote submission.json with {len(payload)} emails", flush=True)

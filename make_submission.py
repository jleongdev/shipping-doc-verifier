from backend.loader import Inbox
from backend.pipeline import process_email
from backend.submission import write_submission

inbox = Inbox("data")
emails = list(inbox)
results = []
for i, email in enumerate(emails, 1):
    results.append(process_email(email, inbox))
    print(f"[{i}/{len(emails)}] {email['email_id']} done", flush=True)

payload = write_submission(results, "submission.json")
print(f"\n✅ Wrote submission.json with {len(payload)} emails")

from backend.pipeline import process_email
from backend.loader import Inbox

inbox = Inbox("data")                 # adjust if your data path differs
for email in list(inbox)[:3]:         # just the first 3 emails
    result = process_email(email, inbox)
    print(result.model_dump())
    print("-" * 40)
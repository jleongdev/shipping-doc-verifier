from backend.loader import Inbox
from backend.pipeline import process_email, find_si_bl, read_document
from backend.ai.extract import extract_fields

inbox = Inbox("data")

count = 0
for email in inbox:
    r = process_email(email, inbox)
    if r.category == "BL_COMPARISON":
        print("=" * 70)
        print(f"{r.email_id}  ->  status={r.status}  "
              f"defects={r.defect_fields}  reason={r.review_reason}")

        # Show what was actually extracted from each document, side by side
        try:
            si_path, bl_path = find_si_bl(email)
            si = extract_fields(read_document(inbox, si_path))
            bl = extract_fields(read_document(inbox, bl_path))
            print(f"\n{'field':<20}{'SI':<25}{'BL':<25}")
            for f in si:
                print(f"{f:<20}{str(si[f]):<25}{str(bl[f]):<25}")
        except Exception as e:
            print("could not extract docs:", e)

        count += 1
        if count >= 2:          # check the first 2 BL_COMPARISON emails
            break

if count == 0:
    print("No BL_COMPARISON emails found.")

from backend.ai.classify import classify_email

samples = [
    ("Confirm draft BL", "Please check the attached draft Bill of Lading against our Shipping Instruction and confirm."),
    ("Invoice question", "Why was invoice #4471 charged twice? Please advise on the freight charges."),
    ("You won a prize!!!", "Click here to claim your free iPhone now!!!"),
]

for subject, body in samples:
    r = classify_email(subject, body)
    print(f"\nSubject: {subject}")
    print(f"  category:   {r['category']}  (confidence {r['confidence']})")
    print(f"  reason:     {r.get('reason')}")

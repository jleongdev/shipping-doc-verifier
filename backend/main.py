from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from .loader import Inbox
from .pipeline import process_all, process_email
from .submission import build_submission

app = FastAPI(title="Shipping Doc Verifier")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

inbox = Inbox("data")   # folder holding inbox/ and attachments/

@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/results")
def results(limit: int | None = None):
    emails = list(inbox)
    if limit:
        emails = emails[:limit]
    return [process_email(e, inbox).model_dump() for e in emails]

@app.get("/review-queue")
def review_queue(limit: int | None = None):
    flagged = [r for r in process_all(inbox) if r.status == "NEEDS_REVIEW"]
    if limit:
        flagged = flagged[:limit]
    return [r.model_dump() for r in flagged]

@app.post("/submit")
def submit():
    payload = build_submission(process_all(inbox))
    return inbox.submit(payload)   # TODO: confirm loader's submit signature

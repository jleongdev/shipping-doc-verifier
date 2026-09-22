from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from .loader import Inbox
from .pipeline import process_all, process_email
from .submission import write_submission

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
    results_list = process_all(inbox, use_cache=True)   # reads cache → instant
    by_id = {r.email_id: r for r in results_list}
    out = []
    for e in inbox:
        r = by_id.get(e.get("email_id"))
        if r is None:
            continue
        row = r.model_dump()
        row["subject"] = e.get("subject", "")
        row["sender"] = e.get("from") or e.get("sender", "")
        out.append(row)
        if limit and len(out) >= limit:
            break
    return out


@app.get("/review-queue")
def review_queue(limit: int | None = None):
    results_list = process_all(inbox, use_cache=True)
    subj = {e.get("email_id"): e.get("subject", "") for e in inbox}
    out = []
    for r in results_list:
        if r.status == "NEEDS_REVIEW":
            row = r.model_dump()
            row["subject"] = subj.get(r.email_id, "")
            out.append(row)
            if limit and len(out) >= limit:
                break
    return out

@app.post("/submit")
def submit():
    payload = write_submission(process_all(inbox))   # writes submission.json
    return {"emails": len(payload), "wrote": "submission.json"}

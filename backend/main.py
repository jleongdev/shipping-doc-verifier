from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .loader import Inbox
from .pipeline import process_all
from .submission import build_submission

app = FastAPI(title="Shipping Doc Verifier")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

inbox = Inbox("data")   # or Inbox("http://localhost:8080")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/results")
def results():
    return [r.model_dump() for r in process_all(inbox)]

@app.get("/review-queue")
def review_queue():
    return [r.model_dump() for r in process_all(inbox) if r.needs_review]

@app.post("/submit")
def submit():
    payload = build_submission(process_all(inbox))
    return inbox.submit(payload)   # TODO: confirm loader's submit signature

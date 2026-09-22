# Shipping Document Verifier

> AI system that triages shipping-operations emails and compares Shipping Instructions (SI) against Bills of Lading (BL) — flagging mismatches across 7 key fields and escalating uncertain cases to human review.

Built for the **Averis x Monash Hackathon 2026**.

- **Live demo:** https://shipping-doc-verifier-8s2l.vercel.app/
- **Demo video:** 
- **Slide deck:** https://docs.google.com/presentation/d/1A5GIkDm1Mp5RpRwcdJ0-kmrjpNqPTCOM/edit?slide=id.p1#slide=id.p1

---

## Problem

Averis receives high volumes of shipping operational emails where staff must compare Shipping Instructions (SI) against draft Bills of Lading (BL). Our system automates that: it classifies each inbox email, extracts shipment fields from the documents, detects mismatches across 7 key attributes, and escalates edge cases to human reviewers instead of guessing.

## What it does

1. **Classify** — sorts every email into one of five categories: `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, `SPAM`.
2. **Extract** — for `BL_COMPARISON` emails, reads the SI and BL text documents and pulls the 7 shipment fields into structured data, aligning fields by meaning even when the two documents use different labels (e.g. "Load Port" = "Port of Loading").
3. **Compare** — checks the 7 fields side by side and reports each as a match or mismatch, showing the SI value against the BL value.
4. **Escalate** — routes unreadable, incomplete, or ambiguous cases to a human-review queue with the reason, instead of forcing a decision.

## Tech stack

| Layer | Choice |
|---|---|
| Backend / API | Python + FastAPI |
| AI | Claude (Anthropic API) — Sonnet for extraction, Haiku for classification |
| Frontend | React + Next.js + Tailwind CSS (deployed on Vercel) |
| Cloud | Frontend hosted on Vercel; backend containerized (Dockerfile) and Cloud Run–ready |

## Architecture

```
Inbox (emails + attachments)
        │
        ▼
   [ Classify ]  ── Claude Haiku ──►  category + confidence
        │
        ▼ (only BL_COMPARISON)
   [ Extract ]   ── Claude Sonnet ──►  7 fields from SI + 7 fields from BL
        │
        ▼
   [ Compare ]   ──►  per-field match / mismatch (normalized)
        │
        ├──► unreadable / missing / ambiguous → Human Review Queue
        │
        ▼
   Results (cached) ──► FastAPI API ──► Next.js dashboard
                     └► submission.json (self-evaluation)
```

## Project structure

```
shipping-doc-verifier/
├── README.md
├── .gitignore
├── .gcloudignore
├── Dockerfile               # containerizes the FastAPI backend (Cloud Run–ready)
├── requirements.txt
├── make_submission.py       # runs the pipeline over all emails → submission.json + cache
├── package.json             # Next.js app lives at the repo root
├── next.config.ts
├── app/                     # Next.js dashboard (layout.tsx, page.tsx, globals.css)
├── data/                    # synthetic dataset (inbox/ + attachments/)
├── cache/                   # cached pipeline results (gitignored)
└── backend/
    ├── main.py              # FastAPI endpoints
    ├── pipeline.py          # classify → extract → compare → escalate
    ├── schemas.py           # shared data contracts
    ├── submission.py        # builds submission.json
    ├── loader.py            # provided data loader
    └── ai/
        ├── claude.py        # shared Claude client
        ├── classify.py      # email classifier (Haiku)
        └── extract.py       # field extraction (Sonnet)
```

## Getting started

### Prerequisites
- Python 3.11+
- Node.js 18+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### 1. Clone
```bash
git clone https://github.com/<your-username>/shipping-doc-verifier.git
cd shipping-doc-verifier
```

### 2. Backend setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment variables
```bash
cp .env.example .env
```
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Generate results (one run — builds the cache + submission)
```bash
python make_submission.py
```
This processes all emails once, writes `submission.json`, and caches results to `cache/results.json` so the API and dashboard load instantly afterward.

### 5. Run the backend
```bash
uvicorn backend.main:app --reload
```
- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs

### 6. Run the frontend (from the repo root)
```bash
npm install
npm run dev
```
- App: http://localhost:3000

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/results` | All emails with classification + comparison results (served from cache) |
| GET | `/review-queue` | Emails flagged for human review |
| POST | `/submit` | Builds `submission.json` from the pipeline results |

## The 7 compared fields

Shipper · Consignee · Notify party · Port of loading · Port of discharge · Container count · Gross weight (kg)

## Deployment

- **Frontend** → deployed on **Vercel** (root directory = repo root), calling the backend via `NEXT_PUBLIC_API_URL`.
- **Backend** → containerized with the included `Dockerfile`; deploys to **Google Cloud Run** (`gcloud run deploy --source .`) with the API key passed as an environment variable. Runs locally for the demo.

## Team

| Role | Member |
|---|---|
| Pipeline Lead | Jerry Leong Jun Fai |
| Classification (AI) | Tan Hao Sheng |
| Extract + Compare (AI) | Poon Shi Xun |
| Frontend | Jason Teh Jia Sheng |
| Cloud + Integration | Lim Jia Wei |

## License

MIT — see [LICENSE](LICENSE).

---
*Built at the Averis x Monash Hackathon 2026.*

# Shipping Document Verifier

> AI system that triages shipping-operations emails and compares Shipping Instructions (SI) against Bills of Lading (BL) — flagging mismatches across 7 key fields and escalating uncertain cases to human review.

Built for the **Averis x Monash Hackathon 2026**.

- **Live demo:** <your-deployed-app-url>
- **Demo video:** <your-youtube-link>
- **Slide deck:** <your-deck-link>

---

## Problem

Averis receives high volumes of shipping operational emails requiring staff to compare Shipping Instructions (SI) against draft Bills of Lading (BL). Our system automates this: it classifies incoming emails, extracts shipment fields, detects mismatches across 7 key attributes (shipper, consignee, notify party, ports, container count, and gross weight), and escalates complex edge cases to human reviewers.

## What it does

1. **Classify** — sorts every inbox email into one of five categories (document comparison, new SI request, invoice query, general message, spam).
2. **Extract** — for comparison requests, reads the SI and BL documents and pulls the 7 shipment fields into structured data (handles synonym labels, PDFs, and scanned pages via vision).
3. **Compare** — checks the 7 fields side by side and reports any mismatch with the SI value vs the BL value.
4. **Escalate** — routes low-confidence, unreadable, or incomplete cases to a human-review queue with the reason and evidence, instead of guessing.

## Tech stack

| Layer | Choice |
|---|---|
| Backend / API | Python + FastAPI |
| AI | Claude (Anthropic API) — Sonnet for extraction, Haiku for classification |
| Frontend | React + Next.js + Tailwind CSS |
| Cloud | Google Cloud — Cloud Run (backend), Secret Manager (keys), Document AI (scanned docs) |

## Architecture

```
Inbox (emails + attachments)
        │
        ▼
   [ Classify ]  ── Claude ──►  category + confidence
        │
        ▼ (only "document_comparison")
   [ Extract ]   ── Claude ──►  7 fields from SI + 7 fields from BL
        │
        ▼
   [ Compare ]   ──►  per-field match / mismatch
        │
        ├──► low confidence / unreadable / missing → Human Review Queue
        │
        ▼
   Discrepancy report  ──►  FastAPI API  ──►  Next.js dashboard
                         └►  submission.json → self-evaluation endpoint
```

## Project structure

```
shipping-doc-verifier/
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
├── data/                    # provided dataset (gitignored)
└── backend/
    ├── main.py              # FastAPI endpoints
    ├── pipeline.py          # orchestration + human-in-the-loop
    ├── schemas.py           # shared data contracts
    ├── submission.py        # builds submission.json
    ├── loader.py            # provided data loader
    └── ai/
        ├── claude.py        # shared Claude client
        ├── classify.py      # email classifier
        └── extract.py       # field extraction
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
Copy the example and add your key:
```bash
cp .env.example .env
```
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Add the data
Download the provided dataset and unzip it into the `data/` folder (this folder is gitignored — never commit it).

### 5. Run the backend
```bash
uvicorn backend.main:app --reload
```
- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs

### 6. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
- App: http://localhost:3000

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/results` | All emails with classification + comparison results |
| GET | `/review-queue` | Emails flagged for human review |
| POST | `/submit` | Build and send `submission.json` to the self-evaluation endpoint |

## The 7 compared fields

Shipper · Consignee · Notify party · Port of loading · Port of discharge · Container count · Gross weight (kg)

## Self-evaluation

To score the pipeline, run the provided data server (Docker) and submit results:
```bash
docker compose up --build      # starts the local data server at localhost:8080
```
Then call `POST /submit` (or `inbox.submit(...)`) to get a score.

## Deployment

- **Backend** → Google Cloud Run (`gcloud run deploy`), with the API key stored in Secret Manager.
- **Frontend** → Vercel or Firebase Hosting, pointed at the Cloud Run URL.

## Team

| Role | Member |
|---|---|
| Pipeline Lead | <name> |
| Classification (AI) | <name> |
| Extract + Compare (AI) | <name> |
| Frontend | <name> |
| Cloud + Integration | <name> |

## License

MIT — see [LICENSE](LICENSE).

---
*Built at the Averis x Monash Hackathon 2026.*

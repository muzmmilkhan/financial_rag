# Financial RAG

Ask questions about financial PDFs. Pages are turned into images, embedded with Gemini, stored in Qdrant, and the best-matching pages are sent to Gemini to write the answer.

```
financial_rag/
├── backend/            FastAPI app (API + PDF ingestion)
│   └── app/
│       ├── main.py          API routes: /health /query /upload
│       ├── ingestion.py     watches data/ and embeds new PDFs
│       ├── pdf.py           PDF -> page images
│       ├── embedder.py      Gemini embeddings
│       ├── vector_store.py  Qdrant read/write
│       ├── llm.py           Gemini answer generation
│       └── config.py        settings from environment variables
├── frontend/           Static web UI (HTML/CSS/JS)
├── data/               Put your PDFs here
├── docker-compose.yml  Runs everything (Qdrant + backend + frontend)
└── .env                Your secrets (you create this)
```

## Setup (3 steps)

**You need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and a free [Gemini API key](https://aistudio.google.com/apikey).

**1. Add your API key**

```bash
cp .env.example .env
```

Open `.env` and replace `your-gemini-api-key` with your real key.

**2. Start everything**

```bash
docker compose up --build
```

**3. Open the app**

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

That's it. The first start is slow because the PDFs already in `data/` are being embedded. Watch the logs (`page 3/120 ...`). Questions return answers once at least one page is indexed.

## Using it

- **Ask:** type a question in the UI (e.g. "What was JPMorgan's net income in 2023?").
- **Add documents:** use the *Upload* tab, or just drop a `.pdf` into `data/`. It is picked up within seconds. Already-processed files are skipped.

## Everyday commands

| Task | Command |
| --- | --- |
| Start in background | `docker compose up -d` |
| Stop | `docker compose down` |
| View backend logs | `docker compose logs -f backend` |
| Wipe the vector database | `docker compose down -v` and delete `data/.processed_files.json` |

## How it works

1. **Ingest:** the backend scans `data/` every 5s. New PDF -> each page becomes an image -> Gemini embeds it -> saved in Qdrant.
2. **Ask:** your question is embedded -> Qdrant finds the most similar pages -> Gemini reads those page images and answers.

## Settings (optional, in `.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | required | Your Gemini key |
| `LLM_MODEL` | `gemini-2.5-pro` | Model that writes answers |
| `EMBEDDING_MODEL` | `gemini-embedding-2` | Model that embeds pages |

## Run without Docker (for development)

Needs Python 3.12, [poppler](https://poppler.freedesktop.org/) (`brew install poppler`), and Qdrant (`docker run -p 6333:6333 qdrant/qdrant`).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY=your-key DATA_DIR=../data
uvicorn app.main:app --reload --port 8000
```

In another terminal: `cd frontend && python3 -m http.server 3000`

## Troubleshooting

- **`Set GEMINI_API_KEY in .env`**: you skipped step 1.
- **UI shows "Offline"**: backend isn't up; check `docker compose logs backend`. The API URL box in the UI should be `http://localhost:8000`.
- **Rate limit (429) messages**: normal on free keys; ingestion retries automatically.

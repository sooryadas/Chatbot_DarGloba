# Real Estate Intelligence Chatbot

An MVP chatbot for answering questions from publicly available DarGlobal and Wasalt information.

## Planned architecture

- `frontend/`: Streamlit user interface.
- `backend/`: FastAPI REST API, retrieval, and OpenRouter answer generation.
- `scraper/`: separate public content collectors and shared collection helpers.
- `data/raw/`: collected records for inspection and ingestion.
- `data/chroma/`: persistent ChromaDB data (not committed).
- `tests/`: independent checks for scraping, API behavior, and retrieval.

## Current implementation status

- Shared collection helpers and DarGlobal/Wasalt page collectors are implemented.
- `python -m scraper.collect` collects the configured start pages and writes JSONL records to `data/raw/collected_documents.jsonl`.
- The FastAPI backend exposes `GET /health` and `POST /api/v1/chat`.
- The Streamlit frontend sends questions and recent turns to FastAPI, renders the answers and source links, and keeps chat history in the browser session state.
- Chat requests can include recent `history` messages. The client is expected to retain conversation history for its session and send it with each request; the backend does not persist chat transcripts.
- The backend retrieves chunks from ChromaDB and uses OpenRouter to answer from retrieved excerpts with source references.
- `backend/app/services/ingestion.py` chunks the collected JSONL pages into overlapping word windows and upserts them into the same ChromaDB collection used for retrieval.
- The backend, frontend, scraper, and ingestion have not yet been run end to end. The ChromaDB collection must be populated by running collection and ingestion before retrieval can return collected pages.
- Website crawl permissions and the final deployment have not been verified.

## Ingestion

After collecting pages, run the ingestion command from the `backend/` directory:

```powershell
python -m app.ingest
```

The default input is `data/raw/collected_documents.jsonl` relative to the project root. Use `--input` to select another JSONL file, or `--chunk-size-words` and `--overlap-words` to adjust chunking. This command has not yet been run.

## Chat API

`POST /api/v1/chat` accepts a question and optional recent conversation messages:

```json
{
  "question": "What projects are available in Oman?",
  "history": [
    {"role": "user", "content": "Tell me about DarGlobal."},
    {"role": "assistant", "content": "I found information about DarGlobal in the sources."}
  ]
}
```

The response contains an `answer` and a `sources` array with source URLs. `GET /health` checks that the API process is responding.

## Run with Docker Compose

Create the local environment file and add your OpenRouter API key:

```cmd
copy .env.example .env
```

Then collect pages, ingest them into the persistent ChromaDB volume, and start the app:

```cmd
docker compose run --rm backend python -m scraper.collect
docker compose run --rm backend python -m app.ingest --input /app/data/raw/collected_documents.jsonl
docker compose up --build
```

Open `http://localhost:8501` for Streamlit. The backend health endpoint is at `http://localhost:8000/health`. Collected JSONL records are stored in `data/raw/`; ChromaDB persists in the `chroma_data` Docker volume. These container steps have not yet been run or verified.

Build updated images with `docker compose build` before running the commands above. If a usable JSONL file already exists, skip collection and ingest that file. The explicit input path is required because the container's directory layout differs from the local checkout. The `model_cache` volume preserves embedding model downloads between ingestion and backend runs.

Docker build status: a build attempt failed because Playwright's installer could not load `libatomic.so.1`. The backend Dockerfile now installs `libatomic1` before invoking Playwright. Both images install CPU-only PyTorch using the single root requirements workflow. The rebuild and container startup remain unverified.

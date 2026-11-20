# Real Estate Intelligence Chatbot

An MVP chatbot for answering questions from publicly available DarGlobal and Wasalt information.

## Evaluation demo

[Open the chatbot](http://34.123.97.111)

The project owner confirmed that the GCP deployment answers questions and handles conversational messages. The demo runs on a Compute Engine VM independently of the developer's laptop. Availability depends on the VM staying running and funded; this is an evaluation deployment, not a production availability guarantee.

- Use the explicit `http://` address; HTTPS has not been configured.
- Open the link on desktop or mobile and use **Clear chat** to start a new conversation.
- Use public property questions only; do not enter confidential or personal information. Keep the demo link within the intended evaluation group.
- The deployed dataset contained four collected documents at the time of testing. Answers are limited to that coverage, not a live property inventory.

## Architecture

- `frontend/`: Streamlit user interface.
- `backend/`: FastAPI REST API, retrieval, and OpenRouter answer generation.
- `scraper/`: separate public content collectors and shared collection helpers.
- `data/raw/`: collected records for inspection and ingestion.
- `data/chroma/`: persistent ChromaDB data (not committed).
- `tests/`: implemented conversational-routing checks. Scraping, API, and retrieval tests remain to be written; their empty placeholders have been removed.

## Current implementation status

- Shared collection helpers and DarGlobal/Wasalt page collectors are implemented.
- `python -m scraper.collect` collects the configured start pages and writes JSONL records to `data/raw/collected_documents.jsonl`.
- The FastAPI backend exposes `GET /health` and `POST /api/v1/chat`.
- The Streamlit frontend sends questions and recent turns to FastAPI, renders the answers and source links, and keeps chat history in the browser session state.
- Chat requests can include recent `history` messages. The client is expected to retain conversation history for its session and send it with each request; the backend does not persist chat transcripts.
- The backend retrieves chunks from ChromaDB and uses OpenRouter to answer from retrieved excerpts with source references.
- `backend/app/services/ingestion.py` chunks the collected JSONL pages into overlapping word windows and upserts them into the same ChromaDB collection used for retrieval.
- The owner has run collection, ingestion, and Docker deployment and confirmed answers through the public frontend. This manual check is separate from automated test coverage.
- DarGlobal uses Playwright through `scraper/dynamic.py`; Wasalt uses Requests and BeautifulSoup. The shared collectors check robots rules and skip failed or empty pages. Review website terms and permitted scope before expanding collection; public visibility alone does not grant permission.
- The raw JSONL file and ChromaDB data are not committed to Git. A fresh clone needs permitted collection or a separately supplied dataset, followed by ingestion.

## Local setup with uv (Windows CMD)

From the project root, with Python 3.13 and uv installed:

```cmd
uv sync
uv run playwright install chromium
uv run python -m scraper.collect
```

Collection replaces `data/raw/collected_documents.jsonl`; back up a useful existing dataset before collecting again. Inspect its content and record count before ingestion. The configured `/contact` seed can return 404; DarGlobal's Contact page is `/get-in-touch`. External Careers pages remain outside the collector's allowlist.

## Ingestion

From the project root, set the database path relative to the backend working directory and ingest:

```cmd
set "CHROMA_PERSIST_DIRECTORY=..\data\chroma"
uv run --directory backend python -m app.ingest
```

The default local input is `data/raw/collected_documents.jsonl` relative to the project root. Use `--input` to select another JSONL file, or `--chunk-size-words` and `--overlap-words` to adjust chunking. The defaults are 180 words with 30 words of overlap. Re-ingestion upserts stable chunk IDs and removes obsolete chunks for refreshed pages.

Start the backend from the project root in CMD, replacing the placeholder privately:

```cmd
set "CHROMA_PERSIST_DIRECTORY=..\data\chroma"
set "OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY"
set "OPENROUTER_MODEL=openrouter/free"
uv run --directory backend uvicorn app.main:app --port 8000
```

In another CMD window at the project root:

```cmd
set "BACKEND_URL=http://localhost:8000"
uv run streamlit run frontend\app.py
```

Open [the local frontend](http://localhost:8501). Environment variables are specific to each terminal. The Python app does not automatically load `.env`; Docker Compose does. Restart the local backend after changing a setting.

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

`backend/app/services/conversation.py` handles standalone greetings, thanks, goodbyes, bot identity/capability questions, and explicit introductions such as `My name is Soorya` or `Call me Arun`. It can answer `What's my name?` using user introductions still present in the recent client-supplied history; it does not store names separately. Model questions describe the configured OpenRouter model setting, not an assumed underlying model identity. These replies have no source citations and do not call retrieval or OpenRouter.

Bare names and messages containing a greeting plus a factual question still follow the normal retrieval flow. Conversational turns are excluded from the text used to search for subsequent factual answers.

## Tests and limitations

Five isolated conversational-routing tests passed locally. Run them with:

```cmd
python -B -m unittest discover -s tests -p test_conversation.py
```

These use Python's built-in `unittest` and require no model downloads or API keys. Automated scraping, ingestion, retrieval, OpenRouter, and API integration coverage remains to be implemented; the empty placeholder test files were removed.

Retrieved context and prompts guide factual responses, but do not guarantee accuracy. Relevance thresholds and reranking are not implemented. Prices and availability may be absent or outdated. Session history is temporary and limited; there is no saved-chat account system.

## Run with Docker Compose

Create a private `.env` file at the project root containing:

```dotenv
OPENROUTER_API_KEY=YOUR_OPENROUTER_KEY
OPENROUTER_MODEL=openrouter/free
```

Replace the key placeholder with your valid OpenRouter key. `.env` is ignored by Git and excluded from Docker's build context. Optional `DARGLOBAL_START_URLS` and `WASALT_START_URLS` accept comma-separated page URLs whose collection is permitted. Never commit credentials.

Build the images before collection and ingestion:

```cmd
docker compose build
docker compose run --rm backend python -m scraper.collect
docker compose run --rm backend python -m app.ingest --input /app/data/raw/collected_documents.jsonl
docker compose up -d
```

Open [Streamlit](http://localhost:8501). The local backend health endpoint is [GET /health](http://localhost:8000/health). It checks API liveness, not retrieval or OpenRouter authentication. Submit a question and inspect its answer and sources to check the complete flow.

Build updated images with `docker compose build` before running the commands above. If a usable JSONL file already exists, skip collection and ingest that file. The explicit input path is required because the container's directory layout differs from the local checkout. The `model_cache` volume preserves embedding model downloads between ingestion and backend runs.

The backend Dockerfile installs `libatomic1` before installing Chromium. Both images install CPU-only PyTorch and use the single root `requirements.txt`. Docker currently installs unpinned requirements; `uv.lock` controls the local uv environment, not Docker builds.

## GCP deployment configuration

The owner deployed to an Ubuntu 24.04 LTS Minimal VM with 2 vCPUs, 4 GB RAM, and a 30 GB persistent boot disk. Install Docker Engine and the Compose plugin, transfer the current source and collected JSONL file, and create `.env` privately on the server. The JSONL file must be transferred separately from a Git clone.

The VM uses this `docker-compose.override.yml`, created on the server alongside the base Compose file:

```yaml
services:
  backend:
    restart: unless-stopped
    ports: !reset []
  frontend:
    restart: unless-stopped
    ports: !override
      - "80:8501"
```

This configuration requires Compose 2.24.4 or newer. Allow inbound HTTP on TCP port 80 for the VM in GCP. FastAPI stays on Docker's internal network. HTTPS is not enabled merely by allowing port 443.

Run on the VM from the project directory:

```bash
sudo docker compose config --quiet
sudo docker compose --parallel 1 build
sudo docker compose run --rm backend python -m app.ingest --input /app/data/raw/collected_documents.jsonl
sudo docker compose up -d
sudo docker compose ps
curl -fsS http://localhost/_stcore/health
```

Use the VM's current external IP with `http://`. Reserve a static IP if the address must survive stopping and starting the VM. ChromaDB lives in the server's `chroma_data` volume; the laptop's database does not automatically transfer. Back up the dataset and volume. Avoid `docker compose down -v`, which deletes named volumes.

After uploading code changes, rebuild the affected image and recreate its service. After changing `.env`, recreate the backend to reload its environment:

```bash
sudo docker compose build backend
sudo docker compose up -d --no-deps --force-recreate backend
```

## Troubleshooting

- **OpenRouter 401:** replace the key privately in `.env` and recreate the backend. A nonempty key is not necessarily valid.
- **Frontend reports a backend connection error:** this message also covers backend HTTP failures. Inspect `docker compose logs --tail=100 backend frontend` to distinguish connection failures from OpenRouter or retrieval errors.
- **Hugging Face authentication warning:** this is separate from OpenRouter authentication. Check whether the embedding step actually failed before treating the warning as a blocker.
- **Missing `scraper.dynamic` in a container:** rebuild the backend from the current source and inspect the build result before running collection again.
- **Empty collection:** inspect the JSONL data, configured URLs, robots rules, and scraper logs before ingestion. Deduplication can reduce the saved count.

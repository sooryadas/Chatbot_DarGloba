# Local Deployment Instructions

This guide runs the chatbot locally on Windows from **CMD** using the existing `uv` project. It does not use Docker.

## Before you start

- Install Docker is not required for this local workflow.
- Confirm Python 3.13 and `uv` are available:

```cmd
python --version
uv --version
```

- Open CMD in the project root:

```cmd
cd /d "E:\project\Projects for Companys\DarGlobal"
```

The project already has `pyproject.toml` and a root `requirements.txt`; do not run `uv init` again.

## 1. Install project dependencies

Synchronize the virtual environment from the project dependencies:

```cmd
uv sync
```

Install the Chromium browser required by the DarGlobal Playwright collector:

```cmd
uv run playwright install chromium
```

Playwright’s Python package and browser binaries are separate installs; keep the browser install aligned with the installed Playwright package. [Playwright browser setup](https://playwright.dev/python/docs/browsers)

## 2. Collect public website pages

From the project root:

```cmd
uv run python -m scraper.collect
```

The configured DarGlobal pages are collected with Playwright, and Wasalt pages use Requests and BeautifulSoup. The collector checks each site’s `robots.txt`, saves records to `data\raw\collected_documents.jsonl`, and skips unavailable URLs. The known DarGlobal Contact page is `https://darglobal.co.uk/get-in-touch`; `/contact` returns 404. Careers is skipped if it redirects outside the approved DarGlobal domains.

Check the output file and saved record count before continuing:

```cmd
type data\raw\collected_documents.jsonl
find /c /v "" data\raw\collected_documents.jsonl
```

If the count is zero, stop here and review the scraper log; ingestion cannot index an empty collection.

## 3. Ingest records into ChromaDB

Open a **second CMD window** in the project root and run:

```cmd
cd /d "E:\project\Projects for Companys\DarGlobal"
set CHROMA_PERSIST_DIRECTORY=..\data\chroma
uv run --directory backend python -m app.ingest
```

The ingestion command chunks collected text, creates embeddings with the configured Sentence Transformer model, and writes chunks and source metadata to the persistent ChromaDB directory.

## 4. Start the FastAPI backend

Open a **third CMD window** in the project root. Set the OpenRouter key in this same window before starting the server:

```cmd
cd /d "E:\project\Projects for Companys\DarGlobal"
set CHROMA_PERSIST_DIRECTORY=..\data\chroma
set OPENROUTER_API_KEY=PASTE_YOUR_NEW_OPENROUTER_KEY_HERE
set OPENROUTER_MODEL=openrouter/free
uv run --directory backend uvicorn app.main:app --reload --port 8000
```

Replace the placeholder locally; do not paste the key into this document or commit it. The application reads environment variables when the backend starts, so restart Uvicorn after changing the key.

Check the API health endpoint in a browser:

```text
http://localhost:8000/health
```

It should return `{"status":"ok"}`. This only checks that FastAPI is responding; ChromaDB retrieval and OpenRouter answering happen after a chat question is submitted.

## 5. Start the Streamlit frontend

Open a **fourth CMD window** in the project root:

```cmd
cd /d "E:\project\Projects for Companys\DarGlobal"
set BACKEND_URL=http://localhost:8000
uv run streamlit run frontend\app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Ask a question about information present in the collected pages and check that source links appear. Follow-up chat history is held in the current Streamlit browser session; transcripts are not persisted to the backend.

## Troubleshooting

### OpenRouter returns `401 Unauthorized`

The key is missing, invalid, revoked, or the backend started before the new key was set. Set a valid key in the backend CMD window and restart Uvicorn. You can check whether a key is configured without printing it:

```cmd
if defined OPENROUTER_API_KEY (echo OpenRouter key is set) else (echo OpenRouter key is missing)
```

“Key is set” does not prove the key is valid. OpenRouter uses the key as a Bearer token. [OpenRouter key check](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)

### Hugging Face Hub unauthenticated warning

The warning about an unauthenticated Hugging Face request is separate from OpenRouter. It can appear while the embedding model is downloaded. It does not by itself mean ingestion or chat failed; an OpenRouter `401` is an API key problem.

### DarGlobal pages are empty

Check the log for requested URL, redirect, status, and Playwright errors. Verify that `uv run playwright install chromium` completed in the same `uv` environment. Do not bypass `robots.txt` or the DarGlobal domain restriction. The `/contact` 404 is expected until the configured URL is changed to `/get-in-touch`.

### Backend cannot find ChromaDB data

Ensure `CHROMA_PERSIST_DIRECTORY=..\data\chroma` is set in both the ingestion and backend CMD windows, and run ingestion before starting the chat. `uv run --directory backend` changes the command's working directory to `backend`, so the path goes up one level to the project `data` folder.

## Stop the services

Press `Ctrl+C` in each CMD window running Uvicorn or Streamlit. Collected JSONL records and the local ChromaDB directory remain under `data\` for the next run.

This guide describes the intended local workflow. Collection, ingestion, and chat must still be verified on the machine where they are run.

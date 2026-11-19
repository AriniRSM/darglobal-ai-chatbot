# DarGlobal & Wasalt AI Companion

A local-first real-estate information chatbot built with Streamlit, retrieval-augmented generation (RAG), ChromaDB, sentence-transformer embeddings, LangGraph, and OpenRouter.

The assistant answers from the project's indexed public-source corpus and links to its sources. It does not have live property listings, current prices, or availability. It must say when a requested fact is not present instead of making it up.

## What is in the current corpus

- DarGlobal: source-linked project/company excerpts and public announcements.
- Wasalt: company background from Quara Holding and a public REGA licensing-directory entry. There are no Wasalt listings.
- REGA: open-data catalog descriptions. The underlying statistical files are not included.

The corpus and its provenance are in [`data/scraped/`](data/scraped/README.md). Direct Wasalt listing pages are excluded. DarGlobal's direct site crawler stops when it encounters an anti-bot interstitial; it does not try to bypass it. The DarGlobal excerpts in the corpus have their original public source URLs recorded.

## Run locally

Requirements: Python 3.11 or newer and an OpenRouter API key.

```bash
cd /path/to/darglobal-ai-chatbot
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Create a project-root `.env` file (it is ignored by Git) and set:

```dotenv
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openrouter/free
```

Then build or refresh the local vector index and start the app:

```bash
python3 -m app.ingestion.pipeline
python3 -m streamlit run app/main.py
```

Streamlit prints the local address, usually <http://localhost:8501>. The index is built locally from the JSONL corpus and any permitted raw HTML. Do not commit `.env` or an API key.

## Refresh source records

The bounded crawler and structured source extractor are separate from chat inference. The app does not crawl websites when someone asks a question.

```bash
python3 main.py inspect
python3 main.py crawl --max-pages 30 --delay 1.0
python3 -m app.scraper.structured --source all --limit 30 --delay 1
python3 -m app.ingestion.pipeline
```

Inspect the generated report and source records before indexing. Crawling is subject to each site's access rules and reuse terms. A robots.txt allowance is not permission to reuse content. The Wasalt crawler remains disabled unless its content-permission gate is explicitly configured after authorization; the structured Wasalt record is sourced from Quara Holding, not Wasalt listing pages.

## How it works

1. Public source records are cleaned and split into overlapping text chunks.
2. A local sentence-transformer model embeds the chunks into ChromaDB.
3. For each question, the retriever finds relevant chunks and applies a relevance threshold.
4. LangGraph routes capability, budget, clarification, no-evidence, and grounded-answer cases.
5. Grounded answers are generated through OpenRouter and streamed into the chat. The UI presents source links and a safe fallback when provider generation fails.

The welcome message and FAQ prompts describe the assistant's scope. Returning Home clears the conversation; chat history is not persisted.

## Project map

| Path | Purpose |
| --- | --- |
| `app/main.py` | Streamlit landing page, chat UI, welcome streaming, session-only conversation, citations, and user-safe error display. |
| `app/scraper/` | Robots-aware site inspection and bounded crawling, plus structured extraction of permitted public sources. |
| `app/ingestion/cleaner.py` | HTML text extraction and normalization. |
| `app/ingestion/pipeline.py` | Reads raw/structured records, chunks and embeds them, and updates ChromaDB and ingestion metadata. |
| `app/ingestion/embedder.py` | Local sentence-transformer embedding adapter used for indexing and search. |
| `app/ingestion/sources.py` | Maps captured HTML files to their source URLs from the crawl report. |
| `app/rag/retriever.py` | Similarity search over the local Chroma collection and relevance filtering. |
| `app/workflow/graph.py` | LangGraph decision flow, guardrails, and answer/fallback routing. |
| `app/llm/openrouter.py` | OpenRouter request construction, streaming, timeouts, and provider error handling. |
| `app/database/metadata_store.py` | SQLite crawl/index status and content-hash bookkeeping. |
| `data/scraped/` | Structured public-source records and corpus provenance notes. |
| `tests/` | Unit/guardrail checks and a question-based chatbot evaluation runner. |
| `Dockerfile`, `render.yaml` | Docker image and Render service configuration. |

## Run checks and evaluation

These commands are provided for the project owner to run in the activated virtual environment:

```bash
python3 -m unittest discover -s tests -v
python3 -m tests.evaluate_chatbot
```

The chatbot evaluation calls OpenRouter for cases that need generated answers. It therefore requires the local index and a configured API key. Results can vary with the free model selected by OpenRouter.

## Docker and deployment

Build and run locally:

```bash
docker build -t darglobal-ai-assistant .
docker run --rm -p 8501:10000 -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" darglobal-ai-assistant
```

The Dockerfile copies `data/scraped/` and builds `chroma_db/` inside the image using the cached embedding model. This keeps the ignored local Chroma files out of Git and makes the index reproducible from the source records. Ensure `data/scraped/` is included in the Git branch used for deployment. `render.yaml` describes a Docker web service but does not itself create or verify a deployment. Configure `OPENROUTER_API_KEY` as a Render secret; never put the key in YAML or source control.

## Remaining steps

1. Run the unit tests and evaluation locally; fix any failures and review generated answers against the cited excerpts.
2. Build the Chroma index from the committed corpus and decide on a safe, repeatable way to make that index available to the Docker build.
3. Build and run the Docker image locally, then verify the health endpoint, citations, fallbacks, and cold-start behavior.
4. Connect the GitHub repository to Render, configure the OpenRouter secret, deploy, and verify the live HTTPS URL end to end.
5. For richer content, obtain an approved DarGlobal data route and an authorized Wasalt listing feed or written permission before collecting those records.

Until deployment and URL checks are completed, this project should be treated as a local prototype rather than a publicly deployed chatbot.

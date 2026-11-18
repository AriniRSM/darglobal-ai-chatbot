# DarGlobal AI Assistant

A Python/Streamlit real-estate assistant prototype using Sentence Transformers embeddings, ChromaDB, LangChain chunking, a LangGraph retrieval workflow, and OpenRouter's free-model router.

## Current state

- App, offline ingestion, retrieval, and Docker/Render configuration are implemented.
- The knowledge base is empty. DarGlobal page requests currently return an anti-bot interstitial; those pages are not stored or bypassed.
- Wasalt content capture is paused. The official terms restrict copying/reproduction and commercial reuse of website materials outside Wasalt. Enable capture only after written permission and project review.
- The chatbot currently returns a grounded no-source fallback instead of inventing property details.
- A local OpenRouter key is configured in the ignored .env file; a live free-router completion test succeeded. The key is not committed. Render still requires an authenticated service setup and its own secret configuration.
- No Render URL exists yet. The local Streamlit health check passed. Docker image build and public deployment remain unverified because the Docker daemon is unavailable and the Render dashboard requires sign-in.

Do not describe this as a completed assignment until source access, indexing, live inference, and independent URL checks succeed.

## Architecture

    DarGlobal / Wasalt websites
      -> robots.txt and sitemap inspection
      -> bounded, cached page crawler
      -> raw HTML and crawl metadata
      -> HTML/JSON-LD extraction
      -> SHA-256 deduplication and SQLite tracking
      -> LangChain chunking
      -> Sentence Transformers embeddings
      -> persistent ChromaDB
      -> Streamlit chat -> LangGraph workflow -> OpenRouter
      -> grounded answer with source links or no-answer fallback

Crawler and indexer are separate from chat inference. The app never crawls sites at request time.

## Phase 1: inspect and scrape

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python main.py inspect
    python main.py crawl --max-pages 30 --delay 1.0

main.py is the inspection and crawl CLI. app/scraper/common.py contains robots.txt checks, sitemap parsing, same-host URL filtering, caching/retries, interstitial detection, and raw HTML capture. Site-specific settings are in app/scraper/darglobal.py and app/scraper/wasalt.py.

Reports are written under data/reports and raw HTML under data/raw/<source>/. Generated content is ignored by Git. The crawler does not bypass login, access controls, or bot protection.

### Observed inspection (18 November 2026)

- DarGlobal robots.txt returned HTTP 200 and allowed the research user agent. Its sitemap exposed 480 URLs. Page requests returned a 212-byte Imperva/Incapsula interstitial marked noindex,nofollow; the crawler rejects it. Five attempted URLs produced zero stored pages.
- Wasalt robots.txt returned HTTP 200 and announced ten sitemap files. Eight sampled sitemaps exposed 142,675 URLs. Wasalt's [official terms](https://wasalt.sa/en/s/terms-and-conditions) restrict copying/reproduction and commercial reuse outside the site. Page capture remains paused unless written permission is obtained. Five HTML pages saved during an initial smoke run were deleted after terms review.
- Wasalt's [terms of use](https://wasalt.sa/en/s/terms-of-use) say the platform does not own listed properties and ask users to verify listing details. Any authorized future use must keep this distinction and cite original listing pages.

A robots.txt allowance is not permission to reuse content. WASALT_CONTENT_PERMISSION=granted is reserved for use only after written authorization and review.

## Ingestion and index

app/ingestion/cleaner.py extracts readable text, headings, descriptions, and explicit JSON-LD values. Fields not present remain null. app/ingestion/pipeline.py chunks with LangChain, embeds with sentence-transformers/all-MiniLM-L6-v2, indexes in ChromaDB, and skips unchanged source hashes using SQLite records from app/database/metadata_store.py. app/ingestion/sources.py maps raw files to original URLs from the crawl report.

After approved source access and usable HTML are available:

    python -m app.ingestion.pipeline

Wasalt ingestion is skipped unless WASALT_CONTENT_PERMISSION=granted. Set that only after written permission. The schema includes project name, developer, location, country, property type, bedrooms, price, currency, amenities, description, source URL, and source. Values come only from page text or structured data; absent fields remain null.

## Chat and LLM

app/main.py is the Streamlit interface. app/rag/retriever.py runs vector search with a relevance floor. app/workflow/graph.py is the conditional LangGraph workflow: clarify a short question, answer from retrieved context when available, or return a no-source fallback. app/llm/openrouter.py calls OpenRouter's chat completions API with timeouts and rate-limit handling.

The default model is openrouter/free, which routes each request to an available free chat model. OpenRouter describes the router and chat endpoint at https://openrouter.ai/openrouter/free. Free model availability and limits can change.

Copy .env.example to .env for local development and set OPENROUTER_API_KEY. Never commit a real key. On Render, set the key as a secret. If the index is empty, the workflow does not call the model.

## Run locally

    streamlit run app/main.py

When no documents are indexed, the app returns a no-source fallback. This is intentional until verified source evidence is available.

## Docker and Render

The Dockerfile installs pinned dependencies, pre-downloads the embedding model, copies the prebuilt Chroma index, and binds Streamlit to 0.0.0.0:10000 (Render's default web port).

    python -m app.ingestion.pipeline
    docker build -t darglobal-ai-assistant .
    docker run --rm -p 8501:10000 -e OPENROUTER_API_KEY="$OPENROUTER_API_KEY" darglobal-ai-assistant

render.yaml defines one Docker web service. Connect the GitHub repository to Render, add OPENROUTER_API_KEY as a secret, and deploy. Render free services use an ephemeral filesystem and spin down after 15 idle minutes, so ChromaDB must be built into the image; cold starts may take about a minute. Limits: https://render.com/docs/free. No public URL is configured or verified yet.

## Evaluation

tests/evaluation_questions.json contains 20 planned questions across company facts, projects, locations, amenities, prices, availability, comparisons, follow-ups, unknowns, and unsupported questions. They have not been evaluated against a populated corpus.

    python -m unittest discover -s tests -v

Nine unit tests pass, covering crawler boundaries, the Wasalt permission gate, structured extraction, chunking/index bookkeeping with a synthetic fixture, empty retrieval, clarification, and missing-key handling. The live OpenRouter client returned a completion using a fictional fixture. The Streamlit health endpoint returned HTTP 200. Live retrieval against the official sites, embeddings for approved real pages, Docker build, and deployment remain unverified.

## Next steps

1. Obtain DarGlobal-approved access or a data feed; do not bypass its interstitial.
2. Obtain written Wasalt permission for storage and external reuse before enabling capture.
3. Run a small approved crawl and inspect representative data.
4. Build the Chroma index and evaluate retrieval/grounding with the 20 questions.
5. Configure the OpenRouter key in Render, connect GitHub, build, and deploy the Docker service.
6. Verify the public HTTPS URL, citations, fallback, and cold start.

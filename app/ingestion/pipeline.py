"""Offline raw HTML -> cleaned LangChain chunks -> ChromaDB indexing."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.database import metadata_store
from app.ingestion.cleaner import extract_document
from app.ingestion.embedder import LocalSentenceEmbeddings

RAW_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
CHROMA_DIR = os.getenv("CHROMA_PATH", "chroma_db")
COLLECTION = "darglobal_public_knowledge"

def _is_allowed_source(source):
    if source == "Wasalt":
        return os.getenv("WASALT_CONTENT_PERMISSION", "").lower() == "granted"
    return source == "DarGlobal"

def _store():
    from langchain_chroma import Chroma
    return Chroma(collection_name=COLLECTION, embedding_function=LocalSentenceEmbeddings(),
                  persist_directory=CHROMA_DIR, collection_metadata={"hnsw:space": "cosine"})

def ingest():
    splitter = RecursiveCharacterTextSplitter(chunk_size=850, chunk_overlap=120, add_start_index=True)
    store = None
    report = {"indexed_pages": 0, "skipped_unchanged": 0, "skipped_sources": [], "errors": []}
    for source_dir in sorted(RAW_DIR.iterdir() if RAW_DIR.exists() else []):
        if not source_dir.is_dir():
            continue
        source = "DarGlobal" if source_dir.name.lower() == "darglobal" else "Wasalt" if source_dir.name.lower() == "wasalt" else source_dir.name
        if not _is_allowed_source(source):
            report["skipped_sources"].append({"source": source, "reason": "content permission not configured"})
            continue
        for file in sorted(source_dir.glob("*.html")):
            url = None
            try:
                raw = file.read_bytes()
                from app.ingestion.sources import source_url_for_file
                url = source_url_for_file(file) or file.as_uri()
                page = extract_document(raw, source, url)
                page["source_url"] = url
                text = "\n".join([page["project_name"] or "", page["project_description"] or "", *page["headings"], page["text"]]).strip()
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if metadata_store.existing_hash(url) == content_hash:
                    report["skipped_unchanged"] += 1
                    continue
                chunks = splitter.split_documents([Document(page_content=text, metadata={
                    "source": source, "source_url": page["source_url"],
                    "project_name": page["project_name"] or "",
                    "location": page["location"] or "",
                    "category": page["property_type"] or "",
                    "content_hash": content_hash,
                    "scraped_at": datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat(),
                })])
                if store is None:
                    store = _store()
                if metadata_store.existing_hash(url):
                    try: store.delete(where={"source_url": page["source_url"]})
                    except Exception: pass
                ids = [hashlib.sha256(f"{page['source_url']}|{content_hash}|{i}".encode()).hexdigest() for i in range(len(chunks))]
                store.add_documents(chunks, ids=ids)
                metadata_store.record(url, source, "indexed", content_hash, chunks[0].metadata["scraped_at"],
                                      datetime.now(timezone.utc).isoformat(), len(chunks))
                report["indexed_pages"] += 1
            except Exception as exc:
                report["errors"].append({"file": str(file), "error": f"{type(exc).__name__}: {exc}"})
                if url: metadata_store.record(url, source, "failed", error=str(exc))
    return report

if __name__ == "__main__":
    import json
    print(json.dumps(ingest(), indent=2))

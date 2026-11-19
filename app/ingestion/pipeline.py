"""Offline raw HTML -> cleaned LangChain chunks -> ChromaDB indexing."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.database import metadata_store
from app.ingestion.cleaner import clean_text, extract_document
from app.ingestion.embedder import LocalSentenceEmbeddings

RAW_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
STRUCTURED_DIR = Path(os.getenv("STRUCTURED_DATA_DIR", str(RAW_DIR.parent / "scraped")))
CHROMA_DIR = os.getenv("CHROMA_PATH", "chroma_db")
COLLECTION = "darglobal_public_knowledge"

def _is_allowed_source(source):
    # Exact allowlist: no individual Wasalt listing or auction records.
    approved = {
        "DarGlobal",
        "DarGlobal official website",
        "DarGlobal news (Quara Holding public news page)",
        "DarGlobal news via Quara",
        "Wasalt public company profile (Quara Holding)",
        "Wasalt company profile (Quara)",
        "REGA Open Data catalog",
        "REGA FAL platform directory",
    }
    if source in approved:
        return True
    if source == "Wasalt":
        return os.getenv("WASALT_CONTENT_PERMISSION", "").lower() == "granted"
    return False

def _store():
    from langchain_chroma import Chroma
    return Chroma(collection_name=COLLECTION, embedding_function=LocalSentenceEmbeddings(),
                  persist_directory=CHROMA_DIR, collection_metadata={"hnsw:space": "cosine"})

def ingest():
    splitter = RecursiveCharacterTextSplitter(chunk_size=850, chunk_overlap=120, add_start_index=True)
    store = None
    report = {"indexed_pages": 0, "indexed_records": 0, "skipped_unchanged": 0, "skipped_sources": [], "errors": []}
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
    for file in sorted(STRUCTURED_DIR.glob("*.jsonl") if STRUCTURED_DIR.exists() else []):
        for line_number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                record = json.loads(line)
                source = record.get("source", "")
                if not _is_allowed_source(source):
                    report["skipped_sources"].append({"source": source, "reason": "source is not enabled for ingestion"})
                    continue
                title = record.get("title") or record.get("project_name") or ""
                source_url = record.get("url") or record.get("source_url") or file.resolve().as_uri()
                category_examples = record.get("public_property_category_examples") or []
                category_text = "; ".join(item.get("label", "") for item in category_examples if isinstance(item, dict))
                raw_text = record.get("text")
                description = record.get("project_description") or record.get("description") or ""
                if isinstance(raw_text, str) and raw_text.strip():
                    body_text = clean_text(raw_text)
                    sections = []
                    if title and title.casefold() not in body_text[:len(title) + 20].casefold():
                        sections.append(title)
                    if description and description.casefold() not in body_text.casefold():
                        sections.append(clean_text(description))
                    if category_text and category_text.casefold() not in body_text.casefold():
                        sections.append(f"Public property categories: {category_text}")
                    if record.get("license"):
                        sections.append(f"Reuse license: {record['license']}")
                    sections.append(body_text)
                    text = "\n".join(section for section in sections if section)
                else:
                    fields = [
                        f"Record type: {record.get('record_type', '')}",
                        f"Title: {title}",
                        f"Published: {record.get('published_at') or ''}",
                        f"Location: {record.get('location') or ''}",
                        f"Property type: {record.get('property_type') or ''}",
                        f"Description: {description}",
                        f"Founded year: {record.get('founded_year') or ''}",
                        f"Reported unique users: {record.get('reported_unique_users') or ''}",
                        f"REGA licensed: {record.get('rega_licensed')}",
                        f"Services: {', '.join(record.get('services') or [])}",
                        f"Public category examples: {category_text}",
                        f"Source URL: {source_url}",
                    ]
                    text = clean_text("\n".join(value for value in fields if value and not value.endswith(": ")))
                if len(text) < 40:
                    report["errors"].append({"file": str(file), "line": line_number, "error": "record has too little cleaned text"})
                    continue
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if metadata_store.existing_hash(source_url) == content_hash:
                    report["skipped_unchanged"] += 1
                    continue
                document = Document(page_content=text, metadata={
                    "source": source, "source_url": source_url,
                    "project_name": title or "Untitled source",
                    "location": record.get("location") or "",
                    "category": record.get("property_type") or record.get("record_type") or "",
                    "content_hash": content_hash,
                    "scraped_at": record.get("scraped_at") or record.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
                })
                chunks = splitter.split_documents([document])
                if store is None:
                    store = _store()
                if metadata_store.existing_hash(source_url):
                    try:
                        store.delete(where={"source_url": source_url})
                    except Exception:
                        pass
                ids = [hashlib.sha256(f"{source_url}|{content_hash}|{i}".encode()).hexdigest() for i in range(len(chunks))]
                store.add_documents(chunks, ids=ids)
                metadata_store.record(source_url, source, "indexed", content_hash,
                                      document.metadata["scraped_at"],
                                      datetime.now(timezone.utc).isoformat(), len(chunks))
                report["indexed_records"] += 1
            except Exception as exc:
                report["errors"].append({"file": str(file), "line": line_number,
                                         "error": f"{type(exc).__name__}: {exc}"})
    return report

if __name__ == "__main__":
    import json
    print(json.dumps(ingest(), indent=2))

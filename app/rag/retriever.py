"""Vector retrieval with a conservative relevance floor and source metadata."""
import os
import re
from pathlib import Path
from app.ingestion.pipeline import COLLECTION
from app.ingestion.embedder import LocalSentenceEmbeddings
import chromadb
from langchain_chroma import Chroma

MIN_RELEVANCE = float(os.getenv("RETRIEVAL_MIN_RELEVANCE", "0.48"))
COMPANY_OVERVIEW_RELEVANCE = 0.44
_COMPANY_OVERVIEW_QUERY = re.compile(
    r"\b(?:what does|what is|tell me about|describe)\s+(?:darglobal|wasalt)\b",
    re.IGNORECASE,
)

def retrieve(question, history=None, k=6):
    chroma_path = os.getenv("CHROMA_PATH", "chroma_db")
    if not (Path(chroma_path) / "chroma.sqlite3").exists():
        return []
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(COLLECTION)
    except Exception:
        return []
    if collection.count() == 0:
        return []
    store = Chroma(collection_name=COLLECTION, embedding_function=LocalSentenceEmbeddings(),
                   persist_directory=chroma_path,
                   collection_metadata={"hnsw:space": "cosine"})
    prior = [m.get("content", "") for m in (history or []) if m.get("role") == "user"][-2:]
    hits = store.similarity_search_with_relevance_scores(" ".join(prior + [question]), k=k)
    relevance_floor = MIN_RELEVANCE
    if _COMPANY_OVERVIEW_QUERY.search(question):
        relevance_floor = min(relevance_floor, COMPANY_OVERVIEW_RELEVANCE)
    return [{"text": doc.page_content, "metadata": doc.metadata, "score": float(score)}
            for doc, score in hits if score >= relevance_floor]

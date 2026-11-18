"""Vector retrieval with a conservative relevance floor and source metadata."""
import os
from pathlib import Path
from app.ingestion.pipeline import COLLECTION
from app.ingestion.embedder import LocalSentenceEmbeddings

MIN_RELEVANCE = float(os.getenv("RETRIEVAL_MIN_RELEVANCE", "0.28"))

def retrieve(question, history=None, k=6):
    chroma_path = os.getenv("CHROMA_PATH", "chroma_db")
    if not (Path(chroma_path) / "chroma.sqlite3").exists():
        return []
    import chromadb
    client = chromadb.PersistentClient(path=chroma_path)
    try:
        collection = client.get_collection(COLLECTION)
    except Exception:
        return []
    if collection.count() == 0:
        return []
    from langchain_chroma import Chroma
    store = Chroma(collection_name=COLLECTION, embedding_function=LocalSentenceEmbeddings(),
                   persist_directory=chroma_path,
                   collection_metadata={"hnsw:space": "cosine"})
    prior = [m.get("content", "") for m in (history or []) if m.get("role") == "user"][-2:]
    hits = store.similarity_search_with_relevance_scores(" ".join(prior + [question]), k=k)
    return [{"text": doc.page_content, "metadata": doc.metadata, "score": float(score)}
            for doc, score in hits if score >= MIN_RELEVANCE]

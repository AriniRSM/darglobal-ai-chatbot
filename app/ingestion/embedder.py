"""Sentence Transformers adapter implementing LangChain's Embeddings interface."""
import os
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer


class LocalSentenceEmbeddings(Embeddings):
    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.model = SentenceTransformer(self.model_name, device="cpu")

    def embed_documents(self, texts):
        vectors = self.model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text):
        vector = self.model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return vector.tolist()

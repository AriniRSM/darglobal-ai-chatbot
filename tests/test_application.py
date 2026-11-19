import os
import unittest
from unittest.mock import patch
from app.ingestion.cleaner import extract_document
from app.workflow.graph import ask
from app.llm.openrouter import generate, OpenRouterError
from app.ingestion import pipeline
from app.ingestion import sources

SAMPLE = b'''<html><head><title>Sample Tower</title><meta name="description" content="A sample residential tower."></head>
<body><main><h1>Sample Tower</h1><p>This is a long enough description with location details explicitly stated as Dubai. It has spaces for residents and local services.</p></main>
<script type="application/ld+json">{"@type":"ApartmentComplex","name":"Sample Tower","address":{"addressLocality":"Dubai","addressCountry":"AE"}}</script></body></html>'''

class ApplicationTests(unittest.TestCase):
    def test_cleaner_keeps_missing_price_null_and_reads_explicit_jsonld(self):
        doc = extract_document(SAMPLE, "DarGlobal", "https://example.test/tower")
        self.assertEqual(doc["project_name"], "Sample Tower")
        self.assertEqual(doc["location"], "Dubai")
        self.assertIsNone(doc["price"])
        self.assertEqual(doc["source_url"], "https://example.test/tower")

    @patch("app.workflow.graph.retrieve", return_value=[])
    def test_empty_retrieval_returns_no_source_fallback(self, _retrieve):
        result = ask("Tell me about the unknown residence", [])
        self.assertEqual(result["docs"], [])
        self.assertIn("couldn't find verified information", result["answer"])

    def test_ingestion_chunks_and_records_an_authorized_local_page(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        class FakeStore:
            def __init__(self): self.documents = []
            def add_documents(self, docs, ids): self.documents.extend(docs)
            def delete(self, where): pass
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source_dir = root / "darglobal"
            source_dir.mkdir()
            (source_dir / "page.html").write_bytes(SAMPLE)
            fake_store = FakeStore()
            with patch.object(pipeline, "RAW_DIR", root), \
                 patch.object(pipeline, "STRUCTURED_DIR", root / "scraped"), \
                 patch.object(pipeline, "_store", return_value=fake_store), \
                 patch.object(pipeline.metadata_store, "existing_hash", return_value=None), \
                 patch.object(pipeline.metadata_store, "record") as record, \
                 patch.object(sources, "source_url_for_file", return_value="https://darglobal.example/tower"):
                result = pipeline.ingest()
            self.assertEqual(result["indexed_pages"], 1)
            self.assertGreaterEqual(len(fake_store.documents), 1)
            self.assertTrue(all(d.metadata["source_url"] == "https://darglobal.example/tower" for d in fake_store.documents))
            record.assert_called_once()

    def test_short_input_asks_for_clarification(self):
        result = ask("?", [])
        self.assertTrue(result["clarification"])
        self.assertIn("Which project", result["answer"])

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
    def test_openrouter_fails_safely_without_key(self):
        with self.assertRaises(OpenRouterError):
            generate("question", [{"text": "evidence", "metadata": {"source": "DarGlobal", "source_url": "https://example.test"}}])

if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from app.scraper.common import is_internal_http_url, normalize_url, sitemap_locations
from app.scraper import wasalt

class Phase1Tests(unittest.TestCase):
    def test_url_scope_rejects_external_hosts_and_assets(self):
        base = "https://darglobal.co.uk"
        self.assertTrue(is_internal_http_url("https://darglobal.co.uk/projects/a", base))
        self.assertFalse(is_internal_http_url("https://elsewhere.example/a", base))
        self.assertFalse(is_internal_http_url("https://darglobal.co.uk/image.webp", base))

    def test_normalize_drops_fragment(self):
        self.assertEqual(normalize_url("https://darglobal.co.uk/a#details"), "https://darglobal.co.uk/a")

    def test_wasalt_content_capture_stays_paused_by_terms_gate(self):
        with patch.object(wasalt, "inspect_policy", return_value=(type("Policy", (), {"__dict__": {"base_url": "https://wasalt.sa"}})(), object())), \
             patch.object(wasalt, "inspect_terms", return_value={"status": 403, "accessible": False}), \
             patch.object(wasalt, "discover_pages", side_effect=AssertionError("must not crawl")):
            result = wasalt.crawl(max_pages=1)
        self.assertEqual(result["captured_pages"], 0)
        self.assertTrue(result["terms_review"]["content_reuse_restrictions_detected"])
        self.assertIn("paused", result["errors"][0].lower())

    def test_sitemap_parser_accepts_urlset(self):
        class Response:
            content = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.org/a</loc></url></urlset>'
            def raise_for_status(self): pass
        class Session:
            def get(self, *args, **kwargs): return Response()
        urls, errors = sitemap_locations(Session(), "https://example.org/sitemap.xml")
        self.assertEqual(urls, ["https://example.org/a"])
        self.assertEqual(errors, [])

if __name__ == "__main__": unittest.main()

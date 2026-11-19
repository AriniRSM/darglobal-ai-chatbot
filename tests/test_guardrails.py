import unittest
from unittest.mock import patch

from app.llm.openrouter import OpenRouterError
from app.workflow.graph import ask


def doc(text, url, score, source="DarGlobal"):
    return {
        "text": text,
        "score": score,
        "metadata": {"source": source, "source_url": url, "project_name": "Test source"},
    }


class GuardrailTests(unittest.TestCase):
    @patch("app.workflow.graph.retrieve", return_value=[])
    def test_capabilities_question_is_static_and_does_not_call_model(self, retrieve):
        with patch("app.workflow.graph.generate", side_effect=AssertionError("model should not run")):
            result = ask("What are your capabilities?")
        self.assertIn("DarGlobal", result["answer"])
        self.assertIn("Wasalt", result["answer"])
        self.assertIn("REGA", result["answer"])
        self.assertEqual(result["sources"], [])
        retrieve.assert_not_called()

    @patch("app.workflow.graph.retrieve", side_effect=AssertionError("budget routing should not search"))
    def test_budget_recommendation_discloses_no_live_inventory_or_current_prices(self, _retrieve):
        with patch("app.workflow.graph.generate", side_effect=AssertionError("budget routing should not call model")):
            result = ask("My budget is US$50 million. Find a suitable property for me.")
        self.assertIn("current unit pricing", result["answer"])
        self.assertIn("live inventory", result["answer"])
        self.assertEqual(result["sources"], [])

    @patch("app.workflow.graph.retrieve", return_value=[])
    def test_no_evidence_uses_abstention_without_model_call(self, _retrieve):
        with patch("app.workflow.graph.generate", side_effect=AssertionError("model should not run")):
            result = ask("Tell me the price of fictional Palm Nebula Tower")
        self.assertIn("couldn't find verified information", result["answer"])
        self.assertEqual(result["sources"], [])

    @patch("app.workflow.graph.retrieve")
    def test_source_panel_excludes_weaker_unrelated_retrievals(self, retrieve):
        retrieve.return_value = [
            doc("Azure villas in Oman", "https://quaraholding.com/azure", 0.82),
            doc("Same article second chunk", "https://quaraholding.com/azure", 0.78),
            doc("Company overview", "https://example.test/investor", 0.61),
            doc("Unrelated page", "https://example.test/other", 0.30),
        ]
        captured = {}
        def fake_generate(question, docs, history):
            captured["urls"] = [item["metadata"]["source_url"] for item in docs]
            return "Azure is in Oman."
        with patch("app.workflow.graph.generate", side_effect=fake_generate):
            result = ask("What was announced about Azure villas?")
        self.assertEqual([item["url"] for item in result["sources"]], ["https://quaraholding.com/azure"])
        self.assertEqual(set(captured["urls"]), {"https://quaraholding.com/azure"})

    @patch("app.workflow.graph.retrieve", return_value=[doc("Relevant text", "https://example.test", 0.8)])
    def test_provider_error_is_never_displayed_to_user(self, _retrieve):
        with patch("app.workflow.graph.generate", side_effect=OpenRouterError("HTTP 400 secret diagnostic")):
            result = ask("Tell me about this source")
        self.assertNotIn("400", result["answer"])
        self.assertNotIn("secret diagnostic", result["answer"])
        self.assertIn("try again shortly", result["answer"])

    @patch("app.workflow.graph.retrieve", return_value=[doc("Evidence", "https://example.test", 0.8)])
    def test_model_provider_failure_keeps_safe_answer_when_evidence_exists(self, _retrieve):
        with patch("app.workflow.graph.generate", side_effect=OpenRouterError("empty")):
            result = ask("Tell me about this source")
        self.assertEqual(result["answer"], "I couldn't generate a response right now. Please try again shortly.")


if __name__ == "__main__":
    unittest.main()

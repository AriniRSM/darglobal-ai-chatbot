"""Run a small answer-and-citation evaluation against the local Chroma index.

This uses the configured chat model for supported questions and therefore can
make OpenRouter requests. Run from the repository root after indexing sources.
"""
import json
import os
import re
import unicodedata
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env", override=False)

from app.workflow.graph import ask  # noqa: E402


def normalize_text(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join("-" if unicodedata.category(char) == "Pd" else char for char in value)
    return re.sub(r"\s+", " ", value)


def evaluate_case(case):
    result = ask(case["question"])
    answer = result.get("answer", "")
    normalized_answer = normalize_text(answer)
    missing_terms = [term for term in case.get("expected_answer_terms", [])
                     if normalize_text(term) not in normalized_answer]
    sources = result.get("sources", [])
    urls = [source.get("url", "") for source in sources]
    checks = {
        "answer_terms": not missing_terms,
        "expected_source_count": ("expected_source_count" not in case or
                                  len(sources) == case["expected_source_count"]),
        "expected_source_url": ("expected_source_url_contains" not in case or
                                any(case["expected_source_url_contains"] in url for url in urls)),
        "expected_source_domain": ("expected_source_domain" not in case or
                                   any(case["expected_source_domain"] in url for url in urls)),
    }
    return {
        "id": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "missing_terms": missing_terms,
        "answer": answer,
        "source_urls": urls,
    }


def main():
    try:
        import langchain_chroma  # noqa: F401
    except ModuleNotFoundError:
        print("Missing dependency 'langchain-chroma' in the active virtual environment. "
              "Run: python3 -m pip install -r requirements.txt")
        return 2
    chroma_path = Path(os.getenv("CHROMA_PATH", "chroma_db"))
    if not (chroma_path / "chroma.sqlite3").exists():
        print(f"No local Chroma index found at {chroma_path}. "
              "Run: python3 -m app.ingestion.pipeline")
        return 2
    cases = json.loads((ROOT / "tests/evaluation_cases.json").read_text(encoding="utf-8"))
    try:
        results = [evaluate_case(case) for case in cases]
    except ModuleNotFoundError as exc:
        if exc.name == "langchain_chroma":
            print("Missing dependency 'langchain-chroma' in the active virtual environment. "
                  "Run: python3 -m pip install -r requirements.txt")
            return 2
        raise
    passed = sum(item["passed"] for item in results)
    report = {"passed": passed, "total": len(results), "results": results}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

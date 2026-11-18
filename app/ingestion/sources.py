"""Map stored HTML filenames back to original source URLs from the crawl report."""
import json
from pathlib import Path

def source_url_for_file(path):
    source_dir = Path(path).parent.name
    report = Path("data/reports/crawl_report.json")
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
        for site in data.get("sites", []):
            if site.get("source", "").lower().replace(" ", "_") == source_dir:
                for page in site.get("pages", []):
                    if page.get("raw_html_path") and Path(page["raw_html_path"]).resolve() == Path(path).resolve():
                        return page.get("url")
    except (OSError, ValueError):
        pass
    return None

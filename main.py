"""Phase 1 command line: inspect source policies or capture public raw pages."""
import argparse
import json
from pathlib import Path
from app.scraper.pipeline import inspect_sources, crawl_sources


def main():
    parser = argparse.ArgumentParser(description="DarGlobal / Wasalt public website inspection and raw crawler")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="check robots.txt and discover public sitemap URLs")
    inspect.add_argument("--report", default="data/reports/source_inspection.json")
    crawl = sub.add_parser("crawl", help="capture bounded raw HTML from robots-allowed pages")
    crawl.add_argument("--max-pages", type=int, default=30, help="maximum pages per source website")
    crawl.add_argument("--delay", type=float, default=1.0, help="minimum pause between requests, seconds")
    crawl.add_argument("--output", default="data/raw")
    crawl.add_argument("--report", default="data/reports/crawl_report.json")
    args = parser.parse_args()
    if args.command == "inspect":
        result = inspect_sources()
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        result = crawl_sources(max_pages=args.max_pages, delay=args.delay, output_dir=args.output)
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

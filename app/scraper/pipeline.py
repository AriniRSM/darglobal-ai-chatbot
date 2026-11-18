"""Phase 1 inspection and bounded scraping orchestration."""
from datetime import datetime, timezone
from app.scraper import darglobal, wasalt

SITES = (darglobal, wasalt)

def inspect_sources():
    return {"inspected_at": datetime.now(timezone.utc).isoformat(),
            "phase": 1, "sites": [site.inspect() for site in SITES]}

def crawl_sources(max_pages=30, delay=1.0, output_dir="data/raw"):
    results = [site.crawl(max_pages=max_pages, delay=delay, output_dir=output_dir) for site in SITES]
    return {"crawled_at": datetime.now(timezone.utc).isoformat(), "phase": 1,
            "max_pages_per_source": max_pages, "request_delay_seconds": delay,
            "sites": results,
            "totals": {"discovered_pages": sum(s["discovered_pages"] for s in results),
                       "captured_pages": sum(s["captured_pages"] for s in results)}}

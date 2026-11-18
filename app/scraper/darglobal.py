"""DarGlobal-specific public website configuration and crawl."""
from app.scraper.common import make_session, inspect_policy, discover_pages, save_raw_page, discover_sitemaps, inspect_terms

SOURCE = "DarGlobal"
BASE_URL = "https://darglobal.co.uk"
SEEDS = ["https://darglobal.co.uk/", "https://darglobal.co.uk/projects", "https://darglobal.co.uk/about"]

def inspect():
    session = make_session()
    policy, robots = inspect_policy(session, BASE_URL)
    terms = inspect_terms(session, "https://darglobal.co.uk/privacy-policy")
    sitemaps, found, errors = ([], [], [])
    if robots:
        sitemaps, found, errors = discover_sitemaps(session, BASE_URL, policy.sitemaps or [])
    return {"source": SOURCE, "policy": policy.__dict__, "sitemap_count": len(sitemaps),
            "sitemap_examples": sitemaps[:10], "sitemaps_read": found, "terms_review": terms, "errors": errors}

def crawl(max_pages=30, delay=1.0, output_dir="data/raw"):
    session = make_session()
    policy, robots = inspect_policy(session, BASE_URL)
    if not robots:
        return {"source": SOURCE, "policy": policy.__dict__, "discovered_pages": 0, "captured_pages": 0, "errors": policy.notes}
    urls, errors = discover_pages(session, BASE_URL, SEEDS, robots, max_pages, delay, policy.sitemaps or [])
    pages = []
    for url in urls:
        try: pages.append(save_raw_page(session, url, SOURCE, output_dir))
        except Exception as exc: errors.append(f"Capture failed for {url}: {type(exc).__name__}: {exc}")
        if delay: __import__("time").sleep(delay)
    return {"source": SOURCE, "policy": policy.__dict__, "discovered_pages": len(urls),
            "captured_pages": sum(bool(p.get("captured")) for p in pages), "pages": pages, "errors": errors}

"""Wasalt-specific public website configuration and crawl."""
import os
from app.scraper.common import make_session, inspect_policy, discover_pages, save_raw_page, discover_sitemaps, inspect_terms

SOURCE = "Wasalt"
BASE_URL = "https://wasalt.sa"
SEEDS = ["https://wasalt.sa/en", "https://wasalt.sa/en/corporate",
         "https://wasalt.sa/en/properties-for-sale-in-riyadh"]

def inspect():
    session = make_session()
    policy, robots = inspect_policy(session, BASE_URL)
    terms = inspect_terms(session, "https://wasalt.sa/en/s/terms-and-conditions")
    # Manual review of official terms found restrictions on copying site materials
    # and using them commercially outside Wasalt. Keep capture paused, including
    # when the terms page itself is transiently inaccessible.
    terms["content_reuse_restrictions_detected"] = True
    terms["restriction_signals"] = [
        "official terms prohibit copying/reproducing published materials",
        "official terms prohibit commercial use of materials outside the website",
    ]
    terms["manual_review_required_for_release"] = True
    sitemaps, found, errors = ([], [], [])
    if robots:
        sitemaps, found, errors = discover_sitemaps(session, BASE_URL, policy.sitemaps or [])
    return {"source": SOURCE, "policy": policy.__dict__, "sitemap_count": len(sitemaps),
            "sitemap_examples": sitemaps[:10], "sitemaps_read": found, "terms_review": terms, "errors": errors}

def crawl(max_pages=30, delay=1.0, output_dir="data/raw"):
    session = make_session()
    policy, robots = inspect_policy(session, BASE_URL)
    terms = inspect_terms(session, "https://wasalt.sa/en/s/terms-and-conditions")
    # Manual review found a restriction; require a deployment-local flag after permission.
    permission_granted = os.getenv("WASALT_CONTENT_PERMISSION", "").lower() == "granted"
    terms["content_reuse_restrictions_detected"] = not permission_granted
    terms["restriction_signals"] = [
        "official terms restrict copying/reproducing published materials",
        "official terms restrict commercial use of materials outside the website",
    ]
    terms["permission_configured"] = permission_granted
    terms["manual_review_required_for_release"] = not permission_granted
    if not permission_granted:
        return {"source": SOURCE, "policy": policy.__dict__, "terms_review": terms,
                "discovered_pages": 0, "captured_pages": 0, "pages": [],
                "errors": ["Content capture paused: published terms restrict reuse outside Wasalt. Obtain written permission and set WASALT_CONTENT_PERMISSION=granted only after review."]}
    if not robots:
        return {"source": SOURCE, "policy": policy.__dict__, "terms_review": terms, "discovered_pages": 0, "captured_pages": 0, "errors": policy.notes}
    urls, errors = discover_pages(session, BASE_URL, SEEDS, robots, max_pages, delay, policy.sitemaps or [])
    pages = []
    for url in urls:
        try: pages.append(save_raw_page(session, url, SOURCE, output_dir))
        except Exception as exc: errors.append(f"Capture failed for {url}: {type(exc).__name__}: {exc}")
        if delay: __import__("time").sleep(delay)
    return {"source": SOURCE, "policy": policy.__dict__, "discovered_pages": len(urls),
            "terms_review": terms, "captured_pages": sum(bool(p.get("captured")) for p in pages), "pages": pages, "errors": errors}

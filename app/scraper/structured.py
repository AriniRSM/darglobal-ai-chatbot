"""Bounded, robots-aware extraction of public real-estate source pages.

Usage:
    python -m app.scraper.structured --source darglobal --limit 30

The Wasalt profile is collected from Quara Holding's public investment page.
No Wasalt listing pages are fetched because Wasalt's published terms restrict
automated extraction/copying of listing content. This module does not attempt
to evade that restriction or any site interstitial.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

USER_AGENT = "DarGlobalAssignmentResearchBot/0.1 (+public-site research; respects robots.txt)"
TIMEOUT = 20
DARGLOBAL_HOST = "darglobal.co.uk"
DARGLOBAL_ROOT = f"https://{DARGLOBAL_HOST}"
DARGLOBAL_SEEDS = (
    f"{DARGLOBAL_ROOT}/projects",
    f"{DARGLOBAL_ROOT}/press",
    f"{DARGLOBAL_ROOT}/blog",
    f"{DARGLOBAL_ROOT}/investor",
)
DARGLOBAL_PATH = re.compile(r"/(projects?|press|news|blog|investor)(/|$)", re.I)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7"})
    return session


def _robots(session: requests.Session, root: str) -> tuple[RobotFileParser | None, list[str], str | None]:
    robots_url = urljoin(root.rstrip("/") + "/", "robots.txt")
    try:
        response = session.get(robots_url, timeout=TIMEOUT)
        response.raise_for_status()
        parser = RobotFileParser(robots_url)
        lines = response.text.splitlines()
        parser.parse(lines)
        sitemaps = [line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("sitemap:")]
        return parser, sitemaps, None
    except requests.RequestException as exc:
        return None, [], f"Cannot verify robots.txt; host crawl stopped ({type(exc).__name__})."


def _same_host(url: str, root: str) -> bool:
    parsed, base = urlparse(url), urlparse(root)
    return parsed.scheme in ("http", "https") and parsed.netloc.lower() == base.netloc.lower()


def _interstitial(response: requests.Response, soup: BeautifulSoup) -> bool:
    body = response.text[:8192].lower()
    meta = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    directives = (meta.get("content", "").lower() if meta else "")
    return any(term in body for term in ("incapsula_resource", "imperva", "captcha", "access denied")) or (
        "noindex" in directives and "nofollow" in directives and len(response.content) < 4096
    )


def _candidate_urls(root: str, seeds: tuple[str, ...], robots: RobotFileParser,
                    sitemap_urls: list[str], limit: int) -> tuple[list[str], list[str]]:
    """Return only sitemap/seed URLs allowed by robots; do not pre-fetch pages."""
    queue = list(seeds)
    errors: list[str] = []
    pending_sitemaps = list(sitemap_urls[:8])
    visited_sitemaps: set[str] = set()
    while pending_sitemaps and len(visited_sitemaps) < 8:
        sitemap_url = pending_sitemaps.pop(0)
        if sitemap_url in visited_sitemaps or not _same_host(sitemap_url, root) or not robots.can_fetch(USER_AGENT, sitemap_url):
            continue
        visited_sitemaps.add(sitemap_url)
        try:
            response = requests.get(sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            response.raise_for_status()
            xml_root = ET.fromstring(response.content)
            root_kind = xml_root.tag.rsplit("}", 1)[-1].lower()
            locs = [node.text.strip() for node in xml_root.iter()
                    if node.tag.rsplit("}", 1)[-1].lower() == "loc" and node.text]
            if root_kind == "sitemapindex":
                pending_sitemaps.extend(locs[:8 - len(visited_sitemaps)])
            else:
                for loc in locs:
                    url = urldefrag(loc)[0]
                    if _same_host(url, root) and DARGLOBAL_PATH.search(urlparse(url).path):
                        queue.append(url)
        except (requests.RequestException, ET.ParseError) as exc:
            errors.append(f"Could not read sitemap {sitemap_url}: {type(exc).__name__}.")

    output: list[str] = []
    seen: set[str] = set()
    for raw_url in queue:
        url = urldefrag(raw_url.strip())[0]
        if url in seen or not _same_host(url, root) or not DARGLOBAL_PATH.search(urlparse(url).path):
            continue
        seen.add(url)
        if robots.can_fetch(USER_AGENT, url):
            output.append(url)
        if len(output) >= limit:
            break
    if not output and not errors:
        errors.append("No seed or sitemap URLs in target sections are allowed by robots.txt.")
    return output, errors

def _jsonld_objects(soup: BeautifulSoup) -> list[dict]:
    found: list[dict] = []
    def visit(value):
        if isinstance(value, dict):
            found.append(value)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            visit(json.loads(script.string or script.get_text()))
        except (json.JSONDecodeError, TypeError):
            continue
    return found


def _first(objects: list[dict], *keys: str):
    for obj in objects:
        for key in keys:
            value = obj.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _as_text(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("name") or value.get("value") or value.get("@id")
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item)
    if value is None:
        return None
    text = re.sub(r"\s+", " ", BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)).strip()
    return text or None


def _extract(url: str, response: requests.Response) -> dict | None:
    soup = BeautifulSoup(response.content, "html.parser")
    if _interstitial(response, soup):
        return None
    objects = _jsonld_objects(soup)
    title = soup.select_one("h1").get_text(" ", strip=True) if soup.select_one("h1") else None
    title = title or _as_text(_first(objects, "headline", "name"))
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    description = _as_text(_first(objects, "description", "abstract"))
    if not description:
        meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        description = _as_text(meta.get("content")) if meta else None
    address = _first(objects, "address", "location")
    if isinstance(address, dict):
        location = ", ".join(filter(None, (_as_text(address.get(k)) for k in ("addressLocality", "addressRegion", "addressCountry"))))
    else:
        location = _as_text(address)
    property_type = _as_text(_first(objects, "category", "additionalType"))
    if not property_type:
        known_types = {"apartment", "house", "residence", "singlefamilyresidence", "villa", "hotel", "commercialproperty"}
        for obj in objects:
            schema_type = obj.get("@type", [])
            schema_types = schema_type if isinstance(schema_type, list) else [schema_type]
            candidate = next((str(value) for value in schema_types if str(value).rsplit("/", 1)[-1].lower() in known_types), None)
            if candidate:
                property_type = candidate.rsplit("/", 1)[-1]
                break
    path = urlparse(url).path.lower()
    category = "news" if re.search(r"/(press|news|blog)(/|$)", path) else "project" if "/project" in path else "company"
    main = soup.find("main") or soup.find("article") or soup.body
    if main:
        main = BeautifulSoup(str(main), "html.parser")
        for element in main.select("script,style,noscript,svg,nav,footer,header,form,button"):
            element.decompose()
        raw_lines = [re.sub(r"\s+", " ", line).strip() for line in main.get_text("\n", strip=True).splitlines()]
        page_text = "\n".join(line for i, line in enumerate(raw_lines) if line and (i == 0 or line != raw_lines[i - 1]))
    else:
        page_text = None
    if not description and page_text:
        description = page_text[:1200]
    if not property_type and category == "project":
        match = re.search(r"\b(villas?|apartments?|residences?|hotel|mixed[- ]use|commercial|residential)\b", page_text or "", re.I)
        property_type = match.group(0) if match else None
    if not location:
        location_match = re.search(r"\b(Riyadh|Jeddah|Wadi Safar|Muscat|Dubai|Doha|London|Marbella|Athens)\b", f"{title or ''} {description or ''} {page_text or ''}", re.I)
        location = location_match.group(0) if location_match else None
    published = _as_text(_first(objects, "datePublished", "dateCreated"))
    if not published:
        time_tag = soup.find("time", attrs={"datetime": True})
        published = time_tag.get("datetime") if time_tag else None
    return {
        "source": "DarGlobal", "record_type": category, "title": title,
        "location": location, "property_type": property_type,
        "published_at": published, "description": description, "text": page_text,
        "url": url, "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def scrape_darglobal(limit: int = 30, delay: float = 1.0) -> dict:
    session = _session()
    robots, sitemaps, error = _robots(session, DARGLOBAL_ROOT)
    if not robots:
        return {"source": "DarGlobal", "status": "stopped", "records": [], "error": error}
    urls, errors = _candidate_urls(DARGLOBAL_ROOT, DARGLOBAL_SEEDS, robots, sitemaps, limit)
    # The official projects directory links directly to detail pages whose URL
    # slugs are not always nested beneath /projects/. Discover only links from
    # that directory, on the same host, and still require robots permission.
    projects_url = f"{DARGLOBAL_ROOT}/projects"
    if robots.can_fetch(USER_AGENT, projects_url):
        try:
            listing = session.get(projects_url, timeout=TIMEOUT)
            listing.raise_for_status()
            listing_soup = BeautifulSoup(listing.content, "html.parser")
            if _interstitial(listing, listing_soup):
                errors.append("Official projects directory returned an anti-bot interstitial; no bypass attempted.")
            else:
                discovered = []
                for link in listing_soup.select("a[href]"):
                    candidate = urldefrag(urljoin(projects_url, link.get("href", "")))[0]
                    path = urlparse(candidate).path.rstrip("/")
                    if (not _same_host(candidate, DARGLOBAL_ROOT) or not path or path == "/projects"
                            or re.search(r"\.(?:pdf|jpg|jpeg|png|webp|svg|css|js)$", path, re.I)
                            or any(part in path.lower() for part in ("/press", "/blog", "/investor", "/contact", "/privacy", "/terms"))):
                        continue
                    if robots.can_fetch(USER_AGENT, candidate):
                        discovered.append(candidate)
                urls = list(dict.fromkeys([projects_url, *discovered, *urls]))[:max(1, limit)]
        except requests.RequestException as exc:
            errors.append(f"Could not discover project pages from the official projects directory ({type(exc).__name__}).")
    records: list[dict] = []
    for url in urls:
        try:
            if not robots.can_fetch(USER_AGENT, url):
                continue
            response = session.get(url, timeout=TIMEOUT)
            if response.status_code in (401, 403, 429):
                errors.append(f"Access/rate limit response HTTP {response.status_code}; stopped without retrying this page.")
                if response.status_code in (401, 403, 429):
                    break
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", "").lower():
                continue
            record = _extract(url, response)
            if record:
                records.append(record)
            elif _interstitial(response, BeautifulSoup(response.content, "html.parser")):
                errors.append("Anti-bot interstitial detected; stopped without attempting to bypass it.")
                break
        except requests.RequestException as exc:
            errors.append(f"{url}: {type(exc).__name__}")
        time.sleep(max(0.0, delay))
    return {"source": "DarGlobal", "status": "completed" if records else "no_accessible_content",
            "discovered_pages": len(urls), "record_count": len(records), "records": records, "errors": errors}


def scrape_quara_darglobal_news(session: requests.Session | None = None) -> dict:
    """Collect DarGlobal headlines published on Quara Holding's public news page."""
    root = "https://www.quaraholding.com"
    page_url = f"{root}/en/news"
    session = session or _session()
    robots_url = f"{root}/robots.txt"
    try:
        robots_response = session.get(robots_url, timeout=TIMEOUT)
        if robots_response.status_code >= 500 or robots_response.status_code in (401, 403):
            return {"source": "DarGlobal (Quara public news)", "status": "stopped", "records": [],
                    "errors": [f"Quara robots.txt returned HTTP {robots_response.status_code}; news fetch stopped."]}
        robots = RobotFileParser(robots_url)
        robots.parse(robots_response.text.splitlines() if robots_response.status_code == 200 else [])
        if not robots.can_fetch(USER_AGENT, page_url):
            return {"source": "DarGlobal (Quara public news)", "status": "excluded_by_robots", "records": [], "errors": []}
        response = session.get(page_url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"source": "DarGlobal (Quara public news)", "status": "stopped", "records": [],
                "errors": [f"Could not fetch Quara's public DarGlobal news page ({type(exc).__name__})."]}

    soup = BeautifulSoup(response.content, "html.parser")
    if _interstitial(response, soup):
        return {"source": "DarGlobal (Quara public news)", "status": "blocked", "records": [],
                "errors": ["Quara news page returned an interstitial; no bypass attempted."]}
    records = []
    for link in soup.select("a[href]"):
        label = _as_text(link.get_text(" ", strip=True)) or ""
        article_url = urljoin(page_url, link.get("href", ""))
        article_path = urlparse(article_url).path
        if (urlparse(article_url).netloc.lower() != urlparse(root).netloc.lower()
                or not article_path.startswith("/en/news/")
                or "darglobal" not in label.lower()):
            continue
        date_match = re.search(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b", label)
        if not date_match:
            continue
        date_value = None
        if date_match:
            try:
                date_value = datetime.strptime(date_match.group(1), "%B %d, %Y").date().isoformat()
            except ValueError:
                pass
        title = re.sub(r"^DarGlobal\s+", "", label, flags=re.I)
        title = re.sub(r"^([A-Z][a-z]+ \d{1,2}, \d{4})\s+", "", title)
        title = re.sub(r"\s+Learn More$", "", title, flags=re.I).strip()
        if not title:
            continue
        type_match = re.search(r"\b(villas?|apartments?|residences?|hotel|community|project)\b", title, re.I)
        location_match = re.search(r"\b(Oman|Wadi Safar|Diriyah|Riyadh|Jeddah|Dubai|Doha|London)\b", title, re.I)
        records.append({
            "source": "DarGlobal news (Quara Holding public news page)",
            "record_type": "news",
            "title": title,
            "published_at": date_value,
            "location": location_match.group(0) if location_match else None,
            "property_type": type_match.group(0) if type_match else None,
            "url": article_url,
            "source_url": page_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return {"source": "DarGlobal (Quara public news)", "status": "completed" if records else "no_records",
            "discovered_pages": 1, "record_count": len(records), "records": records, "errors": []}


def scrape_wasalt_public(session: requests.Session | None = None) -> dict:
    """Extract Wasalt facts from Quara Holding's public profile, not wasalt.sa."""
    root = "https://www.quaraholding.com"
    page_url = f"{root}/en/investments/wasalt"
    session = session or _session()
    robots_url = f"{root}/robots.txt"
    try:
        robots_response = session.get(robots_url, timeout=TIMEOUT)
        # RFC 9309 treats 4xx robots responses as unavailable; Quara has no robots file (404).
        if robots_response.status_code >= 500 or robots_response.status_code in (401, 403):
            return {"source": "Wasalt", "status": "stopped", "records": [],
                    "errors": [f"Quara robots.txt returned HTTP {robots_response.status_code}; profile fetch stopped."]}
        robots = RobotFileParser(robots_url)
        robots.parse(robots_response.text.splitlines() if robots_response.status_code == 200 else [])
        if not robots.can_fetch(USER_AGENT, page_url):
            return {"source": "Wasalt", "status": "excluded_by_robots", "records": [], "errors": []}
        response = session.get(page_url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"source": "Wasalt", "status": "stopped", "records": [],
                "errors": [f"Could not fetch Quara's public Wasalt profile ({type(exc).__name__})."]}

    soup = BeautifulSoup(response.content, "html.parser")
    if _interstitial(response, soup):
        return {"source": "Wasalt", "status": "blocked", "records": [],
                "errors": ["Quara profile returned an interstitial; no bypass attempted."]}
    main = soup.find("main") or soup.body
    text = _as_text(main.get_text(" ", strip=True)) if main else ""
    title = soup.select_one("h1")
    title = title.get_text(" ", strip=True) if title else "Wasalt"
    paragraphs = [p.get_text(" ", strip=True) for p in (main.select("p") if main else [])]
    categories = []
    for link in (main.select("a[href]") if main else []):
        href = link.get("href", "")
        label = _as_text(link.get_text(" ", strip=True))
        category_label = label.lower() if label else ""
        if label and "wasalt.com" in href.lower() and any(term in category_label for term in ("for sale", "for rent", "apartment", "villa", "property", "properties", "land")):
            categories.append({"label": label, "url": href})
    services = []
    for service in ("Wasalt Properties", "Wasalt Auctions", "Wasalt Matchmaker", "Wasalt Projects"):
        if service.lower() in text.lower():
            services.append(service)
    year_match = re.search(r"Founded in (\d{4})", text, re.I)
    users_match = re.search(r"over\s+([\d,]+)\s+unique users", text, re.I)
    record = {
        "source": "Wasalt public company profile (Quara Holding)",
        "record_type": "platform_profile",
        "title": title,
        "founded_year": year_match.group(1) if year_match else None,
        "reported_unique_users": users_match.group(1) if users_match else None,
        "rega_licensed": "licensed by rega" in text.lower(),
        "services": services,
        "public_property_category_examples": categories,
        "source_url": page_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
    }
    return {"source": "Wasalt", "status": "completed", "discovered_pages": 1,
            "record_count": 1, "records": [record],
            "note": "Profile facts and category links came from Quara Holding; no Wasalt listing pages or listing details were fetched."}


def scrape_rega_wasalt_license(session: requests.Session | None = None) -> dict:
    """Collect only REGA's public company-license directory entry for Wasalt."""
    root = "https://rega.gov.sa"
    page_url = f"{root}/en/rega-services/platforms/fal-real-estate-brokerage/?cardsPage=13"
    session = session or _session()
    try:
        robots_response = session.get(f"{root}/robots.txt", timeout=TIMEOUT)
        if robots_response.status_code >= 500 or robots_response.status_code in (401, 403):
            return {"source": "REGA FAL platform directory", "status": "stopped", "records": [],
                    "errors": [f"REGA robots.txt returned HTTP {robots_response.status_code}; directory fetch stopped."]}
        robots = RobotFileParser(f"{root}/robots.txt")
        robots.parse(robots_response.text.splitlines() if robots_response.status_code == 200 else [])
        if not robots.can_fetch(USER_AGENT, page_url):
            return {"source": "REGA FAL platform directory", "status": "excluded_by_robots", "records": [], "errors": []}
        response = session.get(page_url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"source": "REGA FAL platform directory", "status": "stopped", "records": [],
                "errors": [f"Could not fetch REGA's public platform directory ({type(exc).__name__})."]}

    soup = BeautifulSoup(response.content, "html.parser")
    if _interstitial(response, soup):
        return {"source": "REGA FAL platform directory", "status": "blocked", "records": [],
                "errors": ["REGA directory returned an interstitial; no bypass attempted."]}
    text = _as_text((soup.find("main") or soup.body or soup).get_text(" ", strip=True)) or ""
    match = re.search(r"Broker:\s*wasalt\s+Company:\s*wasalt Real Estate Services Company\s+https://wasalt\.sa/", text, re.I)
    excerpt = match.group(0) if match else ""
    if not excerpt:
        return {"source": "REGA FAL platform directory", "status": "no_matching_entry", "records": [],
                "errors": ["Wasalt's company entry was not present in the fetched REGA directory page."]}
    record = {
        "source": "REGA FAL platform directory",
        "record_type": "license_directory_entry",
        "title": "Wasalt Real Estate Services Company — REGA FAL directory",
        "text": excerpt,
        "source_url": page_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"source": "REGA FAL platform directory", "status": "completed", "record_count": 1,
            "records": [record]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape allowed public DarGlobal project and news pages; report restricted sources without fetching them.")
    parser.add_argument("--source", choices=("darglobal", "wasalt", "all"), default="all")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--output", default="data/scraped")
    args = parser.parse_args()
    results = []
    if args.source in ("darglobal", "all"):
        results.append(scrape_darglobal(max(1, args.limit), args.delay))
        results.append(scrape_quara_darglobal_news())
    if args.source in ("wasalt", "all"):
        results.append(scrape_wasalt_public())
        results.append(scrape_rega_wasalt_license())
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        source_slug = result["source"].lower().replace(" (quara public news)", "_quara_news").replace(" (quara holding)", "_quara")
        source_slug = re.sub(r"[^a-z0-9_]+", "_", source_slug).strip("_")
        name = source_slug + ".jsonl"
        if result["records"]:
            (out_dir / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result["records"]), encoding="utf-8")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "results": [
        {k: v for k, v in result.items() if k != "records"} for result in results
    ]}
    (out_dir / "scrape_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

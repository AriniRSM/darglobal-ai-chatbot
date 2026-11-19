"""Shared conservative crawling primitives for public website inspection."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
import hashlib
import time
import xml.etree.ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

USER_AGENT = "DarGlobalAssignmentResearchBot/0.1 (+public-site research; respects robots.txt)"
TIMEOUT_SECONDS = 20

@dataclass
class SitePolicy:
    base_url: str
    robots_url: str
    robots_status: int | None = None
    robots_accessible: bool = False
    allowed_by_robots: bool = False
    sitemaps: list[str] | None = None
    disallow_rules: list[str] | None = None
    notes: list[str] | None = None


def make_session(cache_name: str = "data/cache/http") -> requests.Session:
    """Create a retrying session, using requests-cache when installed."""
    try:
        import requests_cache
        session = requests_cache.CachedSession(cache_name, expire_after=86400,
                                               allowable_methods=("GET",), stale_if_error=True)
    except ImportError:
        session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7"})
    retry = Retry(total=2, connect=2, read=1, status=2, backoff_factor=1.0,
                  status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET"}),
                  respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def inspect_policy(session: requests.Session, base_url: str) -> tuple[SitePolicy, RobotFileParser | None]:
    base_url = base_url.rstrip("/")
    robots_url = urljoin(base_url + "/", "robots.txt")
    policy = SitePolicy(base_url, robots_url, sitemaps=[], disallow_rules=[], notes=[])
    rp = RobotFileParser(robots_url)
    try:
        response = session.get(robots_url, timeout=TIMEOUT_SECONDS)
        policy.robots_status = response.status_code
        if response.status_code != 200:
            policy.notes.append(f"robots.txt returned HTTP {response.status_code}; crawling is disabled for this host.")
            return policy, None
        lines = response.text.splitlines()
        rp.parse(lines)
        policy.robots_accessible = True
        policy.allowed_by_robots = rp.can_fetch(USER_AGENT, base_url + "/")
        for line in lines:
            name, sep, value = line.partition(":")
            if not sep:
                continue
            if name.strip().lower() == "sitemap":
                policy.sitemaps.append(value.strip())
            elif name.strip().lower() == "disallow" and value.strip():
                policy.disallow_rules.append(value.strip())
        if not policy.sitemaps:
            policy.notes.append("No Sitemap directive found in robots.txt; common sitemap paths will be checked.")
        return policy, rp
    except requests.RequestException as exc:
        policy.notes.append(f"Could not read robots.txt; crawling is disabled for this host: {type(exc).__name__}: {exc}")
        return policy, None


def sitemap_locations(session: requests.Session, sitemap_url: str, max_children: int = 8) -> tuple[list[str], list[str]]:
    """Read URL sets and bounded sitemap indexes. Never fetch page URLs here."""
    urls: list[str] = []
    errors: list[str] = []
    pending = [sitemap_url]
    visited: set[str] = set()
    while pending and len(visited) < max_children:
        current = pending.pop(0)
        if current in visited:
            continue
        visited.add(current)
        try:
            response = session.get(current, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            root_type = root.tag.rsplit("}", 1)[-1].lower()
            locs = [node.text.strip() for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "loc" and node.text]
            if root_type == "sitemapindex":
                pending.extend(locs[:max_children - len(visited)])
            elif root_type == "urlset":
                urls.extend(locs)
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            errors.append(f"{current}: {type(exc).__name__}: {exc}")
    return urls, errors


def discover_sitemaps(session: requests.Session, base_url: str, robots_sitemaps: list[str]) -> tuple[list[str], list[str], list[str]]:
    candidates = robots_sitemaps or [urljoin(base_url + "/", path) for path in ("sitemap.xml", "sitemap_index.xml", "sitemap-index.xml")]
    urls: list[str] = []
    found: list[str] = []
    errors: list[str] = []
    for sitemap_url in candidates[:8]:
        before = len(urls)
        sitemap_urls, sitemap_errors = sitemap_locations(session, sitemap_url)
        urls.extend(sitemap_urls)
        errors.extend(sitemap_errors)
        if len(urls) > before:
            found.append(sitemap_url)
    return urls, found, errors


def inspect_terms(session: requests.Session, terms_url: str) -> dict:
    """Check a site's published reuse restrictions without retaining the terms page."""
    try:
        response = session.get(terms_url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        text = " ".join(soup.get_text(" ", strip=True).lower().split())
        if "incapsula_resource" in response.text[:4096].lower() or "imperva" in response.text[:4096].lower():
            return {"url": terms_url, "status": response.status_code, "accessible": False,
                    "content_reuse_restrictions_detected": None, "restriction_signals": [],
                    "error": "anti-bot/interstitial response"}
        restrictions = []
        if any(term in text for term in ("copy", "reproduce", "modify the materials", "نسخها", "نسخ المواد", "تعديل المواد")):
            restrictions.append("terms mention copying/reproducing site materials")
        if (("commercial purpose" in text and ("outside the website" in text or "outside website" in text))
                or ("تجاري" in text and ("خارج الموقع" in text or "خارج موقع" in text))):
            restrictions.append("terms mention commercial use outside the website")
        return {"url": terms_url, "status": response.status_code, "accessible": True,
                "content_reuse_restrictions_detected": bool(restrictions), "restriction_signals": restrictions}
    except requests.RequestException as exc:
        return {"url": terms_url, "status": getattr(getattr(exc, "response", None), "status_code", None),
                "accessible": False, "content_reuse_restrictions_detected": None,
                "restriction_signals": [], "error": f"{type(exc).__name__}: {exc}"}


def normalize_url(url: str) -> str:
    return urldefrag(url.strip())[0]


def is_internal_http_url(url: str, base_url: str) -> bool:
    parsed, base = urlparse(url), urlparse(base_url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != base.netloc.lower():
        return False
    path = parsed.path.lower()
    return not any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".zip", ".mp4", ".mp3"))


def discover_pages(session: requests.Session, base_url: str, seeds: list[str], robots: RobotFileParser,
                   max_pages: int, delay: float, sitemap_directives: list[str] | None = None) -> tuple[list[str], list[str]]:
    sitemap_urls, _, errors = discover_sitemaps(session, base_url, sitemap_directives or [])
    queue = list(dict.fromkeys([*seeds, *sitemap_urls]))
    seen: set[str] = set()
    pages: list[str] = []
    while queue and len(pages) < max_pages:
        url = normalize_url(queue.pop(0))
        if url in seen or not is_internal_http_url(url, base_url):
            continue
        seen.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            continue
        pages.append(url)
        # Bounded one-hop link discovery. The later page capture reuses the GET cache.
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
            if response.status_code == 200 and "html" in response.headers.get("Content-Type", "").lower():
                soup = BeautifulSoup(response.content, "html.parser")
                for anchor in soup.select("a[href]"):
                    candidate = normalize_url(urljoin(url, anchor.get("href", "")))
                    if candidate not in seen and is_internal_http_url(candidate, base_url):
                        queue.append(candidate)
        except requests.RequestException as exc:
            errors.append(f"Link discovery failed for {url}: {type(exc).__name__}: {exc}")
        if delay:
            time.sleep(delay)
    return pages, errors


def save_raw_page(session: requests.Session, url: str, source: str, output_dir: str) -> dict:
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return {"url": url, "source": source, "status": response.status_code,
                "content_type": content_type, "captured": False, "reason": "non-HTML response"}
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    headings = [h.get_text(" ", strip=True) for h in soup.select("h1,h2")[:30]]
    body_prefix = response.text[:4096].lower()
    robots_meta = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "robots"})
    robots_value = robots_meta.get("content", "").lower() if robots_meta else ""
    if "incapsula_resource" in body_prefix or "imperva" in body_prefix or ("noindex" in robots_value and "nofollow" in robots_value and len(response.content) < 2048):
        return {"url": response.url, "source": source, "status": response.status_code,
                "content_type": content_type, "captured": False, "reason": "anti-bot/interstitial response; not stored"}
    page_hash = hashlib.sha256(response.content).hexdigest()
    safe_source = source.lower().replace(" ", "_")
    path = Path(output_dir) / safe_source / f"{page_hash[:16]}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return {"url": response.url, "source": source, "status": response.status_code,
            "content_type": content_type, "title": title, "headings": headings,
            "sha256": page_hash, "bytes": len(response.content),
            "last_modified": response.headers.get("Last-Modified"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "raw_html_path": str(path), "captured": True}

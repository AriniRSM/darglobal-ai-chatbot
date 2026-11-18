"""Extract text and conservative structured fields from captured HTML."""
from __future__ import annotations
import json
import re
from bs4 import BeautifulSoup

def _jsonld_values(soup):
    values = []
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            parsed = json.loads(node.string or node.get_text())
            values.extend(parsed if isinstance(parsed, list) else [parsed])
        except (ValueError, TypeError):
            continue
    return values

def _first(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return None

def extract_document(html: bytes, source: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    structured = _jsonld_values(soup)
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    headings = [h.get_text(" ", strip=True) for h in soup.select("h1,h2,h3")]
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = description_tag.get("content", "").strip() if description_tag else None
    for element in soup.select("script,style,noscript,svg,nav,footer,header,form"):
        element.decompose()
    main = soup.select_one("main") or soup.select_one("article") or soup.body or soup
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
    if len(text) < 80:
        raise ValueError("Page has too little readable text to index")
    # Only trust explicit structured-data keys; missing or unparseable fields stay null.
    data = {}
    for item in structured:
        if isinstance(item, dict):
            if isinstance(item.get("@graph"), list):
                data.update(next((x for x in item["@graph"] if isinstance(x, dict)), {}))
            data.update(item)
    address = data.get("address") if isinstance(data.get("address"), dict) else {}
    offers = data.get("offers") if isinstance(data.get("offers"), dict) else {}
    amenity_features = data.get("amenityFeature") or data.get("amenities")
    if isinstance(amenity_features, list):
        amenities = [x.get("name") for x in amenity_features if isinstance(x, dict) and x.get("name")]
    else:
        amenities = []
    location = _first(address, "addressLocality", "addressRegion", "streetAddress")
    if not location and isinstance(address, str):
        location = address
    return {
        "project_name": _first(data, "name") or title,
        "developer": source if source == "DarGlobal" else None,
        "location": location,
        "country": _first(address, "addressCountry"),
        "property_type": _first(data, "@type", "category", "propertyType"),
        "bedrooms": _first(data, "numberOfBedrooms", "numberOfRooms"),
        "price": _first(offers, "price") if offers else None,
        "currency": _first(offers, "priceCurrency") if offers else None,
        "amenities": amenities,
        "project_description": description or None,
        "headings": headings,
        "text": text,
        "json_ld": structured,
        "source_url": source_url,
        "source": source,
    }

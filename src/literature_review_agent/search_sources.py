from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


USER_AGENT = "literature-review-agent/0.1"


class SearchError(RuntimeError):
    """Raised when a search source cannot be queried cleanly."""


@dataclass
class SearchResult:
    papers: list[dict[str, Any]]
    notes: list[str]


def search_source(source: dict[str, Any], query: str, limit: int = 5) -> SearchResult:
    source_id = source.get("source_id", "")
    if source_id == "DOAJ":
        return _search_doaj(query=query, limit=limit)
    if source_id == "CORE":
        return _search_core(query=query, limit=limit)
    return SearchResult(
        papers=[],
        notes=[f"{source_id or 'UNKNOWN_SOURCE'} is approved but does not have an automated search adapter yet."],
    )


def _search_doaj(query: str, limit: int) -> SearchResult:
    url = f"https://doaj.org/api/search/articles/{quote_plus(query)}?pageSize={limit}"
    payload = _fetch_json(url)
    results = payload.get("results", [])
    papers = []
    for index, item in enumerate(results, start=1):
        bibjson = item.get("bibjson", {})
        identifiers = bibjson.get("identifier", [])
        doi = ""
        for identifier in identifiers:
            if identifier.get("type") == "doi":
                doi = identifier.get("id", "")
                break
        links = bibjson.get("link", [])
        url_value = links[0].get("url", "") if links else ""
        year = _safe_int(bibjson.get("year"))
        abstract = bibjson.get("abstract", "")
        papers.append(
            {
                "paper_id": f"DOAJ-{index:03d}",
                "title": bibjson.get("title", ""),
                "year": year,
                "journal": (bibjson.get("journal") or {}).get("title", ""),
                "doi": doi,
                "source": "DOAJ",
                "url": url_value,
                "abstract": abstract,
                "route_ids": [],
                "status": "candidate",
                "triage_decision": "",
                "triage_reason": "",
                "experimental_signal": "unknown",
                "pilot_signal": "",
                "industrial_compatibility_signal": "",
                "notes": "",
            }
        )
    return SearchResult(papers=papers, notes=[f"DOAJ returned {len(papers)} paper(s)."])


def _search_core(query: str, limit: int) -> SearchResult:
    url = f"https://core.ac.uk:443/api-v2/search/{quote_plus(query)}?page=1&pageSize={limit}"
    payload = _fetch_json(url)
    results = payload.get("data", []) or payload.get("results", [])
    papers = []
    for index, item in enumerate(results, start=1):
        paper_url = item.get("downloadUrl") or item.get("fullTextLink") or item.get("sourceFulltextUrls", [""])
        if isinstance(paper_url, list):
            paper_url = paper_url[0] if paper_url else ""
        papers.append(
            {
                "paper_id": f"CORE-{index:03d}",
                "title": item.get("title", ""),
                "year": _safe_int(item.get("yearPublished")),
                "journal": item.get("publisher", ""),
                "doi": item.get("doi", ""),
                "source": "CORE",
                "url": paper_url or item.get("urls", [""])[0] if item.get("urls") else "",
                "abstract": item.get("description", "") or item.get("abstract", ""),
                "route_ids": [],
                "status": "candidate",
                "triage_decision": "",
                "triage_reason": "",
                "experimental_signal": "unknown",
                "pilot_signal": "",
                "industrial_compatibility_signal": "",
                "notes": "",
            }
        )
    return SearchResult(papers=papers, notes=[f"CORE returned {len(papers)} paper(s)."])


def _fetch_json(url: str) -> dict[str, Any]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except (HTTPError, URLError) as exc:
        raise SearchError(f"Could not fetch {url}: {exc}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SearchError(f"Could not parse JSON from {url}") from exc


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

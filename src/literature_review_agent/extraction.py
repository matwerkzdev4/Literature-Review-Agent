from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = "literature-review-agent/0.1"


class ExtractionError(RuntimeError):
    """Raised when a paper page cannot be fetched or parsed."""


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self._in_title = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content") or ""
            if name in {"description", "og:description", "dc.description"} and not self.meta_description:
                self.meta_description = content.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
            return
        self._chunks.append(cleaned)

    @property
    def body_text(self) -> str:
        return " ".join(self._chunks)


def fetch_document_metadata(url: str) -> dict[str, Any]:
    if not url:
        raise ExtractionError("No URL was provided for extraction.")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read()
    except (HTTPError, URLError) as exc:
        raise ExtractionError(f"Could not fetch document: {exc}") from exc

    if "html" not in content_type.lower():
        return {
            "fetch_status": "non_html",
            "page_title": "",
            "summary_text": "",
            "body_text": "",
        }

    text = raw.decode("utf-8", errors="ignore")
    parser = _HTMLTextExtractor()
    parser.feed(text)
    return {
        "fetch_status": "ok",
        "page_title": parser.title,
        "summary_text": parser.meta_description,
        "body_text": parser.body_text,
    }


def build_extraction_from_text(paper: dict[str, Any], fetched: dict[str, Any] | None = None) -> dict[str, Any]:
    fetched = fetched or {}
    abstract = paper.get("abstract", "") or ""
    text_parts = [
        paper.get("title", "") or "",
        abstract,
        fetched.get("summary_text", "") or "",
        fetched.get("body_text", "") or "",
    ]
    text = " ".join(part for part in text_parts if part).strip()
    process_steps = infer_process_steps(text)
    key_parameters = infer_key_parameters(text)
    reported_scale = infer_scale(text)
    pilot_evidence = infer_pilot_signal(text) or paper.get("pilot_signal", "")
    industrial_evidence = infer_industrial_signal(text) or paper.get("industrial_compatibility_signal", "")
    performance_outcomes = infer_performance_outcomes(text)
    limitations = infer_limitations(text)
    failure_points = infer_failure_points(text)
    missing_details = infer_missing_details(process_steps, key_parameters, reported_scale, text)
    evidence_flags = infer_evidence_flags(text, process_steps, key_parameters, reported_scale)
    summary_snippets = infer_summary_snippets(text)

    return {
        "material_details": summarize_material_details(text),
        "process_steps": process_steps,
        "key_parameters": key_parameters,
        "reported_scale": reported_scale,
        "pilot_evidence": pilot_evidence,
        "industrial_compatibility_evidence": industrial_evidence,
        "performance_outcomes": performance_outcomes,
        "limitations": limitations,
        "failure_points": failure_points,
        "missing_details": missing_details,
        "evidence_flags": evidence_flags,
        "summary_snippets": summary_snippets,
        "page_fetch_status": fetched.get("fetch_status", "not_attempted"),
        "page_title": fetched.get("page_title", ""),
        "page_summary": fetched.get("summary_text", ""),
    }


def infer_process_steps(text: str) -> list[str]:
    patterns = [
        ("mix", ["mix", "mixed", "mixing"]),
        ("mill", ["mill", "milling", "ball-mill", "ball mill"]),
        ("cast", ["tape cast", "tape-cast", "casting", "cast"]),
        ("spray", ["spray", "sprayed", "spraying"]),
        ("dry", ["dry", "dried", "drying"]),
        ("press", ["press", "pressed", "hot press", "hot-press"]),
        ("sinter", ["sinter", "sintered", "sintering"]),
        ("coat", ["coat", "coated", "coating"]),
        ("disperse", ["disperse", "dispersion", "sonicate", "sonication"]),
    ]
    lowered = text.lower()
    found = []
    for label, terms in patterns:
        if any(term in lowered for term in terms):
            found.append(label)
    return found


def infer_key_parameters(text: str) -> list[dict[str, str]]:
    matches = []
    patterns = [
        (r"(\d+(?:\.\d+)?)\s?(?:wt%|weight percent)", "composition", "wt%"),
        (r"(\d+(?:\.\d+)?)\s?(?:rpm)", "speed", "rpm"),
        (r"(\d+(?:\.\d+)?)\s?(?:h|hr|hrs|hour|hours)", "time", "h"),
        (r"(\d+(?:\.\d+)?)\s?(?:c|°c)", "temperature", "C"),
        (r"(\d+(?:\.\d+)?)\s?(?:mm|um|micron|microns)", "thickness_or_size", "mm_or_um"),
    ]
    lowered = text.lower()
    for pattern, name, units in patterns:
        for value in re.findall(pattern, lowered):
            matches.append({"name": name, "value": value, "units": units})
            if len(matches) >= 8:
                return matches
    parameter_pairs = [
        (r"(\d+(?:\.\d+)?)\s?(?:mpa)", "pressure", "MPa"),
        (r"(\d+(?:\.\d+)?)\s?(?:min|minutes)", "time", "min"),
    ]
    for pattern, name, units in parameter_pairs:
        for value in re.findall(pattern, lowered):
            matches.append({"name": name, "value": value, "units": units})
            if len(matches) >= 8:
                return matches
    return matches


def infer_scale(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["pilot-scale", "pilot scale", "demonstrator", "pilot plant"]):
        return "pilot"
    if any(term in lowered for term in ["industrial", "production line", "manufacturing line", "commercial"]):
        return "industrial"
    if any(term in lowered for term in ["bench-scale", "laboratory", "lab-scale", "lab scale"]):
        return "lab"
    return ""


def infer_pilot_signal(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["pilot-scale", "pilot scale", "demonstrator", "scaled-up"]):
        return "pilot_or_scale_signal_present"
    return ""


def infer_industrial_signal(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["industrial", "production", "manufacturing", "standard equipment", "roll-to-roll"]):
        return "industrial_compatibility_signal_present"
    return ""


def infer_performance_outcomes(text: str) -> list[str]:
    outcomes = []
    lowered = text.lower()
    phrases = [
        "improved strength",
        "high density",
        "uniform coating",
        "reduced defects",
        "improved adhesion",
        "enhanced conductivity",
        "high solids loading",
        "good dispersion",
        "stable slurry",
    ]
    for phrase in phrases:
        if phrase in lowered:
            outcomes.append(phrase)
    return outcomes


def infer_limitations(text: str) -> list[str]:
    limitations = []
    lowered = text.lower()
    phrases = ["limited", "challenge", "constraint", "sensitive", "narrow window", "difficult", "poorly understood"]
    for phrase in phrases:
        if phrase in lowered:
            limitations.append(f"Text mentions {phrase}.")
    return limitations[:5]


def infer_failure_points(text: str) -> list[str]:
    failures = []
    lowered = text.lower()
    phrases = ["crack", "agglomeration", "poor adhesion", "defect", "delamination", "instability"]
    for phrase in phrases:
        if phrase in lowered:
            failures.append(f"Text mentions {phrase}.")
    return failures[:5]


def infer_evidence_flags(
    text: str,
    process_steps: list[str],
    key_parameters: list[dict[str, str]],
    reported_scale: str,
) -> dict[str, bool]:
    lowered = text.lower()
    return {
        "has_clear_process_steps": bool(process_steps),
        "has_multiple_process_steps": len(process_steps) >= 2,
        "has_key_parameters": bool(key_parameters),
        "has_scale_signal": bool(reported_scale),
        "has_pilot_signal": bool(infer_pilot_signal(text)),
        "has_industrial_signal": bool(infer_industrial_signal(text)),
        "has_failure_or_limitations": any(term in lowered for term in ["limit", "challenge", "defect", "crack", "delamination"]),
        "has_performance_outcomes": bool(infer_performance_outcomes(text)),
    }


def infer_summary_snippets(text: str) -> list[str]:
    snippets = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    keywords = ["pilot", "industrial", "production", "mix", "mill", "cast", "spray", "dry", "press", "sinter"]
    for sentence in sentences:
        cleaned = " ".join(sentence.split())
        lowered = cleaned.lower()
        if len(cleaned) < 20:
            continue
        if any(keyword in lowered for keyword in keywords):
            snippets.append(cleaned[:220])
        if len(snippets) >= 4:
            break
    return snippets


def infer_missing_details(process_steps: list[str], key_parameters: list[dict[str, str]], reported_scale: str, text: str) -> list[str]:
    missing = []
    if not process_steps:
        missing.append("Process steps were not clearly identified.")
    if not key_parameters:
        missing.append("Key operating parameters were not clearly identified.")
    if not reported_scale:
        missing.append("Reported scale was not clearly identified.")
    if len(text.split()) < 40:
        missing.append("Very little extractable text was available.")
    return missing


def summarize_material_details(text: str) -> str:
    lowered = text.lower()
    clues = []
    materials = [
        "ceramic",
        "slurry",
        "binder",
        "powder",
        "coating",
        "composite",
        "electrode",
        "suspension",
    ]
    for item in materials:
        if item in lowered:
            clues.append(item)
    if clues:
        return "Detected material clues: " + ", ".join(clues[:6]) + "."
    return ""

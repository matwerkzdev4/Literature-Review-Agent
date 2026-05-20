from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .extraction import ExtractionError, build_extraction_from_text, fetch_document_metadata
from .presentation import render_recommendations, render_route_comparison, render_search_results, render_shortlist
from .project import Project
from .search_sources import SearchError, search_source
from .yaml_store import load_yaml, save_yaml


WORKFLOW_ORDER = [
    "intake_agent",
    "translation_agent",
    "search_agent",
    "triage_agent",
    "ranking_agent",
    "full_text_extraction_agent",
    "route_comparison_agent",
    "lab_analogue_agent",
    "recommendation_agent",
    "compliance_agent",
]


@dataclass
class AgentResult:
    notes: list[str]
    pause: bool = False
    stop_early: bool = False
    stop_reason: str = ""


class BaseAgent:
    name: str

    def run(self, project: Project) -> AgentResult:
        raise NotImplementedError


class IntakeAgent(BaseAgent):
    name = "intake_agent"

    def run(self, project: Project) -> AgentResult:
        intake = project.load_state("intake.yml", default={})
        assumptions = list(intake.get("assumptions", []))
        defaults = {
            "intended_use": "Experiment planning for a mixed technical team.",
            "desired_outcome": "Identify the most defensible next experimental path.",
            "review_purpose": "Compare process-sequence routes using public evidence.",
        }
        for key, assumption_text in defaults.items():
            if not intake.get(key):
                intake[key] = assumption_text
                assumptions.append(f"Assumed {key.replace('_', ' ')} because it was not provided.")
        intake["assumptions"] = _dedupe(assumptions)
        project.save_state("intake.yml", intake)
        return AgentResult(notes=["Intake normalized and assumptions recorded."])


class TranslationAgent(BaseAgent):
    name = "translation_agent"

    def run(self, project: Project) -> AgentResult:
        intake = project.load_state("intake.yml", default={})
        scope = project.load_state("technical_scope.yml", default={})
        approved_sources = project.load_config("approved_sources.yml", default={}).get("approved_sources", [])
        question = intake.get("question", "")
        scope["question"] = question
        scope["decision_goal"] = intake.get("desired_outcome", "")
        scope["intended_use"] = intake.get("intended_use", "")
        scope["desired_outcome"] = intake.get("desired_outcome", "")
        scope["constraints"] = intake.get("constraints", [])
        scope["assumptions"] = intake.get("assumptions", [])
        scope.setdefault("material_system", "")
        scope.setdefault("application_domain", "")
        scope.setdefault("scale_relevance", "pilot_or_industrial_relevance")
        route_definitions = scope.get("route_definitions") or []
        if not route_definitions:
            route_steps = _guess_route_steps(question)
            route_definitions = [
                {
                    "route_id": "ROUTE-001",
                    "route_name": _route_name_from_steps(route_steps),
                    "process_sequence": route_steps or ["to_be_defined"],
                    "short_description": "Initial route inferred from the question until a more specific route list is added.",
                }
            ]
        scope["route_definitions"] = route_definitions
        tokens = _tokenize(question)
        route_terms = []
        for route in route_definitions:
            route_terms.extend(route.get("process_sequence", []))
        scope["search_terms"] = {
            "core_keywords": tokens[:8],
            "synonyms": _dedupe(route_terms),
            "excluded_terms": [],
            "query_variants": _build_query_variants(question, tokens[:8], route_terms),
        }
        scope["approved_sources"] = [item["source_id"] for item in approved_sources]
        project.save_state("technical_scope.yml", scope)
        return AgentResult(notes=["Technical scope generated from intake."])


class SearchAgent(BaseAgent):
    name = "search_agent"

    def run(self, project: Project) -> AgentResult:
        scope = project.load_state("technical_scope.yml", default={})
        papers_doc = project.load_state("papers.yml", default={"papers": []})
        existing_papers = papers_doc.get("papers", [])
        query_variants = scope.get("search_terms", {}).get("query_variants") or [_build_search_query(scope)]
        notes: list[str] = []
        discovered: list[dict[str, Any]] = []
        approved_sources = project.load_config("approved_sources.yml", default={}).get("approved_sources", [])
        for source in approved_sources:
            for query in query_variants[:3]:
                try:
                    result = search_source(source, query=query, limit=5)
                except SearchError as exc:
                    notes.append(str(exc))
                    break
                notes.extend(result.notes)
                discovered.extend(result.papers)
        papers = discovered + existing_papers
        normalized = []
        route_ids = [route.get("route_id", "") for route in scope.get("route_definitions", []) if route.get("route_id")]
        for index, paper in enumerate(papers, start=1):
            paper_route_ids = paper.get("route_ids") or route_ids or ["ROUTE-001"]
            normalized.append(
                {
                    "paper_id": paper.get("paper_id") or f"PAPER-{index:03d}",
                    "title": paper.get("title", ""),
                    "year": paper.get("year"),
                    "journal": paper.get("journal", ""),
                    "doi": paper.get("doi", ""),
                    "source": paper.get("source", ""),
                    "url": paper.get("url", ""),
                    "abstract": paper.get("abstract", ""),
                    "route_ids": paper_route_ids,
                    "status": paper.get("status", "candidate"),
                    "triage_decision": paper.get("triage_decision", ""),
                    "triage_reason": paper.get("triage_reason", ""),
                    "experimental_signal": paper.get("experimental_signal", _infer_experimental_signal(paper)),
                    "pilot_signal": paper.get("pilot_signal", _infer_pilot_signal(paper)),
                    "industrial_compatibility_signal": paper.get("industrial_compatibility_signal", _infer_industrial_signal(paper)),
                    "notes": paper.get("notes", ""),
                }
            )
        papers_doc["query"] = query_variants[0] if query_variants else ""
        papers_doc["query_variants"] = query_variants
        papers_doc["search_notes"] = notes
        papers_doc["papers"] = _dedupe_papers(normalized)
        project.save_state("papers.yml", papers_doc)
        _write_output_file(project, "search_results.txt", render_search_results(papers_doc))
        if normalized:
            notes.append(f"Candidate papers collected: {len(papers_doc['papers'])}.")
        else:
            notes.append("No candidate papers found; workflow may stop early.")
        return AgentResult(notes=notes)


class TriageAgent(BaseAgent):
    name = "triage_agent"

    def run(self, project: Project) -> AgentResult:
        papers_doc = project.load_state("papers.yml", default={"papers": []})
        retained = 0
        for paper in papers_doc.get("papers", []):
            title_text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
            if any(flag in title_text for flag in ["simulation", "theoretical", "review article", "purely computational"]):
                paper["status"] = "rejected"
                paper["triage_decision"] = "reject"
                paper["triage_reason"] = "Rejected at abstract level as non-experimental or weakly actionable."
            elif paper.get("abstract") or paper.get("title"):
                paper["status"] = "retained"
                paper["triage_decision"] = "retain"
                paper["triage_reason"] = "Retained for route-level review."
                retained += 1
            else:
                paper["status"] = "rejected"
                paper["triage_decision"] = "reject"
                paper["triage_reason"] = "Rejected because no usable title or abstract was available."
        project.save_state("papers.yml", papers_doc)
        if retained == 0:
            return AgentResult(
                notes=["No papers survived triage."],
                stop_early=True,
                stop_reason="evidence_too_weak_for_experiment_planning",
            )
        return AgentResult(notes=[f"{retained} paper(s) survived triage."])


class RankingAgent(BaseAgent):
    name = "ranking_agent"

    def run(self, project: Project) -> AgentResult:
        papers_doc = project.load_state("papers.yml", default={"papers": []})
        scope = project.load_state("technical_scope.yml", default={})
        retained = [paper for paper in papers_doc.get("papers", []) if paper.get("status") == "retained"]
        ranked_papers = sorted(retained, key=_paper_rank_score, reverse=True)
        route_scores: dict[str, dict[str, Any]] = {}
        for rank, paper in enumerate(ranked_papers, start=1):
            paper["status"] = "shortlisted"
            route_ids = paper.get("route_ids") or ["ROUTE-001"]
            for route_id in route_ids:
                entry = route_scores.setdefault(
                    route_id,
                    {
                        "route_id": route_id,
                        "route_name": _route_name(scope.get("route_definitions", []), route_id),
                        "score": 0,
                        "supporting_paper_ids": [],
                    },
                )
                entry["score"] += _paper_rank_score(paper)
                entry["supporting_paper_ids"].append(paper["paper_id"])
        shortlist = {
            "shortlist_status": "pending_user_approval",
            "ranked_routes": [
                {
                    "route_id": route["route_id"],
                    "route_name": route["route_name"],
                    "rank": index,
                    "shortlist_reason": "Ranked by retained evidence volume and signal strength.",
                    "supporting_paper_ids": route["supporting_paper_ids"],
                }
                for index, route in enumerate(
                    sorted(route_scores.values(), key=lambda item: item["score"], reverse=True),
                    start=1,
                )
            ],
            "ranked_papers": [
                {
                    "paper_id": paper["paper_id"],
                    "title": paper.get("title", ""),
                    "route_ids": paper.get("route_ids") or ["ROUTE-001"],
                    "paper_rank": rank,
                    "shortlist_reason": "Retained after abstract triage and ranked for deeper review.",
                    "approval_status": "pending",
                }
                for rank, paper in enumerate(ranked_papers, start=1)
            ],
            "user_actions": {
                "approved_paper_ids": [],
                "removed_paper_ids": [],
                "reprioritized_paper_ids": [],
            },
            "notes": "",
        }
        project.save_state("shortlist.yml", shortlist)
        _write_output_file(project, "shortlist_review.txt", render_shortlist(shortlist))
        if not ranked_papers:
            return AgentResult(
                notes=["Shortlist is empty."],
                stop_early=True,
                stop_reason="evidence_too_weak_for_experiment_planning",
            )
        return AgentResult(notes=["Shortlist prepared and awaiting approval."], pause=True)


class FullTextExtractionAgent(BaseAgent):
    name = "full_text_extraction_agent"

    def run(self, project: Project) -> AgentResult:
        shortlist = project.load_state("shortlist.yml", default={})
        papers_doc = project.load_state("papers.yml", default={"papers": []})
        paper_index = {paper["paper_id"]: paper for paper in papers_doc.get("papers", []) if paper.get("paper_id")}
        approved_ids = shortlist.get("user_actions", {}).get("approved_paper_ids", [])
        if not approved_ids:
            approved_ids = [paper["paper_id"] for paper in shortlist.get("ranked_papers", []) if paper.get("approval_status") == "approved"]
        if not approved_ids:
            return AgentResult(
                notes=["No approved papers were available for full-text extraction."],
                stop_early=True,
                stop_reason="evidence_too_weak_for_experiment_planning",
            )
        created = 0
        for paper_id in approved_ids:
            paper = paper_index.get(paper_id, {})
            detail_path = project.paths.paper_details_dir / f"{paper_id}.yml"
            existing_detail = load_yaml(detail_path, default={}) if detail_path.exists() else {}
            fetched = {}
            if paper.get("url"):
                try:
                    fetched = fetch_document_metadata(paper.get("url", ""))
                except ExtractionError as exc:
                    fetched = {
                        "fetch_status": "failed",
                        "page_title": "",
                        "summary_text": "",
                        "body_text": "",
                        "fetch_error": str(exc),
                    }
            extracted = build_extraction_from_text(paper, fetched)
            detail = {
                "paper_id": paper_id,
                "title": paper.get("title", ""),
                "doi": paper.get("doi", ""),
                "route_ids": paper.get("route_ids") or ["ROUTE-001"],
                "url": paper.get("url", ""),
                "material_details": extracted["material_details"],
                "process_steps": extracted["process_steps"],
                "key_parameters": extracted["key_parameters"],
                "reported_scale": extracted["reported_scale"],
                "pilot_evidence": extracted["pilot_evidence"],
                "industrial_compatibility_evidence": extracted["industrial_compatibility_evidence"],
                "performance_outcomes": extracted["performance_outcomes"],
                "limitations": extracted["limitations"],
                "failure_points": extracted["failure_points"],
                "missing_details": extracted["missing_details"],
                "evidence_flags": extracted["evidence_flags"],
                "summary_snippets": extracted["summary_snippets"],
                "page_fetch_status": extracted["page_fetch_status"],
                "page_title": extracted["page_title"],
                "page_summary": extracted["page_summary"],
                "notes": existing_detail.get("notes", ""),
            }
            if fetched.get("fetch_error"):
                detail["notes"] = _append_note(detail["notes"], fetched["fetch_error"])
            save_yaml(detail_path, detail)
            created += 1
        return AgentResult(notes=[f"Prepared or refreshed {created} paper detail file(s)."])


class RouteComparisonAgent(BaseAgent):
    name = "route_comparison_agent"

    def run(self, project: Project) -> AgentResult:
        route_map: dict[str, dict[str, Any]] = {}
        detail_files = sorted(project.paths.paper_details_dir.glob("PAPER-*.yml"))
        if not detail_files:
            return AgentResult(
                notes=["No paper detail files were available for route comparison."],
                stop_early=True,
                stop_reason="evidence_too_weak_for_experiment_planning",
            )
        scope = project.load_state("technical_scope.yml", default={})
        for path in detail_files:
            detail = load_yaml(path, default={})
            for route_id in detail.get("route_ids", []) or ["ROUTE-001"]:
                route = route_map.setdefault(
                    route_id,
                    {
                        "route_id": route_id,
                        "route_name": _route_name(scope.get("route_definitions", []), route_id),
                        "process_sequence": _route_steps(scope.get("route_definitions", []), route_id),
                        "supporting_paper_ids": [],
                        "evidence_summary": "",
                        "evidence_strength": "moderate",
                        "evidence_score": 0,
                        "evidence_score_breakdown": {},
                        "pilot_relevance": "limited",
                        "industrial_compatibility": "unclear",
                        "main_advantages": [],
                        "main_limitations": [],
                        "major_uncertainties": [],
                        "comparison_notes": "",
                    },
                )
                route["supporting_paper_ids"].append(detail.get("paper_id", ""))
                paper_score = _paper_evidence_score(detail)
                route["evidence_score"] += paper_score["total"]
                if detail.get("pilot_evidence"):
                    route["pilot_relevance"] = "supported"
                if detail.get("industrial_compatibility_evidence"):
                    route["industrial_compatibility"] = "supported"
                route["main_advantages"].extend(_extract_advantages(detail))
                route["main_limitations"].extend(detail.get("limitations", []))
                if detail.get("missing_details"):
                    route["major_uncertainties"].extend(detail.get("missing_details", []))
                route["comparison_notes"] = _append_note(
                    route["comparison_notes"],
                    f"{detail.get('paper_id', '')}: evidence score {paper_score['total']}/10.",
                )
        for route in route_map.values():
            paper_count = len(route["supporting_paper_ids"])
            average_score = route["evidence_score"] / paper_count if paper_count else 0
            route["evidence_strength"] = _evidence_label(average_score, paper_count)
            route["evidence_score_breakdown"] = {
                "paper_count": paper_count,
                "average_paper_score": round(average_score, 2),
            }
            route["evidence_summary"] = (
                f"Supported by {paper_count} approved paper(s), with an average evidence score of {round(average_score, 1)}/10."
            )
            route["main_advantages"] = _dedupe(route["main_advantages"])
            route["main_limitations"] = _dedupe(route["main_limitations"])
            route["major_uncertainties"] = _dedupe(route["major_uncertainties"])
        route_comparison_doc = {"routes": list(route_map.values())}
        project.save_state("route_comparison.yml", route_comparison_doc)
        _write_output_file(project, "route_comparison.txt", render_route_comparison(route_comparison_doc))
        return AgentResult(notes=["Route comparison completed."])


class LabAnalogueAgent(BaseAgent):
    name = "lab_analogue_agent"

    def run(self, project: Project) -> AgentResult:
        comparison = project.load_state("route_comparison.yml", default={"routes": []})
        equipment = project.load_config("equipment.yml", default={}).get("equipment", {})
        available_equipment = [item for items in equipment.values() for item in items]
        routes = []
        for route in comparison.get("routes", []):
            feasibility = "conditional"
            major_gaps = list(route.get("major_uncertainties", []))
            matching_equipment = _match_equipment_to_route(route.get("process_sequence", []), available_equipment)
            if route.get("evidence_strength") == "weak":
                feasibility = "not_recommended"
                major_gaps.append("Evidence is too weak to support a meaningful analogue.")
            elif not matching_equipment:
                feasibility = "not_recommended"
                major_gaps.append("No strong equipment match was found for the route steps.")
            elif route.get("evidence_strength") == "strong":
                feasibility = "workable"
            routes.append(
                {
                    "route_id": route["route_id"],
                    "route_name": route["route_name"],
                    "analogue_goal": "Build a directional lab analogue for the process sequence.",
                    "matching_equipment": matching_equipment or available_equipment[:3],
                    "needed_adaptations": _needed_adaptations(route.get("process_sequence", []), matching_equipment),
                    "major_gaps": _dedupe(major_gaps),
                    "feasibility_result": feasibility,
                }
            )
        if not routes:
            return AgentResult(
                notes=["No routes were available for analogue assessment."],
                stop_early=True,
                stop_reason="no_valid_path_with_current_equipment",
            )
        if all(route["feasibility_result"] == "not_recommended" for route in routes):
            stop_reason = "no_valid_path_with_current_equipment"
            stop_early = True
        else:
            stop_reason = ""
            stop_early = False
        project.save_state("lab_analogue.yml", {"routes": routes})
        return AgentResult(notes=["Lab analogue assessment completed."], stop_early=stop_early, stop_reason=stop_reason)


class RecommendationAgent(BaseAgent):
    name = "recommendation_agent"

    def run(self, project: Project) -> AgentResult:
        comparison = project.load_state("route_comparison.yml", default={"routes": []})
        analogue = project.load_state("lab_analogue.yml", default={"routes": []})
        analogue_by_id = {route["route_id"]: route for route in analogue.get("routes", [])}
        ranked = sorted(comparison.get("routes", []), key=_route_rank_score, reverse=True)
        recommendations = []
        for index, route in enumerate(ranked, start=1):
            analogue_route = analogue_by_id.get(route["route_id"], {})
            label = _recommendation_label(route, analogue_route)
            recommendations.append(
                {
                    "route_id": route["route_id"],
                    "route_name": route["route_name"],
                    "rank": index,
                    "label": label,
                    "recommendation_reason": _recommendation_reason(route, analogue_route, label),
                    "strongest_support": route.get("evidence_summary", ""),
                    "suggested_next_experiment": "Define and run the smallest meaningful directional analogue for this process sequence.",
                    "required_equipment": analogue_route.get("matching_equipment", []),
                    "key_risks": analogue_route.get("major_gaps", []),
                    "evidence_references": route.get("supporting_paper_ids", []),
                }
            )
        overall = recommendations[0]["label"] if recommendations else "not recommended"
        summary = recommendations[0]["recommendation_reason"] if recommendations else "No route could be recommended."
        project.save_state(
            "recommendations.yml",
            {
                "recommendations": recommendations,
                "final_summary": summary,
                "overall_decision": overall,
            },
        )
        _write_output_file(
            project,
            "recommendations.txt",
            render_recommendations(
                {
                    "recommendations": recommendations,
                    "final_summary": summary,
                    "overall_decision": overall,
                }
            ),
        )
        return AgentResult(notes=["Recommendations generated."])


class ComplianceAgent(BaseAgent):
    name = "compliance_agent"

    def run(self, project: Project) -> AgentResult:
        recommendations = project.load_state("recommendations.yml", default={})
        final_brief_path = project.paths.outputs_dir / "final_brief.md"
        final_brief_path.parent.mkdir(parents=True, exist_ok=True)
        content = _render_final_brief(project, recommendations)
        final_brief_path.write_text(content, encoding="utf-8")
        checks = _run_compliance_checks(content, recommendations)
        workflow_state = project.load_workflow_state()
        workflow_state["compliance"] = checks
        project.save_workflow_state(workflow_state)
        if not checks["passed"]:
            return AgentResult(
                notes=["Compliance checks failed.", *checks["issues"]],
                stop_early=True,
                stop_reason="final_output_failed_compliance_checks",
            )
        return AgentResult(notes=["Final brief rendered and compliance checks completed."])


AGENT_REGISTRY: dict[str, BaseAgent] = {
    agent.name: agent
    for agent in [
        IntakeAgent(),
        TranslationAgent(),
        SearchAgent(),
        TriageAgent(),
        RankingAgent(),
        FullTextExtractionAgent(),
        RouteComparisonAgent(),
        LabAnalogueAgent(),
        RecommendationAgent(),
        ComplianceAgent(),
    ]
}


def _paper_rank_score(paper: dict[str, Any]) -> int:
    score = 0
    if paper.get("pilot_signal"):
        score += 2
    if paper.get("industrial_compatibility_signal"):
        score += 2
    if paper.get("experimental_signal"):
        score += 1
    if paper.get("abstract"):
        score += 1
    return score


def _route_rank_score(route: dict[str, Any]) -> int:
    evidence_score = {"strong": 8, "moderate": 4, "weak": 1}.get(route.get("evidence_strength", ""), 0)
    pilot_score = {"supported": 3, "limited": 1, "none": 0}.get(route.get("pilot_relevance", ""), 0)
    industrial_score = {"supported": 2, "unclear": 1, "none": 0}.get(route.get("industrial_compatibility", ""), 0)
    raw = route.get("evidence_score", 0)
    return evidence_score + pilot_score + industrial_score + int(round(raw))


def _recommendation_label(route: dict[str, Any], analogue: dict[str, Any]) -> str:
    evidence = route.get("evidence_strength")
    feasibility = analogue.get("feasibility_result")
    if evidence == "strong" and feasibility in {"workable", "conditional"}:
        return "recommended"
    if evidence in {"strong", "moderate"} and feasibility != "not_recommended":
        return "conditional"
    return "not recommended"


def _recommendation_reason(route: dict[str, Any], analogue: dict[str, Any], label: str) -> str:
    evidence = route.get("evidence_strength", "unknown")
    feasibility = analogue.get("feasibility_result", "unknown")
    score = route.get("evidence_score_breakdown", {}).get("average_paper_score", "unknown")
    if label == "recommended":
        return f"This route has the strongest available evidence (average paper score {score}/10) and a workable analogue path."
    if label == "conditional":
        return f"This route is promising but still limited by {evidence} evidence strength or analogue constraints."
    return "This route is not recommended because the current evidence or analogue path is too weak."


def _route_name(route_definitions: list[dict[str, Any]], route_id: str) -> str:
    for route in route_definitions:
        if route.get("route_id") == route_id:
            return route.get("route_name", route_id)
    return route_id


def _route_steps(route_definitions: list[dict[str, Any]], route_id: str) -> list[str]:
    for route in route_definitions:
        if route.get("route_id") == route_id:
            return route.get("process_sequence", [])
    return []


def _tokenize(text: str) -> list[str]:
    tokens = []
    for raw in text.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum() or ch == "_")
        if len(token) >= 4 and token not in tokens:
            tokens.append(token)
    return tokens


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _render_final_brief(project: Project, recommendations_doc: dict[str, Any]) -> str:
    intake = project.load_state("intake.yml", default={})
    route_comparison = project.load_state("route_comparison.yml", default={"routes": []})
    lab_analogue = project.load_state("lab_analogue.yml", default={"routes": []})
    recommendations = recommendations_doc.get("recommendations", [])
    analogue_by_id = {item["route_id"]: item for item in lab_analogue.get("routes", [])}
    detail_by_route = _detail_snippets_by_route(project)
    lines = [
        "# Purpose",
        "",
        intake.get("question", "No question recorded."),
        "",
        "# Assumptions",
        "",
    ]
    assumptions = intake.get("assumptions", [])
    lines.extend(assumptions or ["No explicit assumptions recorded."])
    lines.extend(["", "# Ranked Routes", ""])
    if recommendations:
        for item in recommendations:
            lines.append(f"- {item['rank']}. {item['route_name']} ({item['label']}): {item['recommendation_reason']}")
    else:
        lines.append("- No routes could be ranked.")
    lines.extend(["", "# Evidence Summary", ""])
    for route in route_comparison.get("routes", []):
        lines.append(f"- {route['route_name']}: {route.get('evidence_summary', 'No evidence summary available.')}")
        for snippet in detail_by_route.get(route["route_id"], [])[:3]:
            lines.append(f"  Evidence note: {snippet}")
        if route.get("main_advantages"):
            lines.append(f"  Strengths: {'; '.join(route['main_advantages'])}")
        if route.get("main_limitations"):
            lines.append(f"  Limits: {'; '.join(route['main_limitations'])}")
    lines.extend(["", "# Lab Analogue Plan", ""])
    for route_id, analogue in analogue_by_id.items():
        lines.append(f"- {analogue['route_name']}: {analogue.get('analogue_goal', '')}")
        if analogue.get("matching_equipment"):
            lines.append(f"  Equipment: {', '.join(analogue['matching_equipment'])}")
        if analogue.get("needed_adaptations"):
            lines.append(f"  Adaptations: {'; '.join(analogue['needed_adaptations'])}")
    lines.extend(["", "# Recommended Next Experiment", ""])
    if recommendations:
        lines.append(recommendations[0].get("suggested_next_experiment", "No next experiment proposed."))
    else:
        lines.append("No experiment is recommended at this time.")
    lines.extend(["", "# Risks and Unknowns", ""])
    risks = []
    for item in recommendations:
        risks.extend(item.get("key_risks", []))
    lines.extend(_dedupe(risks) or ["No explicit risks recorded."])
    lines.append("")
    return "\n".join(lines)


def _run_compliance_checks(content: str, recommendations_doc: dict[str, Any]) -> dict[str, Any]:
    required_sections = [
        "# Purpose",
        "# Assumptions",
        "# Ranked Routes",
        "# Evidence Summary",
        "# Lab Analogue Plan",
        "# Recommended Next Experiment",
        "# Risks and Unknowns",
    ]
    issues = []
    for section in required_sections:
        if section not in content:
            issues.append(f"Missing required section: {section}")
    if not recommendations_doc.get("recommendations"):
        issues.append("No recommendations were generated.")
    labels = {item.get("label", "") for item in recommendations_doc.get("recommendations", [])}
    if any(label not in {"recommended", "conditional", "not recommended"} for label in labels):
        issues.append("One or more recommendation labels are invalid.")
    return {
        "passed": not issues,
        "issues": issues,
        "required_sections": required_sections,
    }


def _build_search_query(scope: dict[str, Any]) -> str:
    keywords = scope.get("search_terms", {}).get("core_keywords", [])
    if keywords:
        return " ".join(keywords[:5])
    return scope.get("question", "")


def _build_query_variants(question: str, keywords: list[str], route_terms: list[str]) -> list[str]:
    variants = []
    base = " ".join(keywords[:5]).strip() or question.strip()
    if base:
        variants.append(base)
    if keywords and route_terms:
        variants.append(" ".join(_dedupe(keywords[:3] + route_terms[:3])))
    if question and route_terms:
        variants.append(" ".join(_dedupe(question.lower().split()[:4] + route_terms[:2])))
    return _dedupe([variant.strip() for variant in variants if variant.strip()])


def _paper_evidence_score(detail: dict[str, Any]) -> dict[str, int]:
    flags = detail.get("evidence_flags", {})
    total = 0
    total += 2 if flags.get("has_clear_process_steps") else 0
    total += 2 if flags.get("has_key_parameters") else 0
    total += 2 if flags.get("has_scale_signal") else 0
    total += 2 if flags.get("has_industrial_signal") else 0
    total += 1 if flags.get("has_performance_outcomes") else 0
    total += 1 if flags.get("has_failure_or_limitations") else 0
    return {"total": total}


def _evidence_label(average_score: float, paper_count: int) -> str:
    if paper_count >= 2 and average_score >= 6:
        return "strong"
    if paper_count >= 1 and average_score >= 3:
        return "moderate"
    return "weak"


def _extract_advantages(detail: dict[str, Any]) -> list[str]:
    advantages = []
    for outcome in detail.get("performance_outcomes", []):
        advantages.append(f"Reported outcome: {outcome}.")
    if detail.get("pilot_evidence"):
        advantages.append("Pilot or scale signal was detected.")
    if detail.get("industrial_compatibility_evidence"):
        advantages.append("Industrial compatibility signal was detected.")
    return advantages


def _match_equipment_to_route(process_sequence: list[str], equipment_list: list[str]) -> list[str]:
    mapping = {
        "mix": ["Thinky mixer", "Paint shaker", "Waring commercial blender", "Warbush blender", "Centrifugal mixer with vacuum function"],
        "mill": ["XQM-20 ball mill"],
        "cast": ["Long tape casting coater (250 mm x 800 mm)"],
        "spray": ["Walk-in spray booth", "Graco Ultra cordless handheld airless sprayer"],
        "dry": ["BOYN forced air drying oven", "Hotplate stirrers"],
        "press": ["YHA6-100TS hot press machine"],
        "sinter": ["Heraeus laboratory muffle furnace", "Carbolite CWF-1100 furnace"],
        "disperse": ["Sonicator"],
        "coat": ["Walk-in spray booth", "Graco Ultra cordless handheld airless sprayer"],
    }
    matched = []
    for step in process_sequence:
        for equipment in mapping.get(step, []):
            if equipment in equipment_list and equipment not in matched:
                matched.append(equipment)
    return matched


def _needed_adaptations(process_sequence: list[str], matching_equipment: list[str]) -> list[str]:
    if not matching_equipment:
        return ["Define a simpler analogue route or identify missing equipment."]
    adaptations = ["Translate the process sequence into the closest available lab-scale steps."]
    if "sinter" in process_sequence and not any("furnace" in item.lower() for item in matching_equipment):
        adaptations.append("Thermal treatment will need a substitute furnace step.")
    if "spray" in process_sequence and not any("sprayer" in item.lower() or "spray booth" in item.lower() for item in matching_equipment):
        adaptations.append("Coating application will need a substitute deposition step.")
    return adaptations


def _guess_route_steps(question: str) -> list[str]:
    lowered = question.lower()
    step_terms = [
        ("mix", ["mix", "mixed", "mixing"]),
        ("mill", ["mill", "milled", "milling"]),
        ("cast", ["cast", "casting", "tape cast", "tape casting"]),
        ("spray", ["spray", "sprayed", "spraying"]),
        ("dry", ["dry", "dried", "drying"]),
        ("press", ["press", "pressed", "pressing"]),
        ("sinter", ["sinter", "sintered", "sintering"]),
        ("coat", ["coat", "coating", "coated"]),
    ]
    steps = []
    for label, terms in step_terms:
        if any(term in lowered for term in terms):
            steps.append(label)
    return steps


def _route_name_from_steps(steps: list[str]) -> str:
    if not steps:
        return "Primary route candidate"
    return " -> ".join(step.title() for step in steps) + " route"


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for paper in papers:
        key = ((paper.get("doi") or "").lower(), (paper.get("title") or "").strip().lower())
        if key == ("", ""):
            key = ((paper.get("source") or "").lower(), (paper.get("url") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def _infer_experimental_signal(paper: dict[str, Any]) -> str:
    lowered = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    if any(term in lowered for term in ["experimental", "experiment", "fabricated", "prepared", "measured"]):
        return "experimental_signal_present"
    return ""


def _infer_pilot_signal(paper: dict[str, Any]) -> str:
    lowered = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    if any(term in lowered for term in ["pilot", "scale-up", "scaled", "demonstrator"]):
        return "pilot_or_scale_signal_present"
    return ""


def _infer_industrial_signal(paper: dict[str, Any]) -> str:
    lowered = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    if any(term in lowered for term in ["industrial", "production", "manufacturing", "roll-to-roll", "commercial"]):
        return "industrial_compatibility_signal_present"
    return ""


def _append_note(existing: str, new_note: str) -> str:
    if not existing:
        return new_note
    return f"{existing}\n{new_note}"


def _write_output_file(project: Project, filename: str, content: str) -> None:
    project.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
    (project.paths.outputs_dir / filename).write_text(content + "\n", encoding="utf-8")


def _detail_snippets_by_route(project: Project) -> dict[str, list[str]]:
    by_route: dict[str, list[str]] = {}
    for path in sorted(project.paths.paper_details_dir.glob("PAPER-*.yml")):
        detail = load_yaml(path, default={})
        route_ids = detail.get("route_ids", []) or ["ROUTE-001"]
        snippets = detail.get("summary_snippets", [])
        for route_id in route_ids:
            by_route.setdefault(route_id, []).extend(snippets)
    for route_id, snippets in by_route.items():
        by_route[route_id] = _dedupe(snippets)
    return by_route

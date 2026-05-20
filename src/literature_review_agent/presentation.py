from __future__ import annotations


def explain_status(state: dict) -> str:
    workflow_status = state.get("workflow_status", "unknown")
    current_stage = state.get("current_stage", "unknown")
    approval = state.get("approval_gate", {}).get("status", "unknown")
    early_stop = state.get("early_stop", {})
    final_decision = state.get("final_decision", {})
    project_name = state.get("project_name", "")
    project_root = state.get("project_root", "")

    lines = [
        f"Project: {project_name}" if project_name else "Project: unknown",
        f"Project folder: {project_root}" if project_root else "Project folder: unknown",
        f"Workflow status: {workflow_status}",
        f"Current stage: {current_stage}",
    ]

    if workflow_status == "waiting_for_user":
        lines.append("The workflow is paused and needs your input before it can continue.")
        if approval == "pending_user_approval":
            lines.append("It is waiting for you to approve the shortlist.")
    elif workflow_status == "completed":
        lines.append("The workflow has finished.")
        if final_decision.get("overall_label"):
            lines.append(f"Overall result: {final_decision['overall_label']}")
    elif workflow_status == "stopped_early":
        lines.append("The workflow stopped early because the evidence was too weak or the route was not workable.")
        if early_stop.get("reason"):
            lines.append(f"Reason: {early_stop['reason']}")
    else:
        lines.append("The workflow is ready to keep going.")

    notes = state.get("notes")
    if notes:
        lines.append(f"Latest note: {notes}")

    return "\n".join(lines)


def render_search_results(papers_doc: dict) -> str:
    papers = papers_doc.get("papers", [])
    lines = ["Search results"]
    query = papers_doc.get("query")
    if query:
        lines.append(f"Query used: {query}")
    if papers_doc.get("query_variants"):
        lines.append(f"Query variants tried: {len(papers_doc['query_variants'])}")
    if not papers:
        lines.append("No papers are currently stored.")
        return "\n".join(lines)
    lines.append(f"Papers found: {len(papers)}")
    for paper in papers:
        status = paper.get("status", "candidate")
        title = paper.get("title", "Untitled paper")
        source = paper.get("source", "unknown source")
        lines.append(f"- {paper.get('paper_id', '')}: {title} [{source}] ({status})")
    search_notes = papers_doc.get("search_notes", [])
    if search_notes:
        lines.append("Search notes:")
        for note in search_notes:
            lines.append(f"- {note}")
    return "\n".join(lines)


def render_shortlist(shortlist: dict) -> str:
    lines = ["Shortlist review"]
    status = shortlist.get("shortlist_status", "unknown")
    lines.append(f"Shortlist status: {status}")
    ranked_routes = shortlist.get("ranked_routes", [])
    ranked_papers = shortlist.get("ranked_papers", [])
    if ranked_routes:
        lines.append("Routes:")
        for route in ranked_routes:
            lines.append(
                f"- Rank {route.get('rank', '?')}: {route.get('route_name', route.get('route_id', 'Unknown route'))}."
            )
            if route.get("shortlist_reason"):
                lines.append(f"  Why it is here: {route['shortlist_reason']}")
    if ranked_papers:
        lines.append("Papers:")
        for paper in ranked_papers:
            lines.append(
                f"- Rank {paper.get('paper_rank', '?')}: {paper.get('paper_id', '')} - {paper.get('title', 'Untitled paper')} "
                f"[approval: {paper.get('approval_status', 'pending')}]"
            )
            if paper.get("shortlist_reason"):
                lines.append(f"  Why it is here: {paper['shortlist_reason']}")
    if not ranked_routes and not ranked_papers:
        lines.append("No shortlist is available yet.")
    return "\n".join(lines)


def render_recommendations(recommendations_doc: dict) -> str:
    recommendations = recommendations_doc.get("recommendations", [])
    lines = ["Recommendations"]
    if not recommendations:
        lines.append("No recommendations are available yet.")
        return "\n".join(lines)
    lines.append(f"Overall result: {recommendations_doc.get('overall_decision', 'unknown')}")
    for item in recommendations:
        lines.append(
            f"- Rank {item.get('rank', '?')}: {item.get('route_name', item.get('route_id', 'Unknown route'))} "
            f"[{item.get('label', 'unknown')}]"
        )
        lines.append(f"  Reason: {item.get('recommendation_reason', '')}")
    return "\n".join(lines)


def render_route_comparison(route_comparison_doc: dict) -> str:
    routes = route_comparison_doc.get("routes", [])
    lines = ["Route comparison"]
    if not routes:
        lines.append("No route comparison is available yet.")
        return "\n".join(lines)
    for route in routes:
        lines.append(
            f"- {route.get('route_name', route.get('route_id', 'Unknown route'))}: "
            f"{route.get('evidence_strength', 'unknown')} evidence, "
            f"average score {route.get('evidence_score_breakdown', {}).get('average_paper_score', 'unknown')}/10."
        )
        if route.get("main_advantages"):
            lines.append(f"  Strengths: {'; '.join(route['main_advantages'])}")
        if route.get("main_limitations"):
            lines.append(f"  Limits: {'; '.join(route['main_limitations'])}")
        if route.get("major_uncertainties"):
            lines.append(f"  Unknowns: {'; '.join(route['major_uncertainties'])}")
    return "\n".join(lines)

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .orchestrator import Orchestrator
from .project import Project, slugify_project_name
from .presentation import (
    explain_status,
    render_recommendations,
    render_route_comparison,
    render_search_results,
    render_shortlist,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Literature review agent scaffold CLI.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Path to the Literature review agent project root.",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Optional name for the project folder inside projects/.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Initialize intake and reset workflow state.")
    start.add_argument("--question", required=True)
    start.add_argument("--intended-use", default="")
    start.add_argument("--desired-outcome", default="")
    start.add_argument("--review-purpose", default="")
    start.add_argument("--constraint", action="append", default=[])

    start_from_file = subparsers.add_parser("start-from-file", help="Initialize intake from a plain text template file.")
    start_from_file.add_argument("--input-file", type=Path, required=True)

    subparsers.add_parser("run", help="Run or resume the workflow.")
    subparsers.add_parser("status", help="Show current workflow state.")
    subparsers.add_parser("explain-status", help="Explain the current workflow status in plain English.")
    subparsers.add_parser("load-demo-papers", help="Load demo papers into state/papers.yml.")
    subparsers.add_parser("show-search-results", help="Show found papers in plain English.")
    subparsers.add_parser("show-shortlist", help="Show the current shortlist in plain English.")
    subparsers.add_parser("show-route-comparison", help="Show the route comparison in plain English.")
    subparsers.add_parser("show-recommendations", help="Show the final recommendations in plain English.")
    subparsers.add_parser("show-final-brief", help="Show the final brief text if it exists.")

    approve = subparsers.add_parser("approve-shortlist", help="Approve shortlisted papers.")
    approve.add_argument("--all", action="store_true", help="Approve all pending shortlisted papers.")
    approve.add_argument("--paper-id", action="append", default=[], help="Approve a specific paper ID.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    orchestrator = Orchestrator(args.project_root, args.project_name)
    project = Project(args.project_root, args.project_name)

    if args.command == "start":
        orchestrator.start(
            question=args.question,
            intended_use=args.intended_use,
            desired_outcome=args.desired_outcome,
            review_purpose=args.review_purpose,
            constraints=args.constraint,
            project_name=args.project_name,
        )
        print(f"Workflow initialized in projects/{orchestrator.project.project_name}.")
        return

    if args.command == "start-from-file":
        fields = parse_user_input_file(args.input_file)
        orchestrator.start(
            question=fields["question"],
            intended_use=fields["intended_use"],
            desired_outcome=fields["desired_outcome"],
            review_purpose=fields["review_purpose"],
            constraints=fields["constraints"],
            project_name=args.project_name or fields.get("project_name"),
            user_input_path=args.input_file,
        )
        print(f"Workflow initialized in projects/{orchestrator.project.project_name} from {args.input_file}.")
        return

    if args.command == "run":
        result = orchestrator.run()
        print(json.dumps(result, indent=2))
        return

    if args.command == "status":
        state = orchestrator.status()
        state.setdefault("project_name", project.project_name)
        state.setdefault("project_root", str(project.paths.runtime_root))
        print(json.dumps(state, indent=2))
        return

    if args.command == "explain-status":
        state = orchestrator.status()
        print(explain_status(state))
        return

    if args.command == "load-demo-papers":
        demo = project.load_example("demo_papers.yml", default={"papers": []})
        project.save_state("papers.yml", demo)
        print(f"Demo papers loaded into projects/{project.project_name}/state/papers.yml.")
        return

    if args.command == "show-search-results":
        papers_doc = project.load_state("papers.yml", default={"papers": []})
        print(render_search_results(papers_doc))
        return

    if args.command == "show-shortlist":
        shortlist = project.load_state("shortlist.yml", default={})
        print(render_shortlist(shortlist))
        return

    if args.command == "show-route-comparison":
        route_comparison = project.load_state("route_comparison.yml", default={})
        print(render_route_comparison(route_comparison))
        return

    if args.command == "show-recommendations":
        recommendations = project.load_state("recommendations.yml", default={})
        print(render_recommendations(recommendations))
        return

    if args.command == "show-final-brief":
        final_brief = project.paths.outputs_dir / "final_brief.md"
        if not final_brief.exists():
            print("No final brief exists yet.")
            return
        print(final_brief.read_text(encoding="utf-8"))
        return

    if args.command == "approve-shortlist":
        orchestrator.approve_shortlist(all_papers=args.all, paper_ids=args.paper_id)
        print(f"Shortlist updated in projects/{project.project_name}.")
        return

    parser.error("Unknown command.")


def parse_user_input_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    labels = {
        "Question:": "question",
        "Where It Will Be Used:": "intended_use",
        "What Outcome Matters Most:": "desired_outcome",
        "What Is This For:": "review_purpose",
        "Limits Or Constraints:": "constraints_text",
        "Additional Notes:": "additional_notes",
    }
    result = {value: "" for value in labels.values()}
    current_key = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_key
        if current_key is None:
            return
        content = "\n".join(line for line in buffer if line.strip()).strip()
        result[current_key] = content
        buffer = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        matched_label = next((label for label in labels if stripped == label), None)
        if matched_label:
            flush()
            current_key = labels[matched_label]
            continue
        inline_label = next((label for label in labels if stripped.startswith(label)), None)
        if inline_label:
            flush()
            current_key = labels[inline_label]
            inline_value = stripped[len(inline_label) :].strip()
            if inline_value:
                buffer.append(inline_value)
            continue
        if current_key is not None:
            buffer.append(line)
    flush()

    constraints = [line.strip() for line in result["constraints_text"].splitlines() if line.strip()]
    additional_notes = result.get("additional_notes", "").strip()
    if additional_notes:
        constraints.append(f"Additional note: {additional_notes}")

    return {
        "project_name": slugify_project_name(path.stem),
        "question": _clean_template_text(result.get("question", "")),
        "intended_use": _clean_template_text(result.get("intended_use", "")),
        "desired_outcome": _clean_template_text(result.get("desired_outcome", "")),
        "review_purpose": _clean_template_text(result.get("review_purpose", "")),
        "constraints": [_clean_template_text(item) for item in constraints if _clean_template_text(item)],
    }


def _clean_template_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("example:"):
            continue
        if stripped.lower().startswith("help:"):
            continue
        if stripped.lower().startswith("step "):
            continue
        if stripped.lower().startswith("how to use this file"):
            continue
        lines.append(stripped)
    return " ".join(lines).strip()

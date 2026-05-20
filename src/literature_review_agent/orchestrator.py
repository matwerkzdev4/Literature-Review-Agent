from __future__ import annotations

from pathlib import Path
from typing import Any

from .agents import AGENT_REGISTRY, WORKFLOW_ORDER
from .presentation import render_recommendations
from .project import Project, slugify_project_name


class Orchestrator:
    def __init__(self, project_root: Path, project_name: str | None = None) -> None:
        self.project_root = project_root
        self.project = Project(project_root, project_name)

    def start(
        self,
        *,
        question: str,
        intended_use: str = "",
        desired_outcome: str = "",
        review_purpose: str = "",
        constraints: list[str] | None = None,
        project_name: str | None = None,
        user_input_path: Path | None = None,
    ) -> None:
        resolved_project_name = slugify_project_name(project_name or question)
        self.project = Project(self.project_root, resolved_project_name)
        self.project.set_active_project(resolved_project_name)
        self.project.reset_runtime_state()
        self.project.save_state(
            "intake.yml",
            {
                "project_name": resolved_project_name,
                "question": question,
                "intended_use": intended_use,
                "desired_outcome": desired_outcome,
                "review_purpose": review_purpose,
                "constraints": constraints or [],
                "assumptions": [],
            },
        )
        if user_input_path is not None:
            self.project.save_user_input_snapshot(source_path=user_input_path)
        else:
            self.project.save_user_input_snapshot(
                content="\n".join(
                    [
                        f"Question: {question}",
                        f"Where It Will Be Used: {intended_use}",
                        f"What Outcome Matters Most: {desired_outcome}",
                        f"What Is This For: {review_purpose}",
                        "Limits Or Constraints:",
                        *(constraints or []),
                    ]
                )
            )
        workflow_state = self.project.load_workflow_state()
        workflow_state["project_name"] = resolved_project_name
        workflow_state["project_root"] = str(self.project.paths.runtime_root)
        workflow_state["current_stage"] = WORKFLOW_ORDER[0]
        workflow_state["workflow_status"] = "not_started"
        workflow_state["approval_gate"]["status"] = "waiting"
        workflow_state["early_stop"] = {
            "triggered": False,
            "reason": "",
            "stage": "",
            "surviving_route_ids": [],
        }
        workflow_state["final_decision"] = {"overall_label": "", "summary": ""}
        workflow_state["compliance"] = {"passed": False, "issues": [], "required_sections": []}
        for stage in workflow_state.get("stage_status", {}):
            workflow_state["stage_status"][stage] = "pending"
        self.project.save_workflow_state(workflow_state)

    def status(self) -> dict[str, Any]:
        return self.project.load_workflow_state()

    def approve_shortlist(self, all_papers: bool = False, paper_ids: list[str] | None = None) -> None:
        shortlist = self.project.load_state("shortlist.yml", default={})
        approved_ids = list(shortlist.get("user_actions", {}).get("approved_paper_ids", []))
        target_ids = set(paper_ids or [])
        for paper in shortlist.get("ranked_papers", []):
            should_approve = all_papers or paper.get("paper_id") in target_ids
            if should_approve:
                paper["approval_status"] = "approved"
                if paper["paper_id"] not in approved_ids:
                    approved_ids.append(paper["paper_id"])
        shortlist.setdefault("user_actions", {})
        shortlist["user_actions"]["approved_paper_ids"] = approved_ids
        shortlist["shortlist_status"] = "approved"
        self.project.save_state("shortlist.yml", shortlist)

        workflow_state = self.project.load_workflow_state()
        workflow_state["workflow_status"] = "in_progress"
        workflow_state["approval_gate"]["status"] = "approved"
        self.project.save_workflow_state(workflow_state)

    def run(self) -> dict[str, Any]:
        workflow_state = self.project.load_workflow_state()
        if workflow_state.get("workflow_status") == "completed":
            return workflow_state

        workflow_state["workflow_status"] = "in_progress"
        start_stage = self._resolve_start_stage(workflow_state)
        for stage_name in WORKFLOW_ORDER[WORKFLOW_ORDER.index(start_stage) :]:
            if stage_name == "full_text_extraction_agent" and workflow_state["approval_gate"]["required"]:
                shortlist = self.project.load_state("shortlist.yml", default={})
                if shortlist.get("shortlist_status") != "approved":
                    workflow_state["workflow_status"] = "waiting_for_user"
                    workflow_state["current_stage"] = stage_name
                    self.project.save_workflow_state(workflow_state)
                    return workflow_state

            workflow_state["current_stage"] = stage_name
            workflow_state["stage_status"][stage_name] = "in_progress"
            self.project.save_workflow_state(workflow_state)

            result = AGENT_REGISTRY[stage_name].run(self.project)

            workflow_state = self.project.load_workflow_state()
            workflow_state["stage_status"][stage_name] = "completed"
            workflow_state["notes"] = "\n".join(result.notes)

            if result.stop_early:
                workflow_state["workflow_status"] = "stopped_early"
                workflow_state["early_stop"] = {
                    "triggered": True,
                    "reason": result.stop_reason,
                    "stage": stage_name,
                    "surviving_route_ids": [],
                }
                workflow_state["final_decision"] = {
                    "overall_label": "not recommended",
                    "summary": result.stop_reason,
                }
                self.project.save_workflow_state(workflow_state)
                self._write_early_stop_brief(result.stop_reason)
                return workflow_state

            if result.pause:
                workflow_state["workflow_status"] = "waiting_for_user"
                workflow_state["approval_gate"]["status"] = "pending_user_approval"
                self.project.save_workflow_state(workflow_state)
                return workflow_state

            self.project.save_workflow_state(workflow_state)

        recommendations = self.project.load_state("recommendations.yml", default={})
        workflow_state = self.project.load_workflow_state()
        workflow_state["workflow_status"] = "completed"
        workflow_state["final_decision"] = {
            "overall_label": recommendations.get("overall_decision", ""),
            "summary": recommendations.get("final_summary", ""),
        }
        self.project.save_workflow_state(workflow_state)
        return workflow_state

    def _write_early_stop_brief(self, reason: str) -> None:
        intake = self.project.load_state("intake.yml", default={})
        recommendations_doc = {
            "recommendations": [],
            "final_summary": reason,
            "overall_decision": "not recommended",
        }
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
        lines.extend(
            [
                "",
                "# Ranked Routes",
                "",
                "- No route could be recommended.",
                "",
                "# Evidence Summary",
                "",
                f"- The workflow stopped early because: {reason}",
                "",
                "# Lab Analogue Plan",
                "",
                "- No meaningful lab analogue could be confirmed from the available evidence.",
                "",
                "# Recommended Next Experiment",
                "",
                "- No experiment is recommended until stronger evidence is available.",
                "",
                "# Risks and Unknowns",
                "",
                f"- Early-stop reason: {reason}",
                "",
            ]
        )
        output_path = self.project.paths.outputs_dir / "final_brief.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        recommendations_path = self.project.paths.outputs_dir / "recommendations.txt"
        recommendations_path.write_text(render_recommendations(recommendations_doc) + "\n", encoding="utf-8")

    def _resolve_start_stage(self, workflow_state: dict[str, Any]) -> str:
        current = workflow_state.get("current_stage") or WORKFLOW_ORDER[0]
        stage_status = workflow_state.get("stage_status", {})
        if stage_status.get(current) in {"pending", "in_progress"}:
            return current
        for stage in WORKFLOW_ORDER:
            if stage_status.get(stage) != "completed":
                return stage
        return WORKFLOW_ORDER[-1]

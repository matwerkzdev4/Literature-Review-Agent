from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literature_review_agent.extraction import build_extraction_from_text
from literature_review_agent.search_sources import SearchResult
from literature_review_agent.orchestrator import Orchestrator
from literature_review_agent.cli import parse_user_input_file
from literature_review_agent.presentation import (
    explain_status,
    render_recommendations,
    render_route_comparison,
    render_search_results,
    render_shortlist,
)
from literature_review_agent.project import Project


FIXTURE_FILES = [
    "configs",
    "templates",
    "state",
]


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "project"
        self.root.mkdir(parents=True)
        source_root = Path("/home/user/code/Literature review agent")
        for name in FIXTURE_FILES:
            shutil.copytree(source_root / name, self.root / name)
        Project(self.root).reset_runtime_state()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def runtime_root(self) -> Path:
        return Project(self.root).paths.runtime_root

    def runtime_state(self, name: str) -> Path:
        return self.runtime_root() / "state" / name

    def runtime_output(self, name: str) -> Path:
        return self.runtime_root() / "outputs" / name

    def test_start_populates_intake_and_resets_workflow(self) -> None:
        orchestrator = Orchestrator(self.root)
        stale_output_dir = self.runtime_root() / "outputs"
        stale_output_dir.mkdir(exist_ok=True)
        (stale_output_dir / "final_brief.md").write_text("stale", encoding="utf-8")
        orchestrator.start(question="How should we compare routes?")
        workflow_state = orchestrator.status()
        self.assertEqual(workflow_state["current_stage"], "intake_agent")
        self.assertEqual(workflow_state["workflow_status"], "not_started")
        self.assertFalse(self.runtime_output("final_brief.md").exists())

    def test_run_pauses_after_ranking_when_shortlist_needs_approval(self) -> None:
        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Assess slurry processing routes")
        papers_path = self.runtime_state("papers.yml")
        papers_path.write_text(
            "\n".join(
                [
                    "papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Example experimental paper",
                    "    abstract: Experimental process study with pilot signal.",
                    "    route_ids: [ROUTE-001]",
                    "    pilot_signal: pilot",
                    "    industrial_compatibility_signal: standard equipment",
                ]
            ),
            encoding="utf-8",
        )
        result = orchestrator.run()
        self.assertEqual(result["workflow_status"], "waiting_for_user")
        self.assertEqual(result["approval_gate"]["status"], "pending_user_approval")

    def test_approve_shortlist_marks_papers_as_approved(self) -> None:
        orchestrator = Orchestrator(self.root)
        shortlist_path = self.runtime_state("shortlist.yml")
        shortlist_path.write_text(
            "\n".join(
                [
                    'shortlist_status: "pending_user_approval"',
                    "ranked_routes: []",
                    "ranked_papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Example",
                    "    route_ids: [ROUTE-001]",
                    "    paper_rank: 1",
                    '    shortlist_reason: "Test"',
                    '    approval_status: "pending"',
                    "user_actions:",
                    "  approved_paper_ids: []",
                    "  removed_paper_ids: []",
                    "  reprioritized_paper_ids: []",
                    'notes: ""',
                ]
            ),
            encoding="utf-8",
        )
        orchestrator.approve_shortlist(all_papers=True)
        updated = shortlist_path.read_text(encoding="utf-8")
        self.assertIn('approval_status: approved', updated)

    def test_load_demo_papers_fixture_is_available(self) -> None:
        source_root = Path("/home/user/code/Literature review agent")
        examples_dir = source_root / "examples"
        shutil.copytree(examples_dir, self.root / "examples")
        project = Project(self.root)
        demo = project.load_example("demo_papers.yml", default={})
        self.assertEqual(len(demo.get("papers", [])), 2)

    def test_explain_status_waiting_for_user_is_plain_english(self) -> None:
        message = explain_status(
            {
                "workflow_status": "waiting_for_user",
                "current_stage": "full_text_extraction_agent",
                "approval_gate": {"status": "pending_user_approval"},
                "notes": "Shortlist prepared and awaiting approval.",
            }
        )
        self.assertIn("paused", message)
        self.assertIn("approve the shortlist", message)

    @patch("literature_review_agent.agents.search_source")
    def test_search_agent_populates_papers_from_supported_sources(self, search_source_mock) -> None:
        def fake_search(source, query, limit=5):
            source_id = source.get("source_id")
            if source_id == "DOAJ":
                return SearchResult(
                    papers=[
                        {
                            "paper_id": "DOAJ-001",
                            "title": "Open route paper",
                            "year": 2024,
                            "journal": "Open Journal",
                            "doi": "10.1/example",
                            "source": "DOAJ",
                            "url": "https://example.org/doaj-paper",
                            "abstract": "Experimental slurry process with pilot discussion.",
                            "route_ids": [],
                        }
                    ],
                    notes=["DOAJ returned 1 paper(s)."],
                )
            if source_id == "CORE":
                return SearchResult(papers=[], notes=["CORE returned 0 paper(s)."])
            return SearchResult(papers=[], notes=[f"{source_id} is approved but does not have an automated search adapter yet."])

        search_source_mock.side_effect = fake_search

        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Compare ceramic slurry tape casting")
        orchestrator.run()

        papers_text = self.runtime_state("papers.yml").read_text(encoding="utf-8")
        self.assertIn("Open route paper", papers_text)
        self.assertIn("query:", papers_text)
        self.assertIn("query_variants:", papers_text)
        self.assertIn("search_notes:", papers_text)

    @patch("literature_review_agent.agents.fetch_document_metadata")
    def test_full_text_extraction_populates_real_fields_from_text(self, fetch_document_metadata_mock) -> None:
        fetch_document_metadata_mock.return_value = {
            "fetch_status": "ok",
            "page_title": "Pilot-scale ceramic tape casting",
            "summary_text": "Experimental tape casting process with 5 wt% binder and drying at 120 C.",
            "body_text": (
                "The slurry was mixed, ball milled, tape cast and dried. "
                "A pilot-scale line was discussed. "
                "The process used standard manufacturing equipment and reduced defects."
            ),
        }

        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Assess ceramic tape casting route")
        papers_path = self.runtime_state("papers.yml")
        papers_path.write_text(
            "\n".join(
                [
                    "papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Example experimental paper",
                    "    abstract: Experimental tape cast process with pilot discussion.",
                    "    route_ids: [ROUTE-001]",
                    "    url: https://example.org/paper",
                    "    status: shortlisted",
                ]
            ),
            encoding="utf-8",
        )
        shortlist_path = self.runtime_state("shortlist.yml")
        shortlist_path.write_text(
            "\n".join(
                [
                    'shortlist_status: "approved"',
                    "ranked_routes: []",
                    "ranked_papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Example experimental paper",
                    "    route_ids: [ROUTE-001]",
                    "    paper_rank: 1",
                    '    shortlist_reason: "Test"',
                    '    approval_status: "approved"',
                    "user_actions:",
                    "  approved_paper_ids:",
                    "    - PAPER-001",
                    "  removed_paper_ids: []",
                    "  reprioritized_paper_ids: []",
                    'notes: ""',
                ]
            ),
            encoding="utf-8",
        )

        from literature_review_agent.agents import FullTextExtractionAgent

        FullTextExtractionAgent().run(Project(self.root))
        detail_text = (self.runtime_root() / "state" / "paper_details" / "PAPER-001.yml").read_text(encoding="utf-8")
        self.assertIn("process_steps:", detail_text)
        self.assertIn("- mix", detail_text)
        self.assertIn("- mill", detail_text)
        self.assertIn("reported_scale: pilot", detail_text)
        self.assertIn("page_fetch_status: ok", detail_text)

    def test_build_extraction_from_text_pulls_process_and_parameters(self) -> None:
        extracted = build_extraction_from_text(
            {
                "title": "Tape casting study",
                "abstract": "The slurry was mixed and ball milled with 5 wt% binder, dried at 120 C for 2 h.",
            }
        )
        self.assertIn("mix", extracted["process_steps"])
        self.assertIn("mill", extracted["process_steps"])
        self.assertTrue(extracted["key_parameters"])
        self.assertIn("evidence_flags", extracted)
        self.assertTrue(extracted["evidence_flags"]["has_key_parameters"])
        self.assertTrue(extracted["summary_snippets"])

    def test_translation_agent_infers_route_name_from_question(self) -> None:
        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Compare mix mill cast dry routes")
        orchestrator.run()
        technical_scope = self.runtime_state("technical_scope.yml").read_text(encoding="utf-8")
        self.assertIn("Mix -> Mill -> Cast -> Dry route", technical_scope)

    def test_render_search_results_is_plain_english(self) -> None:
        message = render_search_results(
            {
                "query": "ceramic slurry",
                "query_variants": ["ceramic slurry", "slurry tape cast"],
                "papers": [
                    {
                        "paper_id": "PAPER-001",
                        "title": "Example paper",
                        "source": "DOAJ",
                        "status": "candidate",
                    }
                ],
                "search_notes": ["DOAJ returned 1 paper(s)."],
            }
        )
        self.assertIn("Search results", message)
        self.assertIn("Example paper", message)

    def test_render_shortlist_is_plain_english(self) -> None:
        message = render_shortlist(
            {
                "shortlist_status": "pending_user_approval",
                "ranked_routes": [{"rank": 1, "route_name": "Tape casting route"}],
                "ranked_papers": [
                    {
                        "paper_rank": 1,
                        "paper_id": "PAPER-001",
                        "title": "Example paper",
                        "approval_status": "pending",
                    }
                ],
            }
        )
        self.assertIn("Shortlist review", message)
        self.assertIn("Tape casting route", message)

    def test_render_recommendations_is_plain_english(self) -> None:
        message = render_recommendations(
            {
                "overall_decision": "recommended",
                "recommendations": [
                    {
                        "rank": 1,
                        "route_name": "Tape casting route",
                        "label": "recommended",
                        "recommendation_reason": "Strong evidence and workable analogue.",
                    }
                ],
            }
        )
        self.assertIn("Recommendations", message)
        self.assertIn("Tape casting route", message)

    def test_render_route_comparison_is_plain_english(self) -> None:
        message = render_route_comparison(
            {
                "routes": [
                    {
                        "route_name": "Tape casting route",
                        "evidence_strength": "strong",
                        "evidence_score_breakdown": {"average_paper_score": 6.5},
                        "main_advantages": ["Pilot or scale signal was detected."],
                        "main_limitations": ["Text mentions limited."],
                        "major_uncertainties": ["Key operating parameters were not clearly identified."],
                    }
                ]
            }
        )
        self.assertIn("Route comparison", message)
        self.assertIn("Tape casting route", message)

    def test_completed_run_writes_readable_output_files(self) -> None:
        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Compare mix mill cast dry routes")
        papers_path = self.runtime_state("papers.yml")
        papers_path.write_text(
            "\n".join(
                [
                    "papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Example experimental paper",
                    "    abstract: Experimental mix mill cast dry process with pilot discussion.",
                    "    route_ids: [ROUTE-001]",
                    "    pilot_signal: pilot",
                    "    industrial_compatibility_signal: standard equipment",
                    "    status: candidate",
                ]
            ),
            encoding="utf-8",
        )
        orchestrator.run()
        orchestrator.approve_shortlist(all_papers=True)
        orchestrator.run()
        self.assertTrue(self.runtime_output("search_results.txt").exists())
        self.assertTrue(self.runtime_output("shortlist_review.txt").exists())
        self.assertTrue(self.runtime_output("recommendations.txt").exists())
        self.assertTrue(self.runtime_output("final_brief.md").exists())

    def test_completed_run_writes_scored_route_comparison(self) -> None:
        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Compare mix mill cast dry routes")
        papers_path = self.runtime_state("papers.yml")
        papers_path.write_text(
            "\n".join(
                [
                    "papers:",
                    "  - paper_id: PAPER-001",
                    "    title: Pilot mix mill cast route",
                    "    abstract: Experimental mix mill cast dry process with pilot scale and standard manufacturing equipment.",
                    "    route_ids: [ROUTE-001]",
                    "    pilot_signal: pilot",
                    "    industrial_compatibility_signal: standard equipment",
                    "    status: candidate",
                ]
            ),
            encoding="utf-8",
        )
        orchestrator.run()
        orchestrator.approve_shortlist(all_papers=True)
        orchestrator.run()
        route_comparison = self.runtime_state("route_comparison.yml").read_text(encoding="utf-8")
        self.assertIn("evidence_score:", route_comparison)
        self.assertIn("evidence_score_breakdown:", route_comparison)

    def test_end_to_end_demo_flow_completes(self) -> None:
        source_root = Path("/home/user/code/Literature review agent")
        examples_dir = source_root / "examples"
        shutil.copytree(examples_dir, self.root / "examples")
        orchestrator = Orchestrator(self.root)
        orchestrator.start(question="Compare mix mill cast dry ceramic slurry routes")
        project = Project(self.root)
        demo = project.load_example("demo_papers.yml", default={"papers": []})
        project.save_state("papers.yml", demo)
        first = orchestrator.run()
        self.assertEqual(first["workflow_status"], "waiting_for_user")
        orchestrator.approve_shortlist(all_papers=True)
        final = orchestrator.run()
        self.assertEqual(final["workflow_status"], "completed")
        self.assertTrue(self.runtime_output("route_comparison.txt").exists())
        self.assertTrue(self.runtime_output("final_brief.md").exists())

    def test_parse_user_input_file_reads_plain_text_template(self) -> None:
        template = self.root / "user_input.txt"
        template.write_text(
            "\n".join(
                [
                    "Question:",
                    "I want to compare routes for a ceramic slurry.",
                    "",
                    "Where It Will Be Used:",
                    "This may be used for a lab coating process.",
                    "",
                    "What Outcome Matters Most:",
                    "I want the most practical route with the strongest evidence.",
                    "",
                    "What Is This For:",
                    "We want to choose the best next experiment.",
                    "",
                    "Limits Or Constraints:",
                    "Use public sources only.",
                    "Keep it simple to explain.",
                    "",
                    "Additional Notes:",
                    "Plain English is preferred.",
                ]
            ),
            encoding="utf-8",
        )
        parsed = parse_user_input_file(template)
        self.assertEqual(parsed["question"], "I want to compare routes for a ceramic slurry.")
        self.assertIn("Use public sources only.", parsed["constraints"])

    def test_parse_user_input_file_reads_same_line_answers(self) -> None:
        template = self.root / "user_input_same_line.txt"
        template.write_text(
            "\n".join(
                [
                    "Question: What are the best thermal insulation composite sheets and how are they made?",
                    "Where It Will Be Used: In battery packs.",
                    "What Outcome Matters Most: The route with the strongest evidence.",
                    "What Is This For: We want to choose the best next experiment.",
                    "Limits Or Constraints: Use public sources only.",
                    "Additional Notes: Plain English is fine.",
                ]
            ),
            encoding="utf-8",
        )
        parsed = parse_user_input_file(template)
        self.assertEqual(
            parsed["question"],
            "What are the best thermal insulation composite sheets and how are they made?",
        )
        self.assertEqual(parsed["intended_use"], "In battery packs.")


if __name__ == "__main__":
    unittest.main()

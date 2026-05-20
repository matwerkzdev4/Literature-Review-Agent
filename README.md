# Literature Review Agent

This project is a YAML-driven, resumable multi-agent workflow for turning a plain-English materials or process question into an experiment planning brief.

The workflow compares competing routes defined by process sequence, uses only approved public sources, ranks routes mainly by strength of evidence, pauses once for shortlist approval, and returns route labels of `recommended`, `conditional`, or `not recommended`.

## Final Brief Sections

The final brief must always contain these sections in this order:

1. Purpose
2. Assumptions
3. Ranked Routes
4. Evidence Summary
5. Lab Analogue Plan
6. Recommended Next Experiment
7. Risks and Unknowns

## Workflow Order

1. `intake_agent`
2. `translation_agent`
3. `search_agent`
4. `triage_agent`
5. `ranking_agent`
6. User approval gate
7. `full_text_extraction_agent`
8. `route_comparison_agent`
9. `lab_analogue_agent`
10. `recommendation_agent`
11. `compliance_agent`

The `orchestrator_agent` runs these steps sequentially and stores progress in YAML.

## CLI Scaffold

The project now includes a minimal Python scaffold for running the workflow state machine.

Example commands:

```bash
python3 -m literature_review_agent --project-root . start --question "Compare processing routes for the target material"
python3 -m literature_review_agent --project-root . start-from-file --input-file templates/user_input_template.txt
python3 -m literature_review_agent --project-root . run
python3 -m literature_review_agent --project-root . status
python3 -m literature_review_agent --project-root . approve-shortlist --all
python3 -m literature_review_agent --project-root . show-search-results
python3 -m literature_review_agent --project-root . show-shortlist
python3 -m literature_review_agent --project-root . show-recommendations
python3 -m literature_review_agent --project-root . show-final-brief
```

This scaffold manages YAML state, shortlist approval, pause and resume behavior, and final brief generation. It does not yet include real literature search integrations.

Each workflow run is saved in its own folder under `projects/<project_name>/`.

The workflow writes readable helper files into `projects/<project_name>/outputs/`:

- `search_results.txt`
- `route_comparison.txt`
- `shortlist_review.txt`
- `recommendations.txt`
- `final_brief.md`

For non-technical users, a plain-English intake template is available at [user_input_template.txt](/home/user/code/Literature%20review%20agent/templates/user_input_template.txt).

If you want a simpler starting point, use [SIMPLE_GUIDE.md](/home/user/code/Literature%20review%20agent/SIMPLE_GUIDE.md).

## Project Layout

```text
Literature review agent/
  agents/
  configs/
  projects/
  specs/
  templates/
  tone.yml
  workflow_change_log.yml
```

## Core Design Rules

- Route comparison is organized by process sequence.
- Search is limited to approved public sources.
- Evidence strength is the top recommendation factor.
- Humans approve only the shortlist.
- Subagents make local judgments.
- The orchestrator makes workflow decisions.
- The workflow must stop early if no defensible recommendation can be made.

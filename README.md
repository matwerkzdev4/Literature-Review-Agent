# Literature Review Agent

## What This Application Does

The Literature Review Agent helps a team turn a broad materials or process question into a clear experiment-planning brief. Instead of leaving research notes scattered across papers, spreadsheets, and conversations, it guides the work through a fixed review process: define the question, find candidate papers, shortlist useful evidence, compare possible process routes, check whether the lab has suitable equipment, and produce a concise recommendation.

In plain English, it is a decision-support tool for answering questions like:

- Which processing route looks most defensible based on public evidence?
- Which route should we test first in the lab?
- What evidence, risks, and unknowns should the team be aware of before spending time or money on experiments?

## Why It Matters

Early technical decisions are often made with incomplete information. A team may know that several routes are possible, but not which one has the strongest evidence, which one fits available equipment, or which one carries the biggest hidden risk.

This application creates value by making that decision process more structured, traceable, and repeatable. It helps reduce wasted experimental effort, captures assumptions clearly, and gives both technical and non-technical stakeholders a shared summary of why a route is recommended, conditional, or not recommended.

## Intended Impact

The goal is not to replace expert judgment. The goal is to make expert judgment easier to apply.

The application is designed to help teams:

- move from a broad research question to a practical next experiment,
- compare competing process routes using consistent criteria,
- preserve the reasoning behind each recommendation,
- identify weak evidence before it becomes an expensive lab trial,
- communicate findings in a brief that managers, engineers, and researchers can all read.

## Current Status

This repository is a working Python scaffold for the workflow. It can manage project folders, save YAML state, pause for shortlist approval, resume work, and generate plain-English output files.

It is not yet a fully automated production research system. The current version includes basic search and extraction logic, but deeper integrations with literature databases, PDF extraction, citation validation, and expert review workflows are still future work.

## What The Final Brief Contains

Each completed review produces a final brief with these sections:

1. Purpose
2. Assumptions
3. Ranked Routes
4. Evidence Summary
5. Lab Analogue Plan
6. Recommended Next Experiment
7. Risks and Unknowns

The final brief is intended to be short enough for decision-making, but structured enough that the recommendation can be challenged and improved.

## How The Workflow Works

The workflow follows a fixed sequence:

1. Intake the user's question.
2. Translate the question into a technical review scope.
3. Search approved public sources for candidate papers.
4. Triage papers that are not useful enough.
5. Rank the remaining papers and routes.
6. Pause for the user to approve the shortlist.
7. Extract useful details from approved papers.
8. Compare routes by evidence strength and process sequence.
9. Check whether a meaningful lab analogue can be run with available equipment.
10. Generate recommendations.
11. Check that the final brief has the required sections.

The workflow stores progress in YAML files so a review can be paused, inspected, and resumed.

## Example Outputs

Each workflow run is saved under:

```text
projects/<project_name>/
```

Readable output files are written to:

```text
projects/<project_name>/outputs/
```

Typical output files include:

- `search_results.txt`
- `shortlist_review.txt`
- `route_comparison.txt`
- `recommendations.txt`
- `final_brief.md`

## Using The CLI

The project includes a minimal command-line interface for running the workflow state machine.

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

For non-technical users, start with:

- `SIMPLE_GUIDE.md`
- `templates/user_input_template.txt`

## Project Layout

```text
Literature review agent/
  agents/       Notes about agent roles
  configs/      Approved sources, equipment, and decision rules
  projects/     Saved example and runtime workflow projects
  specs/        Workflow design and rationale
  src/          Python implementation
  templates/    User input and final brief templates
  tests/        Workflow tests
```

## Core Design Rules

- Routes are compared by process sequence.
- Evidence strength is the top recommendation factor.
- Search is limited to approved public sources.
- The user approves the shortlist before deeper extraction.
- Recommendations must be traceable to the evidence available.
- The workflow should stop early if no defensible recommendation can be made.

## Next Development Priorities

The most important improvements are:

- improve real literature search integrations,
- improve paper-to-route matching,
- extract better detail from PDFs and full-text papers,
- make evidence scoring more rigorous,
- improve the final brief for real project review meetings,
- validate recommendations with domain experts.

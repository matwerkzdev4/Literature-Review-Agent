# Project Handover

## What This Repository Is

This project is a YAML-driven Python scaffold for an experiment-planning literature review workflow. It takes a plain-English question, moves through a fixed multi-agent sequence, pauses for shortlist approval, and produces a final brief.

The code is a working scaffold, not a production-integrated research system. It currently relies on simple search and extraction logic and does not yet connect to real literature databases.

## Where Development Stopped

The latest recorded implementation work is documented in [project history.md](project history.md).

As of `2026-04-01`, the project had:

- a working CLI scaffold,
- resumable YAML state,
- project-per-run output folders under `projects/`,
- shortlist approval and resume behavior,
- plain-English helper outputs,
- a parser fix for same-line intake answers.

The main unfinished areas called out by the project itself are:

1. Improve route generation so broad questions do not collapse to generic route labels.
2. Improve paper-to-route matching.
3. Improve extraction depth from papers.
4. Improve the final brief quality.
5. Review first-run behavior and refine using user feedback.

## Canonical Files

These directories are the main development surfaces:

- `src/literature_review_agent/`: CLI and workflow implementation.
- `tests/`: current test coverage.
- `configs/`: workflow rules and equipment/source policy.
- `specs/`: workflow design and rationale.
- `templates/`: user-facing intake and output templates.
- `README.md` and `SIMPLE_GUIDE.md`: usage and orientation.
- `workflow_change_log.yml`: design decisions and workflow changes.
- `project history.md`: implementation history and next actions.

## Runtime Data Policy

There are three kinds of state in this repository:

1. Scaffold state
   Files under top-level `state/` are the base workflow scaffold and should stay in git.

2. Curated example runs
   `projects/smoke_test/` and `projects/user_input_template/` are retained on purpose because they document expected workflow behavior and provide a reproducible example handover path.

3. Future local runs
   New run folders under `projects/<project_name>/` should usually not be committed unless they are intentionally curated examples worth keeping.

## Git Tracking Policy

Tracked:

- source code,
- tests,
- specs and docs,
- stable configs,
- templates,
- curated example runs kept for handover.

Ignored:

- `__pycache__/`
- `*.pyc`
- `.active_project`
- `.codex`
- future uncurated run folders under `projects/`

## Important Current Behavior

- The orchestrator is sequential and YAML-backed.
- Route comparison is organized by process sequence.
- The workflow pauses once after ranking for shortlist approval.
- The workflow can stop early if no defensible path survives.
- The saved `user_input_template` example currently ends in early stop with `no_valid_path_with_current_equipment`.

Relevant example output:

- `projects/user_input_template/outputs/final_brief.md`
- `projects/user_input_template/state/workflow_state.yml`

## How To Continue Development

1. Read `README.md`.
2. Read `SIMPLE_GUIDE.md`.
3. Read `project history.md`.
4. Read `workflow_change_log.yml`.
5. Run the tests.
6. Run the saved example workflow to confirm behavior.
7. Choose one of the unfinished areas above and implement it with tests.

## Suggested First Commands

```bash
PYTHONPATH=src python3 -m pytest
PYTHONPATH=src python3 -m literature_review_agent --project-root . status
PYTHONPATH=src python3 -m literature_review_agent --project-root . --project-name smoke_test run
PYTHONPATH=src python3 -m literature_review_agent --project-root . --project-name user_input_template show-final-brief
```

## Publishing Notes

This folder was not originally a git repository. Before pushing:

1. Initialize git.
2. Review the staged files once.
3. Commit the repository with this handover state.
4. Push to the GitHub remote.

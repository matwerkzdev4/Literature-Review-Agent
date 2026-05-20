# Design Rationale

## Purpose

This workflow exists to turn a plain-English technical question into an evidence-based experiment planning brief.

It is designed for cases where a team needs to compare competing process routes, understand what the public literature really supports, and decide what experiment is most worth running next.

## Intended Outcome

The intended outcome is a concise and traceable planning brief that:

- compares competing routes defined by process sequence,
- judges the strength of the available public evidence,
- checks whether each route shows pilot-demonstrated and industrially compatible signals,
- assesses whether a meaningful directional lab analogue can be carried out with available equipment,
- and recommends the most defensible next experimental path.

The workflow is not trying to maximize literature completeness. It is trying to support a better next decision.

## What This Workflow Satisfies

This design is meant to satisfy the following needs:

- publicly accessible evidence only,
- repeatable route comparison,
- evidence-first recommendation logic,
- clear separation between evidence and interpretation,
- human approval at the shortlist stage,
- resumable progress through YAML state files,
- readable outputs for a mixed technical team,
- and explicit handling of weak-evidence or no-go outcomes.

## Key Design Choices

### Routes are defined by process sequence

The workflow compares routes by their process steps instead of grouping mainly by chemistry family or final manufacturing label.

This was chosen because the final product is an experiment planning brief. For planning, the practical sequence of operations matters more than naming categories alone.

### Evidence strength is the top ranking factor

The workflow ranks routes mainly by how strong, useful, and consistent the literature support is.

This was chosen to avoid overvaluing routes that look easy to try in the lab but are poorly supported by evidence.

### YAML is the shared workflow format

The workflow stores state in YAML files so both humans and agents can inspect the current position of the workflow.

This was chosen to make the process transparent, resumable, and easier to audit.

### The workflow uses specialist subagents

The work is split into bounded agents such as intake, search, triage, extraction, comparison, analogue assessment, recommendation, and compliance.

This was chosen so that each stage has one clear job and so that the workflow is easier to debug and maintain than a single large prompt.

### The orchestrator makes workflow decisions

Subagents make local judgments. The orchestrator decides whether to continue, pause for approval, stop early, or release the final brief.

This was chosen to keep workflow control consistent and prevent specialist agents from making conflicting process decisions.

### There is only one approval gate

Human approval happens only after shortlist ranking.

This was chosen to keep the workflow supervised where it matters most without making the rest of the workflow too slow or fragmented.

### Early stop is a valid output

The workflow may stop and return a negative result when the evidence is too weak or no meaningful lab analogue is possible.

This was chosen because a disciplined no-go answer is more valuable than a forced recommendation.

## Why These Choices Create Value

These design choices create value in several ways.

First, they reduce false confidence. The workflow is designed to prefer a careful negative answer over an impressive but weakly supported recommendation.

Second, they make the reasoning traceable. A team can inspect the route definitions, paper records, extracted evidence, and final recommendation path without relying on hidden reasoning.

Third, they make route comparison more consistent. Using process sequence as the comparison basis helps teams look at operational differences more clearly.

Fourth, they improve handoff. YAML state files and specialist subagents make it easier for different people or future agents to resume the work without rebuilding context.

Fifth, they support a mixed technical audience. The final brief is short and practical, but still tied to evidence.

## Known Tradeoffs

This design has deliberate tradeoffs.

- Restricting the workflow to public sources improves accessibility but may miss stronger closed-access evidence.
- A sequential v1 workflow is easier to control but not optimized for speed.
- Grouping routes by process sequence may simplify important chemistry differences in some cases.
- A directional lab analogue is useful for planning, but it is not the same as exact process replication.
- A concise final brief is easier to use, but some deeper nuance will remain in the YAML state rather than in the brief itself.

## What This Workflow Is Not Trying To Do

This workflow is not trying to be:

- a general academic literature review engine,
- a substitute for scientific judgment,
- a guarantee of industrial readiness,
- a replacement for human approval and team discussion,
- or a system that always returns a positive recommendation.

## Related Documents

- [Workflow Spec](/home/user/code/Literature%20review%20agent/specs/workflow_spec.md)
- [Agent Contracts](/home/user/code/Literature%20review%20agent/specs/agent_contracts.md)
- [Workflow Change Log](/home/user/code/Literature%20review%20agent/workflow_change_log.yml)

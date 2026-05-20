# Design Process

## Starting Point

This workflow began as one large prompt intended for use in ChatGPT agent mode.

That original prompt attempted to do literature screening, industrial relevance assessment, laboratory feasibility assessment, and report generation inside one single workflow instruction set.

## Original Intent

The original workflow was trying to do several useful things at once:

- find literature from approved public sources,
- identify industry-validated or scalable processes,
- assess whether lab work could be done with available equipment,
- and produce a structured report.

The overall intention was sound, but the workflow was too compressed into one prompt.

## Problems Found in the Original Workflow

During review, several design problems were identified.

### The objective was overloaded

The original workflow mixed literature discovery, industrial validation, lab feasibility assessment, and go or no-go guidance into one agent behavior.

### Important terms were too vague

Terms such as "industry-validated" were not precise enough to support repeatable decisions.

### Abstract screening carried too much weight

The original structure expected abstracts to support decisions that often require full-paper details.

### Formatting logic was mixed with reasoning logic

The original workflow tried to enforce report-format behavior inside the same prompt that handled scientific reasoning.

### Route comparison was underdefined

It was not initially clear whether routes should be compared by chemistry, processing family, or manufacturing method.

### The scoring logic risked oversimplifying

A compressed confidence score could hide important differences between routes.

## Clarifications Gathered During Planning

The redesign was shaped by a set of explicit decisions.

- The final output should be an experiment planning brief.
- Industrial relevance should mean pilot-demonstrated and compatible with standard industrial equipment.
- The workflow should compare multiple competing routes.
- Strength of evidence should be the main ranking factor.
- Lab feasibility should mean a meaningful directional analogue, not exact reproduction.
- The audience should be a mixed technical team.
- Human approval should happen only at the shortlist stage.
- YAML should be the main state format.
- Routes should be defined by process sequence for v1.

These clarifications changed the workflow substantially.

## Major Workflow Changes

The redesign introduced several major changes.

### From one large prompt to multiple agents

The workflow was split into specialist agents with bounded jobs, including intake, translation, search, triage, extraction, comparison, analogue assessment, recommendation, and compliance.

### From broad review to route comparison

The new workflow centers on comparing competing routes rather than just reviewing a single topic area.

### From general literature output to planning brief

The final output was narrowed to a practical experiment planning brief instead of a broader review report.

### From implicit control to explicit orchestration

A dedicated orchestrator was introduced to manage sequencing, pause and resume behavior, early-stop rules, and final release checks.

### From forced completion to valid early stop

The new design accepts that the workflow may end in a negative or no-go outcome when the evidence is too weak.

## Why the Agentic Structure Was Chosen

The agentic structure was chosen because it provides clearer boundaries and more reliable handoffs.

With a single large prompt, too many kinds of reasoning compete in the same place. With a structured workflow:

- each step has one main responsibility,
- outputs can be checked before the next step begins,
- workflow state can be resumed,
- and failures are easier to diagnose.

This makes the system more suitable for repeated use by a team.

## Role of the Change Log

The structured audit trail for design decisions is stored in the workflow change log.

This file should be read together with:

- [Workflow Change Log](/home/user/code/Literature%20review%20agent/workflow_change_log.yml)
- [Workflow Spec](/home/user/code/Literature%20review%20agent/specs/workflow_spec.md)
- [Agent Contracts](/home/user/code/Literature%20review%20agent/specs/agent_contracts.md)

In simple terms:

- `workflow_change_log.yml` records decisions in structured form,
- this document explains the reasoning journey in readable narrative form.

## Final Design Direction

The current design direction is a sequential, resumable, YAML-driven workflow where:

- routes are compared by process sequence,
- evidence strength leads ranking,
- a shortlist is approved by a human,
- route comparison and lab analogue feasibility are assessed after full-text extraction,
- and the final output is a concise experiment planning brief.

## Remaining Open Questions

At the current v1 planning stage, there are no major unresolved design questions recorded.

Later implementation work may still introduce practical questions about code structure, source integration, or automation boundaries, but the workflow design itself is now substantially defined.

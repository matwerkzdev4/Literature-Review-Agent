# Agent Contracts

## `intake_agent`

- Reads: raw user request
- Writes: `state/intake.yml`
- Owns: goal clarification, constraints capture, assumption logging

## `translation_agent`

- Reads: `state/intake.yml`
- Writes: `state/technical_scope.yml`
- Owns: technical scope, route definitions, search keywords

## `search_agent`

- Reads: `state/technical_scope.yml`, `configs/approved_sources.yml`
- Writes: `state/papers.yml`
- Owns: public-source search and initial route tagging

## `triage_agent`

- Reads: `state/papers.yml`, `state/technical_scope.yml`
- Writes: `state/papers.yml`
- Owns: title and abstract keep/reject decisions

## `ranking_agent`

- Reads: `state/papers.yml`, `state/technical_scope.yml`
- Writes: `state/shortlist.yml`
- Owns: provisional route and paper ranking for approval

## `full_text_extraction_agent`

- Reads: `state/shortlist.yml`, approved papers
- Writes: `state/paper_details/PAPER-*.yml`
- Owns: paper-level extraction of process details, scale signals, limits, and missing details

## `route_comparison_agent`

- Reads: `state/paper_details/*.yml`
- Writes: `state/route_comparison.yml`
- Owns: route-level evidence comparison

## `lab_analogue_agent`

- Reads: `state/paper_details/*.yml`, `state/route_comparison.yml`, `configs/equipment.yml`
- Writes: `state/lab_analogue.yml`
- Owns: directional analogue feasibility with available equipment

## `recommendation_agent`

- Reads: `state/route_comparison.yml`, `state/lab_analogue.yml`, `state/paper_details/*.yml`
- Writes: `state/recommendations.yml`
- Owns: route ranking, route labels, next-experiment recommendation

## `compliance_agent`

- Reads: `state/recommendations.yml`, final brief draft, `templates/final_brief_template.md`
- Writes: compliance result into `state/workflow_state.yml`
- Owns: format, section order, traceability, and evidence-before-interpretation checks

## `orchestrator_agent`

- Reads: all workflow state files
- Writes: `state/workflow_state.yml`
- Owns: sequencing, pause and resume, early stop, and release gating

# Project Handover

## Who This Handover Is For

This handover is written for a research engineer who may not have a software engineering background. You can continue developing this application by working with Codex in plain English.

You do not need to understand every code file before making progress. The best way to continue is to describe the research workflow you want, ask Codex to inspect the relevant files, ask it to make a focused change, and ask it to test the result.

## What This Application Is

The Literature Review Agent is a prototype tool for turning a broad materials or process question into an experiment-planning brief.

It is intended to help answer questions such as:

- Which processing route has the strongest public evidence?
- Which route should we test first in the lab?
- What risks or missing information should be discussed before starting experiments?
- Can the proposed route be meaningfully tested using available equipment?

The application stores each review as files, compares routes using a fixed workflow, pauses for the user to approve a shortlist of papers, and then writes a final brief.

## Current Maturity

This is a working scaffold, not a finished research product.

It can already:

- start a review from a plain-English question,
- save review progress,
- pause and resume,
- produce readable output files,
- keep example runs for handover,
- generate a final brief structure.

It cannot yet be fully trusted to perform a real literature review without human checking.

The main limitations are:

- literature search is still basic,
- full paper extraction is shallow,
- route matching is based on simple rules,
- evidence scoring is not yet rigorous,
- recommendations should be reviewed by a technical expert.

Treat the current system as a useful workflow assistant, not as an authority.

## The Most Important Files

Start with these files:

- `README.md`: explains what the application does and why it matters.
- `SIMPLE_GUIDE.md`: simpler user-facing guide.
- `templates/user_input_template.txt`: plain-English input form for a new review.
- `projects/user_input_template/outputs/final_brief.md`: example final output.
- `configs/equipment.yml`: lab equipment list used for feasibility checks.
- `configs/approved_sources.yml`: literature sources the workflow is allowed to use.
- `specs/workflow_spec.md`: the intended review logic.
- `src/literature_review_agent/agents.py`: the main workflow behavior.
- `src/literature_review_agent/search_sources.py`: search source connections.
- `src/literature_review_agent/extraction.py`: extraction of useful details from papers.
- `tests/test_workflow.py`: checks that the application still behaves as expected.

If you are unsure where to look, ask Codex:

```text
Read the handover, README, and workflow spec. Tell me which files control the part of the application I want to improve.
```

## How To Work With Codex

Use Codex as your software partner. Give it one clear task at a time.

Good example prompts:

```text
Review the current literature search logic and explain, in plain English, what sources it actually searches today.
```

```text
Improve the final brief so that it clearly separates evidence, assumptions, risks, and recommended next experiment. Keep the language suitable for a mixed technical and management audience.
```

```text
Add support for a better paper search source. First explain the options, then implement the simplest reliable one and add tests.
```

```text
The route names are too generic. Inspect the route generation logic and improve it so broad questions produce clearer process-route candidates.
```

```text
Run the tests, explain any failures in plain English, and fix only the failures related to this change.
```

Avoid broad prompts such as:

```text
Make the whole app better.
```

Instead, ask for one improvement at a time.

## Recommended Development Order

The most useful next improvements are:

1. Improve route generation.
   Broad user questions should produce meaningful route candidates, not vague labels.

2. Improve paper-to-route matching.
   Papers should be connected to the routes they actually support.

3. Improve paper extraction.
   The system needs better extraction from abstracts, HTML pages, and eventually PDFs.

4. Improve evidence scoring.
   Scoring should better reflect experimental quality, scale relevance, and process detail.

5. Improve the final brief.
   The final output should be good enough for a project review meeting.

6. Add stronger literature search integrations.
   The current search is limited and should not be treated as complete.

## How To Check The Application

Ask Codex to run these checks after changes:

```bash
python -m pytest
```

If that does not work, ask Codex:

```text
Run the project tests in the correct way for this machine. If they fail because of paths or setup, explain the issue and fix the project-local cause.
```

Useful workflow commands are:

```bash
python -m literature_review_agent --project-root . status
python -m literature_review_agent --project-root . start --question "Compare processing routes for the target material"
python -m literature_review_agent --project-root . run
python -m literature_review_agent --project-root . approve-shortlist --all
python -m literature_review_agent --project-root . show-final-brief
```

If Python cannot find the package, ask Codex to run the command with `PYTHONPATH=src` or the Windows equivalent.

## Data And Folder Policy

Keep these in GitHub:

- source code,
- tests,
- documentation,
- templates,
- configs,
- curated example runs.

Be careful with new folders under:

```text
projects/<project_name>/
```

These folders contain review runs. Commit them only if they are useful examples for future handover or validation. Do not commit confidential project work, private papers, or sensitive customer information.

## Important Current Behavior

- The workflow is sequential.
- Progress is saved in YAML files.
- The user approves the shortlist before deeper review.
- Routes are compared by process sequence.
- Evidence strength is the main recommendation factor.
- The workflow can stop early if it cannot make a defensible recommendation.

One saved example currently ends with:

```text
no_valid_path_with_current_equipment
```

That is not necessarily a bug. It means the workflow decided that the available equipment did not support a meaningful lab analogue for that example.

## What To Be Careful About

Do not assume the application has read every important paper. It has not.

Do not assume a `recommended` label means the route is truly ready for investment. It means the current rules found it more defensible than the alternatives.

Do not add private or paid paper contents to GitHub unless you are certain they are allowed to be shared.

Do not make many large changes at once. Ask Codex to keep each change focused and tested.

## Suggested First Codex Session

Start by asking Codex:

```text
Read README.md, HANDOVER.md, SIMPLE_GUIDE.md, and specs/workflow_spec.md. Summarise the application in plain English, identify the top 3 limitations, and recommend the first improvement to make.
```

Then ask:

```text
Inspect the code for that first improvement, propose a small implementation plan, then make the change and run the tests.
```

## Publishing Changes

When you are happy with a change, ask Codex:

```text
Show me the git status and summarise what changed in plain English.
```

Then:

```text
Commit and push the changes to GitHub with a clear commit message.
```

Codex can handle the Git commands, but you should still read its summary before pushing important changes.

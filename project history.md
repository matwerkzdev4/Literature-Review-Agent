# Project History

## 2026-04-01

### Summary

- Built the first working version of the workflow.
- Added the agent structure, YAML state files, and project documentation.
- Added a runnable Python command-line workflow.
- Added simple search, shortlist approval, route comparison, and final brief generation.
- Added plain-English helper commands and readable output files.
- Added a plain-English user input template.
- Fixed the input parser so it can read answers written on the same line as each section title.
- Changed the workflow so each run is saved in its own folder under `projects/`.
- Ran a demo using the saved user input file.
- Confirmed that the user input is now read correctly.
- The demo ended with an early stop because the sample papers were too weak for a real recommendation.

### Current State

- The workflow runs end to end.
- It can pause for shortlist approval.
- It saves project files in `projects/<project_name>/`.
- It creates a final brief and other helper output files.
- It still uses simple scoring and simple paper reading.
- Real search coverage is still limited.

### Action Plan For Next Time

1. Improve route generation so broad questions do not fall back to `Primary route candidate`.
2. Improve paper-to-route matching so routes are more meaningful.
3. Improve paper reading so the workflow pulls better process details from papers.
4. Improve the final brief so it reads more like a real review output.
5. Review the first-run output with user feedback and refine the workflow based on that.

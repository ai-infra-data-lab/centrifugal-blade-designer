---
name: blade-designer-checks
description: Implement and verify changes in centrifugal_blade_designer using its selected Python environment, concise test reports and scoped Git workflow. Use for this app's development and validation; do not apply to the parent ledger app.
---

Work from the blade-designer project directory. Follow its AGENTS.md and inspect
FEATURES.md plus the modules/specifications/tests relevant to the requested change.
Do not load every audit document by default. The parent Git repository also owns
an unrelated ledger app.

Use the selected `.venv/Scripts/python.exe` on Windows. The operational details,
tool versions and optional RTK restrictions are in
`../../../docs/DEVELOPMENT_TOOLS.md` relative to this skill folder; read the needed
section only. Git/subtree publication is in `../../../docs/DEVELOPMENT.md`.

- While editing, start with `tools/run_tests.py --suite quick --brief`, then run
  explicitly relevant test paths through the same runner. Quick is six basic
  numerical test files, not proof of GUI, serialization, output or CAD behavior.
- Before completion, run the full regression when AGENTS.md requires it. Use
  `tools/run_tests.py --suite full --brief`; if partitioning is justified by time,
  account for every collected ID and report missing/duplicate/skip/error cases.
- `--brief` saves the full pytest log and JUnit locally. Read the failed test's
  log when the summary is insufficient. Never replace the runner with bare pytest
  or discard warnings, failure details, collection errors or exit codes.
- Run the documented isolated Ruff check for modified Python code. Do not apply
  broad formatting or automatic fixes as part of feature work.
- Distinguish analytic tests, historical numerical fixtures, Qt offscreen,
  actual CAD-kernel checks, native GUI and ANSYS verification. Do not convert
  an unavailable/skipped check into PASS.
- The user has authorized committing completed fixes in this project. Inspect
  diffs and stage explicit project paths only. Do not stage unrelated work or
  use `git add .`. Push needs a current explicit user request. Read-only/planning
  requests do not authorize edits or commits.

Report what changed, test counts/errors and evidence locations, commit ID if
created, and the relevant remaining manual checks. Keep successful output short;
provide details needed to diagnose a failure. Do not claim a token-saving rate
without measuring it in the current workflow.

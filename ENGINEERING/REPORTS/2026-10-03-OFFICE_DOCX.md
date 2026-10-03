# OFFICE-001 Arabic text to DOCX experiment

Date: 2026-10-03. Repository: n923760-rgb/digital-services-platform.
Starting main: 1d948707fa55d144d435dc971247c5c8c127a95f;
tree: 2c67e162d45d3db1d720fd3bafa5422e1038bde8.
Central reference read from current main; repository's adopted reference is
641e4f9e45da109257ba1f38752b94604c2e4531. Final task source and CI IDs belong in the PR.
Task branch: feat/office-docx-experiment.

## Requirement and authorization

FACT: owner requested integrated office services and continued the proposed local
Arabic text-to-Word slice. Asked whether there are actual customer requests or an
experiment; exact owner answer was “كمل بدون توقف”. This authorizes continuing the
named experiment, not a factual claim of customer demand. The current trigger is
the requested office experiment and missing Word executor. Actual customer demand
remains UNKNOWN. Do not interpret the answer as launch, prices, providers or scale.
This is separate from the earlier Office deferral described in draft PR 45.

## Scope and source review

FACT: new independent standard-library formatter in platform_core, fixed template,
immutable bounded input, editable DOCX bytes and SHA-256, sanitized input failures,
native styles/RTL runs and deterministic ZIP timestamps. No file paths or metadata
are derived from customer input. No dependencies, migrations, queues or framework.
Existing bot, financial history, service registry and flags are unchanged.
PR 45 edits the roadmap/trial guide; neither is modified here. This task report
records the new scope without creating a second roadmap. Reconcile its pending
deferral text when that independent PR is reviewed.

Changed files: office_docx.py, test_office_docx.py, docs/OFFICE-DOCX.md and this report.
Local snapshot is isolated from other work; repository writes use the GitHub API.
QA fixtures are synthetic and excluded from commits, along with rendered previews.

## Verification

Available: repository API, local Python 3.12.14, packaged document converter and PNG
inspection. No project locked environment, local pytest/Ruff, PostgreSQL or Compose.

| Check | Actual result |
| --- | --- |
| Python unittest discovery on changed module | PASS, 16 tests |
| Arabic/mixed text, controls, blank/overlimit input, output failure | PASS in unit checks |
| Exact text order, spaces, tabs, newline normalization, passive ZIP and digest | PASS |
| Alternating scripts and 40,000-character aggregate boundary | PASS |
| Synthetic native DOCX renders | PASS conversion, 1 mixed page and 3 long pages |
| Arabic alignment, line wrapping, four page images inspected | PASS for these fixtures |
| Mixed XML-like angle brackets/quotes visual order | FAIL; converter still misorders punctuation despite native text preservation |
| Complete visual gate | BLOCKED pending punctuation fix and reinspection |
| Real Word desktop/mobile edit and Telegram artifact delivery | NOT RUN |
| Full locked pytest, Ruff, dependency checks, DB/Compose | NOT RUN locally; existing exact-source CI pending |

Command: `PYTHONPATH=packages/python python -m unittest discover -s tests -p test_office_docx.py -q`
using the bundled Python 3.12.14. Renderer: bundled documents/render_docx.py, then
every page PNG opened. Logical `w:jc=start` corrected the initial Arabic alignment
failure. Native opposite-direction runs/embedding preserve strings but do not yet
qualify all mixed punctuation rendering. No paid or production safety claim follows.

## Result and next bounded correction

Experimental formatter and structural tests are implemented. Leave PR draft because
the visual gate is incomplete. Correct mixed punctuation on the actual rendering path
and re-render all affected samples before promoting the executor. After that,
private artifact ownership, expiry, cached delivery and actual Telegram receipts
need their own bounded implementation; this module alone authorizes none of them.

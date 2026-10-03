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
native styles/RTL runs, balanced Latin embeddings and deterministic ZIP timestamps. No file paths or metadata
are derived from customer input. No dependencies, migrations, queues or framework.
Existing bot, financial history, service registry and flags are unchanged.
PR 45 edits the roadmap/trial guide; neither is modified here. This task report
records the new scope without creating a second roadmap. Reconcile its pending
deferral text when that independent PR is reviewed.

Changed files: office_docx.py, test_office_docx.py, docs/OFFICE-DOCX.md and this report.
Local snapshot is isolated from other work; repository writes use the GitHub API.
QA fixtures are synthetic and excluded from commits, along with rendered previews.

Initial source a6d7a1a4d2b44967674664c88f808291f0bc5b4e triggered Foundation
37127044926 and advisory 37127044943. Advisory and web passed; Python stopped at
Ruff with import ordering and two nested-context style findings. Corrected those
four findings in the follow-up commit. At 0f295c2b72672ff92a625f6928774f8b0e9359f4,
Foundation 37127250460 still rejected the ordering of MAX_BLOCK_CHARS/MAX_BLOCKS;
corrected it to the exact Ruff diagnostic. Final-source CI must be checked independently.

At source 8dfb4abc3057bc72bb71d5eb20b849495fe1c2d5, Foundation runs
37127382847 (PR) and 37127380564 (push) passed Python, web and Compose. Advisory
runs 37127382845 and 37127380567 passed. Python collected 182 tests plus 24
subtests. The PR stayed draft because the mixed punctuation visual gate failed.
Those results are historical and do not prove this follow-up source passes CI.

## Mixed punctuation correction

FACT: owner continued the requested quality work with “تمام كمل”. The observed
misordering of `<tag> & "quote".`, 2026-10-03 and 12.5% is the correction trigger.
Removing run direction attributes, using a single run, and retaining native w:dir
embedding did not change the rendered punctuation. Unicode LRE/PDF embeddings
around Latin text in RTL paragraphs fixed these inspected cases. Native w:dir
wrappers were removed; ordinary runs are readable/editable through python-docx.
Trailing whitespace stays outside embeddings, and tabs/line breaks separate them.

CONTRACT CHANGE: output contains invisible U+202A/U+202C formatting marks; raw
extracted/copied text is no longer exactly the submitted string. Original request
strings remain unchanged. Logical comparison strips only these generated marks.
Input embeddings/overrides/isolates are rejected with a sanitized code, including
unbalanced controls; this is documented rather than silently rewriting input.
No new runtime dependency, agent, provider or activation is introduced.

Reference: [Microsoft's w:dir specification](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.bidirectionalembedding)
describes markup as equivalent to LRE/RLE and PDF characters. The implementation
uses explicit LRE/PDF because the available native converter ignored w:dir for
these cases. This is a measured renderer result, not a universal application claim.

## Verification

Available: repository API, local Python 3.12.14, packaged document converter and PNG
inspection. No project locked environment, local pytest/Ruff, PostgreSQL or Compose.

| Check | Actual result |
| --- | --- |
| Python unittest discovery on changed module | PASS, 18 tests |
| Arabic/mixed text, controls, blank/overlimit input, output failure | PASS in unit checks |
| Visible text order, spaces, tabs, newline normalization, passive ZIP and digest | PASS; generated direction marks excluded from logical comparison |
| Alternating scripts and 40,000-character aggregate boundary | PASS |
| Synthetic native DOCX renders | PASS conversion, 1 mixed page, 3 long pages, 1 punctuation page and 1 edited punctuation page |
| Arabic alignment, line wrapping, all six page images inspected | PASS for these fixtures; edited paragraph uses editor's default alignment |
| Mixed angle brackets/quotes, email, URL, identifier, date and percentage order | PASS on seven-case punctuation fixture and representative mixed fixture |
| Python-docx open/edit/save/reopen | PASS, existing visible content retained and appended paragraph readable |
| Native Word compatibility gate | NOT RUN; no universal compatibility claim |
| Real Word desktop/mobile edit and Telegram artifact delivery | NOT RUN |
| Full locked pytest, Ruff, dependency checks, DB/Compose | NOT RUN locally; existing exact-source CI pending |

Command: `PYTHONPATH=packages/python python -m unittest discover -s tests -p test_office_docx.py -q`
using the bundled Python 3.12.14. Renderer: bundled documents/render_docx.py, then
every page PNG opened. Logical `w:jc=start` corrected the initial Arabic alignment
failure. The follow-up's bounded Unicode embeddings corrected the inspected mixed
punctuation regression. No paid or production safety claim follows.

Synthetic DOCX SHA-256: mixed
`2b2ede4caf6c1972aff0acf98619c413f7a21d003a5cb593afae40b9effcd211`, long
`28f708da595c5157458a3b86ba984468364414de5d47f7b62a2be9c41170db21`, punctuation
`705abd30623f9204ff73cb00bf1c73720314996fd5f08f0ba699c1d9b611c429`.

## Result and next bounded correction

Experimental formatter, regression tests and observed punctuation correction are
implemented. Keep PR draft until final-source CI and native Word compatibility
are assessed. The six inspected pages pass the available renderer's visual gate.
After that,
private artifact ownership, expiry, cached delivery and actual Telegram receipts
need their own bounded implementation; this module alone authorizes none of them.

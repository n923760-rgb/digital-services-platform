# DSP-005 — processor input budgets before materialization

Date: 2026-10-01. Repository: n923760-rgb/digital-services-platform.
Baseline main: 4caecbe0514d925df3c834327691130abf91c5d6; no open PRs. Owner authorization to continue repairs and qualified merging persists; Telegram is the customer product.
Root AGENTS.md, PROJECT-SOURCES.md, canonical roadmap and dsp-file-security applied. Central reference head reverified unchanged at previously read 641e4f9e45da109257ba1f38752b94604c2e4531.
Capabilities: repository API/external CI. Local CLI, browser, provider and production tests NOT RUN.

## Causal diagnosis

FACT: process_pdf_merge read all order inputs into a list before merge_pdfs_isolated/merge_pdfs_in_sandbox enforced their 40 MiB total bound. Internal order callers could bypass bot admission and cause excessive parent input materialization. The size passed to GET came from freshly retrieved file metadata without an independent processor cap. Existing lower-level parser bounds remained useful but too late for this parent read.
FACT: S3Storage reads MaxBytes+1, and read_file rejects HEAD/GET size mismatch; this bounded-adapter contract is preserved.

## Bounded repair

Processor fetches at most eleven metadata rows, rejects invalid count, ownership, INPUT type, PDF MIME, readiness and expiry, then enforces per-file MAX_UPLOAD_BYTES and aggregate MAX_INPUT_BYTES before any storage access.
Each sequential read receives min(per-file cap, remaining aggregate budget); verify_file checks the newly retrieved size before HEAD/GET. Actual accepted lengths decrement the remaining budget. Object mismatch rejects processing before parser/output.
read_file and verify_file accept optional keyword max_bytes; existing callers retain default semantics.
No parsing, isolation, financial, schema, dependency, launch flag or deployment changes.

## Reviewed files and evidence

Source: packages/python/platform_core/processors.py and files.py. Tests: tests/test_pdf_merge_slice.py. Documentation: docs/FILES.md, canonical roadmap and this report.
Eight additional PostgreSQL cases use small test objects with large metadata to demonstrate rejection without allocating large files: aggregate overrun, single-file overrun, expired/foreign/wrong-type input, metadata growth after preflight, exact aggregate boundary and object growth after HEAD. Existing valid isolated processing/delivery and financial failure regressions remain.
At report preparation: external CI pending; local commands NOT RUN. The associated PR records exact tested head, actual run URL, conclusions, test total and merge state after qualification. Do not infer PASS from prepared prose.

## Limits and next task

This bounds accepted raw input bytes per process_pdf_merge call, not total RSS, parser/decompression allocation or fleet concurrency. A bounded storage adapter remains part of the trusted contract; an arbitrary internal implementation that ignores MaxBytes could allocate excessive data before returning. Existing parsing/sandbox/output limits remain unchanged. Independent direct list-based parser calls already receive caller-materialized bytes and are outside this processor acquisition fix.
Historical DSP-004 CI/merge proof: PR #26, run 36896881244, 82 tests and Python/web/Compose PASS; main merge 4caecbe0514d925df3c834327691130abf91c5d6.
Next bounded task: DSP-009 truthful Telegram intake/supported-input guidance. Actual Telegram, malware, production storage/recovery, long-job liveness and load/RSS evidence remain unqualified.

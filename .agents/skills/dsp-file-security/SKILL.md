---
name: dsp-file-security
description: Review file upload admission, customer ownership, bounded PDF isolation, retention and storage recovery.
---

# dsp-file-security

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Read FILES/BACKUP-RECOVERY contracts, files.py, storage_s3.py, processors.py, pdf_* modules, Telegram upload/retrieval and Docker sandbox configuration.
2. Trace admission -> byte/type/aggregate validation -> metadata intent -> storage -> attachment -> isolated parsing -> output verification -> authorized delivery -> expiry/deletion. Check rejected/cancelled/concurrent uploads and orphan cleanup, not only valid PDF output.
3. Check per-user quotas and total bytes before materializing inputs; confirm ownership/readiness/expiry on every read. Recheck callback identity and completed result association. A signature/extension match is not antivirus approval.
4. Preserve no-network/non-root/read-only sandbox, no application secrets, dropped privileges and bounded CPU/memory/PIDs/time/temp/output. Inspect heartbeat during long processing and crash/timeout cleanup.
5. Use disposable S3Mock/PostgreSQL and affected file/PDF/workflow tests; actual container isolation needs Compose runtime evidence. Add hostile/large/active input and missing/expired/storage-failure cases only when relevant.
6. Qualify production IAM/lifecycle/malware/backup separately in approved staging. Report exact source, bounds, evidence and remaining threat assumptions; do not put customer bytes or credentials in reports.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

# DSP-004 — Telegram upload admission

Date: 2026-10-01. Canonical repository: n923760-rgb/digital-services-platform.
Verified baseline main: 635b979d136cb5516154f9409b87e1eb802ad3de; no open PRs at task start.
Authority: owner explicitly authorized continued repairs and merging; Telegram is the customer product. Central reference previously reviewed at 641e4f9e45da109257ba1f38752b94604c2e4531; local AGENTS.md and dsp-file-security skill applied.
Capabilities: repository API and external GitHub Actions only. Local CLI/runtime/browser NOT RUN. No deployment, secret changes or paid-service activation.

## Diagnosis

FACT at baseline: the Telegram handler downloaded/stored a document before attach_pdf checked active workflow/file count. Filling a workflow then sending another document could create an unattached READY object with normal retention. Simultaneous uploads could both incur network/storage before one was rejected. Cancellation and replacement during download could attach input to a different workflow. No per-customer retained-input byte guard existed.

## Bounded repair

- Before download, check enabled PDF workflow, registry file count (up to ten), per-file size, 40 MiB workflow input total and configurable MAX_USER_UPLOAD_BYTES (100 MiB default). Retained cancelled/submitted/pending/failed INPUT metadata counts toward the customer budget.
- Hold a PostgreSQL session advisory lock per customer through admission/download/storage/attach. Competing uploads fail before download; no transaction spans those network operations. A process/session disconnect releases the lock. Existing deduplication runs before download.
- Bound actual downloaded bytes to the smallest remaining budget, rather than trusting declared size.
- Bind attachment to the original workflow ID. Attachment and extending short-lived intent retention to normal retention commit together. Existing direct callers retain their original API behavior.
- An upload intent expires in one hour until attachment succeeds. Rejected attachments attempt immediate deletion. File row locking plus a fresh reference check prevent this cleanup from deleting attached/order-owned input. A failed deletion leaves expired metadata for hourly retry; crashed storage I/O remains visible through short-lived metadata.
- No schema migration, wallet change, provider integration, feature activation or new dependency.

## Review and validation

Reviewed complete source changes: config.py, files.py, telegram_workflow.py, new telegram_uploads.py, bot pdf_workflow.py, .env.example, docs/FILES.md, this report/roadmap and new test_telegram_upload_admission.py.
Added 11 PostgreSQL-backed tests with fake Telegram/object storage: full workflow no download, competing last slot, cancellation/replacement, duplicate update, actual-stream cap, customer retention quota, workflow total, lock release/isolation, short intent/deletion retry, successful retention/reference safety, invalid size/disabled service.
At report creation: local Ruff/migrations/pytest/web/Compose NOT RUN; external CI pending. The associated PR records exact head, run URL, test totals, full-job conclusions and actual merge result when available. Do not infer PASS from this prepared report or previous PRs.

## Limits and next task

This closes only the bounded bot admission path after exact-source CI qualification. DSP-005 internal processor aggregate memory/materialization is separate. This does not establish account/rate abuse protection, malware screening, actual Telegram provider delivery or production storage/recovery safety.
Metadata-based quota is not a physical-byte guarantee when expired objects await provider cleanup. Hourly cleanup scans at most 100 records and can be delayed by backlog or storage failures. Production lifecycle is required for storage writes that finish after cleanup; output bytes are outside this input quota. Existing expired/abandoned historical objects retain their existing cleanup schedule.
Next: DSP-005 independent diagnosis; actual Telegram staging remains UNKNOWN until an authorized disposable bot/environment is available. Keep launch flags off.

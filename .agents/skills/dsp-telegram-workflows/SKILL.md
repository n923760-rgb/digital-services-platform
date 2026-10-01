---
name: dsp-telegram-workflows
description: Review private Telegram intake, PDF quote consent, callbacks, persistence, delivery and file retrieval.
---

# dsp-telegram-workflows

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Read apps/telegram_bot/, telegram_workflow.py, custom_requests.py, customer_files.py, orders.py and delivery.py. Trace customer identity from callback.from_user rather than the bot's message sender.
2. Enumerate enabled/disabled features and actual supported input types. Check handler precedence, draft/workflow ownership, per-message deduplication, concurrent uploads, resume/cancel, limits and safe errors.
3. Audit the exact offer a confirmation button represents: quote identity/revision, price, ordered file IDs and expiry. Diagnose DSP-001 with quote A -> changed inputs/price -> quote B -> A callback. Old offers must not reserve/charge under a new offer.
4. Verify concurrent/replayed confirmation returns one order and reservation; valid new confirmation remains usable. Read affected tests/test_telegram_workflow.py and tests/test_telegram_catalog_callback.py.
5. For delivery distinguish send acceptance from durable receipt commit. Preserve bounded retries/stale recovery and idempotent capture; Telegram can duplicate sends across a crash window. Never promise exactly-once sending.
6. Test actual Telegram journeys only in an approved staging bot, without exposing its token. API fixtures are not real-send evidence. Record NOT RUN if unavailable; report customer messaging/notification gaps honestly.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

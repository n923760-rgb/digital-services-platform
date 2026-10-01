---
name: dsp-financial-safety
description: Review or diagnose wallet, order, payment and settlement invariants in this platform.
---

# dsp-financial-safety

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Trace input -> order/payment owner -> wallet row lock -> immutable ledger -> job/delivery -> external receipt. Read ledger.py, orders.py, payments.py, jobs.py and delivery.py, and the financial migrations/contracts.
2. Check integer halalas, ownership, request/event idempotency keys, amount/SAR/provider matching, lock order, transaction rollback, reservation/settlement uniqueness and stale-attempt fencing. Distinguish release of held balance from an external provider refund.
3. Use a disposable migrated PostgreSQL database. Select meaningful regressions from test_financial_integration.py, test_job_integration.py, test_payments.py and test_pdf_merge_slice.py. Exercise concurrent same/different requests, insufficient funds, forged/replayed events, failure/recovery and no capture before receipt.
4. For quote/confirmation changes, coordinate with dsp-telegram-workflows; never accept a button that refers to a different offer. For a payment adapter use the owner-selected provider's current specification; test HMAC fixtures are not live integration.
5. Report exact source, causal path, actual test evidence, unresolved reconciliation/crash windows and the next bounded task. Without PostgreSQL execution mark proof NOT RUN; static inference does not close financial qualification.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

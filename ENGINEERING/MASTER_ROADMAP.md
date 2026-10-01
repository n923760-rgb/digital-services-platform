# Master Engineering Roadmap

Status: Telegram bot product — internal foundation, production qualification incomplete.
Owner confirmed 2026-10-01: Telegram is the customer interface; existing web is operations/admin tooling.
Latest recorded application source: d2937cb622349ceb590e22b1e8b22a29e3241481. Historical attribution only; retrieve live main every session.
[Baseline](REPORTS/2026-10-01-MASTER_BASELINE.md) · [Original CI blocker](REPORTS/2026-10-01-CI_QUALIFICATION.md) · [Qualified repairs](REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md) · [Authority](../AGENTS.md)

## 1. Current Verified State

FACT: bot-facing service foundation, integer SAR wallet, durable jobs/delivery, versioned PDF quote confirmation, completed-file retrieval and text service review intake.
FACT: SQLAlchemy asyncio dependency correction and quote revision correction merged as separate PRs #24/#25 after Python/web/Compose CI PASS; latest repair suite reports 71 tests passed.
FACT: governance/reference/six local skills prepared in PR #23 under explicit owner merge authority; do not equate documentation with runtime certification.
UNKNOWN: deployed instance, actual Telegram provider sends, production payment/storage/recovery and operator-browser evidence.
Paid orders and new service activation remain off by default.

## 2. Architecture

Telegram private chat -> aiogram -> platform_core -> PostgreSQL/S3.
ARQ/Redis dispatch durable PostgreSQL jobs -> no-network PDF sandbox -> result -> delivery_outbox -> receipt-based capture.
Web/FastAPI support authenticated internal operations; no new customer ordering website is in scope.
Domain source ownership remains independent of adapters. Digital Store remains a separate product.

## 3. Closed Historical Work

Baseline PRs #1–22: ledger/orders, durable jobs/delivery, PDF isolation, admin security, backup smoke, registry and custom-text review.
DSP-014: PR #24, SQLAlchemy asyncio extra, clean install/migrations/61-test suite/Compose qualified. Dependency locking remains a separate open gap.
DSP-001: PR #25, versioned offer callbacks and migration 0013, stale-price/input, ownership, payload/legacy, replay/concurrency regressions; 71 tests passed and Compose/web PASS.
[Detailed exact-source evidence](REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md). Source changes invalidate affected historical evidence.

## 4. Current Findings

DSP-001 and DSP-014 closed for source/CI correction; real Telegram staging remains unqualified.
Open: payment integration (002), production storage/recovery (003), upload admission/quota (004), aggregate byte/materialization (005), trusted proxy/login throttling (006/007), sandbox long-job liveness (008), truthful intake/customer notifications (009), locking/supply chain (010), admin mobile/accessibility (011), branch protection (012), docs/pagination/retention/scaling (013).
Root engineering authority and canonical planning address part of DSP-012; GitHub protection/settings remain unchanged.
All remaining findings retain baseline FACT/INFERENCE/UNKNOWN classifications until diagnosed.

## 5. Release Blocker Map

| Gate | Required proof |
| --- | --- |
| Bot customer journey | private identity, supported input, quote/confirm/resume/cancel/status/delivery E2E |
| Paid flow | owner-selected provider, verified events, refund/dispute/reconciliation |
| Files | quotas/admission, production S3/IAM, malware/safety and ownership/expiry |
| Recovery | independent encrypted DB + object restore, financial reconciliation |
| Operations | trusted proxy/throttle, long-job liveness, monitoring and rollback |
| Operator UI | Arabic/mobile/accessibility and session/write journeys |
| Release identity | exact main source and artifact/deployment hashes; owner release decision |

## 6. Qualification Gaps

Local commands NOT RUN in this API-only session. External CI executes disposable PostgreSQL/Compose checks.
Real Telegram bot/token, live/sandbox payment account and production storage credentials not exercised.
No live launch configuration, traffic/business profitability or approved full business specification was supplied.
No browser/actual customer-message, production recovery or load evidence claimed.

## 7. Ordered Engineering Gates

1. Finish qualified merge of project authority/reference/skills and Telegram direction (PR #23).
2. DSP-004 admission/quota diagnosis before public uploads; DSP-005 aggregate-byte limits as its own bounded task.
3. DSP-009 truthful bot intake text and explicit supported-input guidance; notification/status requirements for chosen service scope.
4. DSP-006/007/008 independent proxy/Redis/sandbox-liveness diagnoses.
5. Select and integrate payment provider with authenticated checkout/events and reconciliation.
6. Qualify production storage/privacy/recovery and dependency/artifact reproducibility.
7. Actual Telegram staging, operational reliability and operator-browser evidence; freeze candidate and owner launch decision.
One coherent issue per branch/PR. No unrelated changes or automatic activation.

## 8. Runtime Gates

Bot: menus, supported media/text, customer callback identity, stale quote rejection, concurrency/replay, cancel/resume, actual delivery/file retrieval and send/crash duplicate window without duplicate ledger capture.
Workers/storage: Redis loss, stale processing, invalid/active/large PDFs, slow processing, quota exhaustion, upload interruption, expiry and missing outputs.
Payments/recovery: signed/forged/replayed/out-of-order events and post-restore financial/object consistency.
Admin: OWNER/OPERATOR, Origin/cookies/expiry, proxy clients, triage/service revisions, keyboard/RTL/mobile/loading/error states.
Current source/CI proof does not replace actual Telegram or production-like evidence.

## 9. Release Gates

Freeze one current main source and actual artifact/deployment contents after selected launch blockers close.
Require exact-source CI plus Telegram/provider/storage/operations E2E and tested rollback/recovery.
Merge authority received for these engineering changes does not authorize deployment, DNS, production migrations or paid-service activation.

## 10. Owner Decisions

Confirmed: Telegram bot is the customer product; merge qualified engineering changes.
Open: brand/domain, launch services/prices/SLA, provider/refunds/disputes, privacy/retention, lab/staging/production budget and storage, GitHub protection settings.
Continue already authorized ordinary work without redundant approval prompts; protected operations need scope for that operation.

## 11. Deferred Work

Subject to product decisions: broader AI/manual/template execution, richer media intake, store link and deeper analytics.
A customer website is not in current scope. Notification and operational controls required for launch cannot be deferred merely by labelling them future work.

## 12. Exact Immediate Next Round

After PR #23 qualification/merge, diagnose DSP-004 upload admission:
a workflow at its file limit -> another document -> verify no unnecessary download/storage; race two last-slot uploads and cancellation; inspect unreferenced-file cleanup and per-user limits.
Use a disposable migrated database/storage and one bounded remediation task.
Keep paid orders/uploads gated until provider, safety and production qualification requirements are met.

# Master Engineering Roadmap

Status: Telegram bot product — internal foundation, production qualification incomplete.
Owner confirmed 2026-10-01: Telegram is the customer interface; existing web is operations/admin tooling.
Task baseline: 08087d7f2798aad6b7d7ffe02ebc0d9fbb31f6d9. Historical attribution only; retrieve live main every session.
[Baseline](REPORTS/2026-10-01-MASTER_BASELINE.md) · [Original CI blocker](REPORTS/2026-10-01-CI_QUALIFICATION.md) · [Qualified repairs](REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md) · [Authority](../AGENTS.md)

## 1. Current Verified State

FACT: bot-facing service foundation, integer SAR wallet, durable jobs/delivery, versioned PDF quote confirmation, completed-file retrieval and text service review intake.
FACT: SQLAlchemy asyncio dependency correction and quote revision correction merged as separate PRs #24/#25 after Python/web/Compose CI PASS; latest repair suite reports 71 tests passed.
FACT: governance/reference/six local skills merged in PR #23 after Python/web/Compose CI PASS; documentation does not establish runtime certification.
FACT: DSP-004 merged in PR #26; pre-download guards, per-customer serialization, original-workflow attachment and short intents qualified by CI run 36896881244 (82 tests, Python/web/Compose PASS). No production claim. [Task report](REPORTS/2026-10-01-UPLOAD_ADMISSION.md).
FACT: DSP-005 merged in PR #27 after run 36902438700: 90 tests and Python/web/Compose PASS. Processor acquisition now checks aggregate/per-file bytes before storage reads; RSS/load remains unqualified.
FACT: PR #28 merged after run 36904542220 (95 tests and Python/web/Compose PASS): truthful intake, unsupported-media guidance and sender-owned status reads. Automatic triage notifications remain absent.
FACT: DSP-008 sandbox progress heartbeat merged in PR #29 after run 36905174492: 97 tests and Python/web/Compose PASS. Full-duration hostile PDF/load evidence remains unqualified.
FACT: DSP-006 merged in PR #30; run 36906472920 passed Python/web/Compose, 97 tests and actual two-source proxy/direct forged-header checks.
FACT: DSP-007 merged in PR #31 after run 36907076671: 104 tests, actual Redis concurrency/expiry and Python/web/Compose/two-source proxy checks PASS.
FACT: DSP-010 merged PR #32 after exact-head run 36909223236: hashed Python/npm locks, immutable image/action inputs, clean installs, 104 tests and Python/web/Compose PASS. [Dependencies](../docs/DEPENDENCIES.md).
FACT: DSP-011 source correction merged PR #33 after run 36910685996: 104 tests, Python/web/Compose and Chromium mobile/RTL/session journeys PASS. Browser uses built Next.js + intercepted synthetic API; live backend/browser and Telegram remain unqualified.
FACT: DSP-013 review pagination merged PR #34 after run 36912070468: 105 tests, migration 0014, Python/web/Compose and Chromium page/session checks PASS; mutable queue and production-load limits remain documented.
FACT: Cleanup isolation merged PR #35 after run 36913178393: 108 tests and Python/web/Compose/Chromium PASS; storage failure/retry/live-file/sanitized-log regressions qualified.
UNKNOWN: deployed instance, actual Telegram provider sends and production payment/storage/recovery.
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

DSP-001, DSP-004, DSP-005 and DSP-014 closed for source/CI correction; real Telegram staging remains unqualified.
Scoped source/CI corrections qualified: proxy/throttle (006/007), sandbox heartbeat (008), truthful intake/customer status (part of 009), dependency inputs (part of 010), admin mobile/session interaction (part of 011).
Open: payment integration (002), production storage/recovery (003), actual Telegram/automatic notifications (009), release artifact/supply chain qualification (010), live admin/session/accessibility evidence (011), branch protection (012), review pagination/retention/scaling (013).
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
Chromium browser evidence covers built Next.js with intercepted synthetic API only. No actual customer-message, production recovery or load evidence claimed.

## 7. Ordered Engineering Gates

1. Project authority/reference/skills and Telegram direction merged (PR #23).
2. DSP-004 and DSP-005 merged/CI qualified; [task report](REPORTS/2026-10-01-PROCESSOR_INPUT_BUDGET.md).
3. DSP-009 intake/status qualified in PR #28; automatic notifications remain a separate capability and no SLA is claimed.
4. DSP-008/DSP-006/DSP-007 scoped source/CI corrections qualified.
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

Qualify read-only DSP-010 advisory audit against locked runtime/npm inputs; [report](REPORTS/2026-10-01-DEPENDENCY_AUDIT.md). Then consolidate the review/evidence register and remaining launch prerequisites.
Actual Telegram staging still requires an authorized disposable bot/environment and provider credentials supplied through its secret store. Do not request tokens in chat or claim actual Telegram sends from mocked adapter tests.
Keep paid orders/uploads gated until provider, safety and production qualification requirements are met.

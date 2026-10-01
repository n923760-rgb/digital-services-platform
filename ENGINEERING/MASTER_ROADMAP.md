# Master Engineering Roadmap

Status: INITIAL ADOPTION — qualification incomplete.
Last recorded baseline: 2026-10-01, source b90dccda7175b7f77dfe8cba4b3bc573d283a299.
This SHA is historical evidence; reverify live main for every new task.
[Full baseline](REPORTS/2026-10-01-MASTER_BASELINE.md) · [Evidence](EVIDENCE/2026-10-01-BASELINE.md) · [Authority](../AGENTS.md)

## 1. Current Verified State

FACT at baseline: internal foundation 0.1.0; only PDF merge processor; Arabic admin and Telegram text review intake; wallet/payment accounting kernel.
FACT: main unprotected and no rulesets returned at baseline; no released artifact; latest exact-source historical CI PASS (python/web/compose).
UNKNOWN: production deployment, live-provider operation, runtime/mobile/recovery/load evidence.
Paid orders and new service activation remain off by default; do not treat this roadmap or governance PR as launch approval.

## 2. Architecture

Modular monolith: adapter apps -> platform_core -> PostgreSQL/S3; Redis/ARQ dispatch -> bounded no-network PDF sandbox -> delivery outbox -> receipt-based capture.
PostgreSQL owns money/orders/jobs/workflows/admin authorization. Store product stays independent.

## 3. Closed Historical Work

PRs #1–22 merged by baseline, most recently #22 custom-request triage. Features include ledger/idempotent orders, durable jobs/delivery, PDF isolation, admin auth, backup smoke, registry and text review.
Historical merges and CI are evidence for their actual source, not certification of production readiness.

## 4. Current Findings

Open DSP-001–DSP-013 in baseline section N; later DSP-014 clean-install failure in the [CI addendum](REPORTS/2026-10-01-CI_QUALIFICATION.md). No finding was fixed by the audit.
First build blocker: DSP-014 missing SQLAlchemy asyncio/greenlet dependency, observed in new PR CI. Highest consent design gap: DSP-001 stale quote button lacks quote version.
Other code diagnoses: upload admission/quota (004), aggregate size/memory (005), proxy/throttle (006/007), sandbox liveness (008), mobile layout (011).
Product/qualification gaps: payments (002), storage/recovery (003), intake messaging/notifications (009), reproducibility (010), governance (012), docs/scaling (013).
Use separate bounded implementation PRs; don't combine this ledger into one repair branch.

## 5. Release Blocker Map

| Gate | Blocking evidence |
| --- | --- |
| Clean install/build | DSP-014 required asyncio dependency and migrated tests/Compose |
| Customer consent | DSP-001 old quote/input buttons rejected deterministically |
| Paid flow | real verified provider, refunds/disputes/reconciliation and consent E2E |
| Customer files | production S3/IAM, safety controls, quotas and ownership/expiry proof |
| Financial recovery | DB + object restore, event reconciliation and tested rollback |
| Operations | trusted proxy/throttle, job/delivery failure and liveness evidence |
| Product surfaces | Arabic/mobile/browser and real Telegram journeys |
| Release identity | exact source, reproducible artifact/deployment hashes, owner decision |

## 6. Qualification Gaps

Local checks NOT RUN by API controller. No qualified CLI/Docker/PostgreSQL/browser lab in this session.
No provider/staging/production credentials exercised. Full business specification and profitability inputs not supplied.
Static source review and historical CI must remain distinguishable from observed runtime.

## 7. Ordered Engineering Gates

1. Governance adoption PR: AGENTS/reference/resource map/roadmap/report/evidence/local skills. Prepared under owner request; merge remains owner-protected.
2. Qualify disposable Linux lab and correct DSP-014 in a separate dependency-only task; prove clean-install Python/migration/Compose checks.
3. DSP-001 deterministic diagnosis, then one bounded consent correction with regression.
4. DSP-004–008 separate input/resource/proxy/Redis/liveness diagnoses and remedies.
5. Choose payment provider and implement its authenticated boundaries as coherent tasks.
6. Qualify production storage, safety/privacy and off-host recovery.
7. Surface E2E, reliability/load tests, release candidate and owner decision.

Governance files do not close any runtime or settings gate automatically.

## 8. Runtime Gates

Telegram: callback identity, old/new quotes, file ownership, resume/cancel, double submit, restart, actual send, duplicate send crash window and no duplicate capture.
Browser: OWNER/OPERATOR permissions, Origin/cookies, two clients behind Caddy, login/expiry/logout, triage/service changes, narrow screens, zoom/keyboard/loading/error states.
Workers/storage: Redis loss, stale recovery, large/invalid/active PDFs, slow jobs, quota exhaustion, interrupted upload, cleanup and missing/expired output.
Payments/recovery: sandbox verified/forged/replayed/out-of-order callbacks and restored ledger/object consistency.
Results currently NOT RUN/UNKNOWN beyond historical CI described in baseline.

## 9. Release Gates

Freeze one exact main source and artifact/deployment contents after affected fixes.
Require exact-source CI, staging E2E, security/privacy/recovery and rollback evidence.
A later source/dependency change invalidates affected evidence.
No merge/release/activation/deploy is authorized by green CI alone.

## 10. Owner Decisions

Brand/domain, launch services and pricing, response SLA, provider/refund/dispute rules, privacy/retention, lab/staging budget, production storage, and GitHub protection.
Protected operations require explicit owner scope; continue ordinary previously authorized documentation work without redundant approval prompts.

## 11. Deferred Post-Release Work

Subject to later product decision: broader AI/manual/template services, customer web ordering, store link, richer input types and deeper analytics.
Customer notices and operational controls required for chosen launch scope cannot simply be deferred because they are listed here.

## 12. Exact Immediate Next Round

Complete/review governance adoption PR and inspect its exact-source CI. Do not merge automatically.
New qualification on documentation head 180324216ca932b27e3fcdc293c086e7680671ab: web PASS; Python/Compose FAIL due to missing greenlet with SQLAlchemy 2.1.1. See [CI addendum](REPORTS/2026-10-01-CI_QUALIFICATION.md). Historical baseline success remains unchanged evidence.
First qualify test lab and diagnose/remediate DSP-014 in a separate bounded dependency task; this documentation PR does not fix it.
Then diagnose DSP-001 using two displayed quotes for one workflow:
quote A -> mutate price/inputs -> quote B -> activate A callback -> verify rejection without order/reservation.
New valid quote confirms once; replay remains idempotent; independent customers remain isolated.
Implementation is a separate bounded task, with no paid-operation enablement.

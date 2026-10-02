# Master Engineering Roadmap

Status: direct local text-summary slice; old PDF/Stars source/history retained, paid runtime qualification incomplete.
Owner reset: 2026-10-02. Saudi market, Arabic first/RTL, Modular Monolith; Telegram is the first channel, not the architecture.
Historical direct-slice base: 0c402848a31d09f699675a76f6dcce84ed8babff. Retrieve live main every session.
[Authority](../AGENTS.md) · [Scope decision](../docs/SCOPE.md) · [Reset report](REPORTS/2026-10-02-SOLO_SCOPE_RESET.md) · [Baseline](REPORTS/2026-10-01-MASTER_BASELINE.md) · [Historical review](REPORTS/2026-10-01-POST_REPAIR_REVIEW.md) · [Historical evidence](EVIDENCE/2026-10-01-QUALIFIED_CHANGES.md)

## 1. Current Verified State

FACT: the default entrypoint now serves direct text summarization through a small local Summarizer interface. The legacy PROCESSORS registry remains merge-pdf only; direct summaries create no jobs row. The local extractive algorithm is not generative AI. [Contract](../docs/DIRECT-SUMMARY.md).
FACT: existing SAR wallet uses integer halalas and reservation/capture/release history. Native XTR Stars invoices/charges are separate and never convert into SAR.
FACT: default runtime is PostgreSQL/migrator/FastAPI-health plus an opt-in direct-summary bot. Redis/ARQ/PDF/S3/Next.js stay in docker-compose.legacy.yml. Migration 0017 preserves existing history and adds input/result expiry and immutable invoice text hashes. Final source/CI proof is in the direct-slice PR body.
FACT: Stars engineering integration merged in [PR #40](https://github.com/n923760-rgb/digital-services-platform/pull/40). Its qualified source 2102f41a345bf9d5e2aad6868bee24f5b88095d2, tree 2049666cddb8b5b2d05e5734dc90c8c2c8c01490 matches reset starting main 58b4721e23e4cddabadb542a79ceffc5e775aa16. Exact-source Foundation [36942691617](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36942691617) passed 136 tests/python/web/Compose; advisory [36942691648](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36942691648) reported Python 57/0 skips/0 known vulnerabilities and npm production 0. This is historical source/CI evidence, not live payments or a summarization V0.
OWNER DESCRIPTION: completed V0 with text summary, simple TOP_UP/CHARGE/REFUND, direct execution and create_all. This differs from the inspected source; it is not represented as verified completion here.
UNKNOWN: measured growth trigger, external AI provider choice, actual bot/payment/deployment and production recovery evidence. The implementation follows the owner's described text-summary/direct scope; no separate trigger answer is invented.
Paid checkout/orders and service activation remain off by default.

## 2. Architecture

Target small baseline: Python/FastAPI + aiogram + PostgreSQL as a Modular Monolith. Channels call application/domain functions in platform_core. A small service uses direct execution by default; additions require a confirmed actual trigger.
Default: Telegram -> summary application/PostgreSQL -> direct Summarizer -> text result/receipt. Legacy: Telegram/domain/PostgreSQL -> ARQ/Redis/PDF/S3, with FastAPI/Next.js operations.
Do not confuse the current dependency graph with the target minimum. Existing infrastructure is not proof of demand. The [architecture contract](../docs/ARCHITECTURE.md) separates active scope and historical foundation acceptance.
The Digital Store remains an independent product.

## 3. Closed Historical Work

Historical PRs #1–22 established financial/job/delivery/PDF/admin/backup/registry foundations. PR #23 adopted the central reference, root authority and six local skills. Qualified repairs/additions in PRs #24–39 are attributed in the [repair report](REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md), [review checkpoint](REPORTS/2026-10-01-POST_REPAIR_REVIEW.md) and linked task reports.
[Cleanup fairness](REPORTS/2026-10-01-CLEANUP_RETRY_FAIRNESS.md) is tracked in PR #39; [native Stars](REPORTS/2026-10-01-TELEGRAM_STARS.md) in PR #40 and its [contract](../docs/TELEGRAM-STARS.md).
These changes are existing history, not a mandate to expand the reset scope or evidence of actual production demand.

## 4. Current Findings

FACT: active guidance previously required workers for work that takes time and used the Telegram bot as product identity; this conflicts with the new owner-directed scope. This reset corrects instructions/contracts without claiming runtime simplification.
FACT: the starting source lacked the described summarizer. This continuation implements its minimal local/direct form and separates default/legacy startup, preserving financial/migration history.
UNKNOWN: a current trigger for additional queues, UI, services or other complexity. None was supplied. Never infer confirmation from elapsed time.
Existing live provider, storage, recovery and operator evidence gaps stay attributable, but apply to the actual selected service; optional features are not defects merely because they are missing.

## 5. Release Blocker Map

| Gate | Required proof for the selected slice |
| --- | --- |
| Scope | One selected service, smallest implementation and actual trigger answer before additions |
| Domain/finance | Thin handlers; one atomic transaction per financial transition; idempotency and preserved history |
| Errors/providers | Classified, sanitized logged failures with a stated policy; external calls behind simple adapters |
| Schema | All changes via Alembic now that it exists; safe data-preserving rollback |
| Customer journey | Actual Arabic/private-input/consent/result/failure path for the selected channel/service |
| Paid flow, if launched | Real Stars payment/refund/support and uncertain-outcome reconciliation |
| Files, if selected service uses them | Ownership/expiry, bounded input processing, actual storage and document safety |
| Recovery/operations | Appropriate DB recovery and actual dependencies, secret handling, monitoring and rollback |
| Release identity | Exact source/deployment identity and scoped owner launch authority |

A queue, dashboard, S3 service or a new channel is not automatically required by this table.

## 6. Qualification Gaps

Execution capabilities: repository API and existing external CI. Local shell/runtime commands NOT RUN in this reset.
Historical Chromium evidence uses built Next.js with intercepted synthetic API. Provider calls in payment tests are fake; PostgreSQL/Compose runs use disposable data.
The direct local slice was qualified and merged in [PR #42](https://github.com/n923760-rgb/digital-services-platform/pull/42): exact source c486848824cbacda33fb9662bf92b5e1a38a3ac8, tree c69d2a4199b89d3cd08fbfb29d718c818d0556b9 equals merged main 82cbcd1d46808ca4b62e7396653dc4d8ea8c9cab. [Foundation push 36965910649](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36965910649) passed 154 tests, Ruff, migration 0017, legacy regressions and the isolated minimal deployment; [advisory 36965910629](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36965910629) passed. Provider/Telegram calls are synthetic. External AI and real Telegram/Stars journeys remain NOT RUN.
Actual Telegram/payment/storage and deployment remain unqualified. These facts do not authorize purchasing infrastructure or enabling paid flags.

## 7. Ordered Engineering Gates

1. Apply the explicitly requested scope/permanent rules and reconcile source facts in this reset.
2. The continuation follows the text-summary/direct baseline; no queue expansion trigger was supplied. Resolve an external provider choice only if requested.
3. For the chosen service, propose the smallest direct slice and warn about any premature stage jump before implementation.
4. Implement one bounded confirmed change; preserve finance, data and already-adopted migrations.
5. Select the smallest meaningful checks for changed behavior; use existing affected CI, not speculative new test/tool frameworks.
6. Qualify actual chosen customer/provider journeys and recovery before an authorized launch.

This is conditional work, not an automatic upgrade sequence. Before any new feature/complexity ask: **هل المحفّز صار موجود فعلاً؟**

## 8. Runtime Gates

Select cases from the actual service: private identity, valid/invalid input, duplicate/concurrent financial requests, timeout/provider failure, explicit rejection and truthful result reporting.
If the PDF service is retained, existing isolation, file ownership/expiry, send/restart and worker behavior remain relevant until a qualified replacement exists.
For direct text summary, qualify input/output limits, quote/payment replay, direct provider calls outside locks, failure/refund, cached result/actual delivery and minimal startup. An external AI provider and summary-quality benchmark remain unqualified.
Select HTTP/admin/browser/Redis/storage cases only when they are affected or remain dependencies. Historical tests do not prove a new service/runtime.

## 9. Release Gates

Bind the selected release to one exact main source and actual deployment contents. Qualify its real channel/provider/recovery behavior and rollback.
Engineering merge authority does not authorize deployment, production migrations, DNS, real billing, paid activation or destructive financial/data changes.
Safety/correctness rules are immediate; growth infrastructure is conditional.

## 10. Owner Decisions

Confirmed: Saudi/Arabic-first product, one developer, Modular Monolith, Telegram as first channel, thin handlers, atomic finance, explicit classified/logged error policies, external-provider abstractions and migration-only schema changes once Alembic exists. Before new features/complexity ask whether the real trigger exists; choose the simplest viable version and flag stage jumps.
Existing payment decision remains Telegram Stars directly per order until explicitly revised. Qualified engineering merge authority persists.
Continuation scope: the described text-summary/direct baseline. Local extractive summarization is the implemented default; the optional local/external-provider question remains open. A growth trigger was not provided; do not invent one.
Other decisions only when needed: selected provider/model, Stars prices/final terms/support and authorized disposable environment. Never request tokens in chat.

## 11. Deferred Work

Additional services, queues/worker expansion, Redis/ARQ adoption for new slices, Next.js/dashboard expansion, microservices, generic frameworks, richer media, notifications, store integration and analytics require an actual confirmed trigger or explicitly requested scope with a confirmed current need.
Retain existing features/history as facts while assessing simplification. Do not select speculative roadmap tasks as the next implementation merely because they were previously listed.
Production controls apply to the selected live flow and must not be replaced by optional feature work.

## 12. Exact Immediate Next Round

PR #42 source qualification is complete; [preparation report](REPORTS/2026-10-02-DIRECT_SUMMARY.md) and its PR body retain the evidence. The continuation found that startup ran interrupted-order/refund recovery before Telegram authentication. Correct that bounded ordering defect, prove failed authentication leaves the database untouched, and qualify the exact repair source before merge. [Startup repair report](REPORTS/2026-10-02-SUMMARY_STARTUP_AUTH.md).
Default startup needs no worker/Redis/S3/Next.js; legacy history and configuration stay intact. No price, retention/privacy policy, external AI provider or paid activation is selected by implementation.
After source qualification, remaining dependent work is owner-set prices/final terms/support and an authorized disposable bot for actual invoice/receipt/result/refund, plus appropriate DB backup/recovery. Do not add queues/UI/services or provider frameworks without asking for their actual trigger. Never request secret values in chat.

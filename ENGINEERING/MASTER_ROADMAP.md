# Master Engineering Roadmap

Status: scope reset for one developer; existing PDF/Stars source retained, target service/execution decision pending.
Owner reset: 2026-10-02. Saudi market, Arabic first/RTL, Modular Monolith; Telegram is the first channel, not the architecture.
Historical reset inspection source: 58b4721e23e4cddabadb542a79ceffc5e775aa16. Retrieve live main every session.
[Authority](../AGENTS.md) · [Scope decision](../docs/SCOPE.md) · [Reset report](REPORTS/2026-10-02-SOLO_SCOPE_RESET.md) · [Baseline](REPORTS/2026-10-01-MASTER_BASELINE.md) · [Historical review](REPORTS/2026-10-01-POST_REPAIR_REVIEW.md) · [Historical evidence](EVIDENCE/2026-10-01-QUALIFIED_CHANGES.md)

## 1. Current Verified State

FACT: source contains one registered tool processor, merge-pdf; Telegram text submission is service-review intake, not a working summarizer. No AI summarization provider/processor is registered.
FACT: existing SAR wallet uses integer halalas and reservation/capture/release history. Native XTR Stars invoices/charges are separate and never convert into SAR.
FACT: current execution uses durable PostgreSQL jobs/delivery with Redis/ARQ, an isolated PDF parser, S3 adapter and an existing Next.js operations UI. Alembic is already adopted through 0016.
FACT: Stars engineering integration merged in [PR #40](https://github.com/n923760-rgb/digital-services-platform/pull/40). Its qualified source 2102f41a345bf9d5e2aad6868bee24f5b88095d2, tree 2049666cddb8b5b2d05e5734dc90c8c2c8c01490 matches reset starting main 58b4721e23e4cddabadb542a79ceffc5e775aa16. Exact-source Foundation [36942691617](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36942691617) passed 136 tests/python/web/Compose; advisory [36942691648](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36942691648) reported Python 57/0 skips/0 known vulnerabilities and npm production 0. This is historical source/CI evidence, not live payments or a summarization V0.
OWNER DESCRIPTION: completed V0 with text summary, simple TOP_UP/CHARGE/REFUND, direct execution and create_all. This differs from the inspected source; it is not represented as verified completion here.
UNKNOWN: selected service for the reset, actual demand/latency/concurrency trigger, live bot/deployment and production provider/recovery evidence.
Paid checkout/orders and service activation remain off by default.

## 2. Architecture

Target small baseline: Python/FastAPI + aiogram + PostgreSQL as a Modular Monolith. Channels call application/domain functions in platform_core. A small service uses direct execution by default; additions require a confirmed actual trigger.
Current source: Telegram -> domain/PostgreSQL -> ARQ/Redis -> isolated PDF processing/S3 -> durable delivery; FastAPI/Next.js provide internal operations.
Do not confuse the current dependency graph with the target minimum. Existing infrastructure is not proof of demand. The [architecture contract](../docs/ARCHITECTURE.md) separates active scope and historical foundation acceptance.
The Digital Store remains an independent product.

## 3. Closed Historical Work

Historical PRs #1–22 established financial/job/delivery/PDF/admin/backup/registry foundations. PR #23 adopted the central reference, root authority and six local skills. Qualified repairs/additions in PRs #24–39 are attributed in the [repair report](REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md), [review checkpoint](REPORTS/2026-10-01-POST_REPAIR_REVIEW.md) and linked task reports.
[Cleanup fairness](REPORTS/2026-10-01-CLEANUP_RETRY_FAIRNESS.md) is tracked in PR #39; [native Stars](REPORTS/2026-10-01-TELEGRAM_STARS.md) in PR #40 and its [contract](../docs/TELEGRAM-STARS.md).
These changes are existing history, not a mandate to expand the reset scope or evidence of actual production demand.

## 4. Current Findings

FACT: active guidance previously required workers for work that takes time and used the Telegram bot as product identity; this conflicts with the new owner-directed scope. This reset corrects instructions/contracts without claiming runtime simplification.
FACT: the described summarization V0 is absent from source. Selecting/building it and replacing current execution are pending owner decisions.
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
No actual text-summary implementation, AI model choice/provider, direct service path or simplified deployment was qualified.
Actual Telegram/payment/storage and deployment remain unqualified. These facts do not authorize purchasing infrastructure or enabling paid flags.

## 7. Ordered Engineering Gates

1. Apply the explicitly requested scope/permanent rules and reconcile source facts in this reset.
2. Obtain the service choice and actual background-execution trigger answer already requested.
3. For the chosen service, propose the smallest direct slice and warn about any premature stage jump before implementation.
4. Implement one bounded confirmed change; preserve finance, data and already-adopted migrations.
5. Select the smallest meaningful checks for changed behavior; use existing affected CI, not speculative new test/tool frameworks.
6. Qualify actual chosen customer/provider journeys and recovery before an authorized launch.

This is conditional work, not an automatic upgrade sequence. Before any new feature/complexity ask: **هل المحفّز صار موجود فعلاً؟**

## 8. Runtime Gates

Select cases from the actual service: private identity, valid/invalid input, duplicate/concurrent financial requests, timeout/provider failure, explicit rejection and truthful result reporting.
If the PDF service is retained, existing isolation, file ownership/expiry, send/restart and worker behavior remain relevant until a qualified replacement exists.
If text summary is selected, qualify its input/output limits, AI adapter/failure behavior and direct execution; do not claim a processor exists before implementation.
Select HTTP/admin/browser/Redis/storage cases only when they are affected or remain dependencies. Historical tests do not prove a new service/runtime.

## 9. Release Gates

Bind the selected release to one exact main source and actual deployment contents. Qualify its real channel/provider/recovery behavior and rollback.
Engineering merge authority does not authorize deployment, production migrations, DNS, real billing, paid activation or destructive financial/data changes.
Safety/correctness rules are immediate; growth infrastructure is conditional.

## 10. Owner Decisions

Confirmed: Saudi/Arabic-first product, one developer, Modular Monolith, Telegram as first channel, thin handlers, atomic finance, explicit classified/logged error policies, external-provider abstractions and migration-only schema changes once Alembic exists. Before new features/complexity ask whether the real trigger exists; choose the simplest viable version and flag stage jumps.
Existing payment decision remains Telegram Stars directly per order until explicitly revised. Qualified engineering merge authority persists.
Pending questions: **text summary only or PDF merge only?** **Does an actual background-execution trigger exist, or should the selected path execute directly?**
Other decisions only when needed: selected provider/model, Stars prices/final terms/support and authorized disposable environment. Never request tokens in chat.

## 11. Deferred Work

Additional services, queues/worker expansion, Redis/ARQ adoption for new slices, Next.js/dashboard expansion, microservices, generic frameworks, richer media, notifications, store integration and analytics require an actual confirmed trigger or explicitly requested scope with a confirmed current need.
Retain existing features/history as facts while assessing simplification. Do not select speculative roadmap tasks as the next implementation merely because they were previously listed.
Production controls apply to the selected live flow and must not be replaced by optional feature work.

## 12. Exact Immediate Next Round

Complete the policy/source reconciliation round and its full diff/link/evidence review. Source runtime remains the existing gated PDF/Stars stack.
The service/execution questions are pending; continue independent authorized work but do not choose the service, add AI/provider dependencies or remove worker/admin/data components by assumption.
When the owner answers, verify live main, record the trigger answer and implement the smallest bounded selected slice. Keep Alembic/history and existing payment semantics unless explicitly changed. No automatic queue/dashboard expansion or launch.

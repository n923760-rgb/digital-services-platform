# Scope decision — one developer, actual triggers

Owner direction: 2026-10-02. This is a product/architecture contract, not another roadmap. Current tasks, decisions and evidence belong in [the canonical roadmap](../ENGINEERING/MASTER_ROADMAP.md).

## Decision

Saudi market, Arabic first/RTL, one developer. Keep a Modular Monolith: Telegram and HTTP invoke application functions in platform_core; PostgreSQL owns application and financial state. Telegram is the first channel and must not become the domain architecture.

Use the smallest service slice and direct execution by default. Before a new feature or complexity, ask **هل المحفّز صار موجود فعلاً؟** A useful trigger is an observed problem (for example repeated demand for a service, measured waiting time or overlapping requests), not a speculative growth story. Record the owner's answer and choose the smallest change that solves it. Warn explicitly when a request jumps a stage. No invented capacity threshold or automatic upgrade schedule.

A queue/worker, Redis/ARQ, Next.js, a full dashboard, microservices or a provider/plugin framework needs its own actual trigger or named owner request and confirmed current need. A simple provider function or interface is sufficient. Correctness, atomic finance, error handling, provider boundaries and migration discipline apply immediately; they are not deferred maturity features.

## Intended baseline versus verified source

| Area | Owner-described small baseline | Verified source before this reset |
| --- | --- | --- |
| Service | One text-summary service | Only merge-pdf is registered in PROCESSORS; text is review intake, not summarization |
| Execution | Direct application call | ARQ/Redis worker, durable jobs/delivery and isolated PDF parser |
| Wallet | TOP_UP/CHARGE/REFUND | Existing SAR ledger includes reservation/capture/release; separate XTR invoices/charges |
| Schema | create_all before Alembic | Alembic already adopted through 0016; all future changes must be migrations |
| Operations UI | Add only on demand | Existing Next.js admin and authenticated OWNER/OPERATOR operations |
| Payments | Existing owner selection must be reconciled | Telegram Stars directly per order, gated off; no Stars-to-SAR conversion |

The reported V0 completion is not source verification. Do not claim that text summarization, direct execution or a simplified wallet is already implemented here. Two decisions were requested: the one service to retain/build, and whether an actual background-execution trigger exists. No answer is inferred from elapsed time.

Existing source and financial/migration history stay attributable. Simplification is a bounded source change after those answers, not deletion of historical tables/ledgers or a second create_all bootstrap. Keep the prior Stars/direct-per-order decision until the owner explicitly changes it; do not fund an internal wallet with Stars.

## Permanent implementation rules

Handlers parse/authenticate input, call application services and present results. Business rules do not belong in the Telegram/API adapter.

Commit all related financial writes, state and idempotency in one database transaction. Provider calls occur outside database locks; commit verified outcomes atomically and keep uncertain results explicitly pending. A remote payment and PostgreSQL commit are not one shared transaction.

Every handled failure has a classification, sanitized log and defined policy. Expected invalid input is rejected clearly; temporary infrastructure/provider failures have bounded or explicit retry behavior; financial uncertainty stays unresolved until verified; unexpected faults are logged and surfaced rather than reported as success. Avoid raw customer content, secrets and duplicate logging at every layer.

External AI/storage/payment calls use a small adapter/callable. Avoid unnecessary registries/frameworks for one provider. Once Alembic exists, schema changes are migrations only; retain data/history during application rollback.

## Application of this decision

This reset changes engineering scope and removes automatic complexity from active guidance. It does not establish a new runtime, feature implementation or launch. Existing startup/CI still exercise the current PDF/Stars stack until a separately reviewed simplification changes it. Existing source qualification is historical proof for its exact source; it does not prove an unimplemented summarization service or a real payment.

Do not convert an existing deployment requirement into a growth requirement. Select future validation and launch prerequisites from the actual chosen service. Paid activation/deployment, production migrations and destructive operations still require their scoped authority.

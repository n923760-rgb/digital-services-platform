# Architecture contract — Modular Monolith

Owner reset scope on 2026-10-02 for one developer and a Saudi/Arabic-first product. [Scope decision](SCOPE.md) supersedes the former assumption that time-consuming work must always use ARQ. The older FOUNDATION/V1 specification is historical context, not permission to introduce complexity.

## Target boundaries

Python/FastAPI + aiogram + PostgreSQL form the small baseline. Telegram is the first transport channel; HTTP and any later channel invoke the same application/domain modules in platform_core. Keep handlers thin. All related financial database writes are atomic; external providers use small adapters; failures have classifications, sanitized logs and stated policies. Alembic has already been introduced, so all future schema changes use migrations.

Prefer a direct service call for a small workload. Add background execution, Redis/ARQ, Next.js, full operations tooling or other infrastructure only after asking the owner whether its trigger actually exists. A single provider can use one function/interface. Do not add a speculative framework or a microservice.

## Current source, not the target minimum

The current repository implements PDF merge, SAR reservation/settlement history, native direct-per-order Stars, persisted Telegram workflows, ARQ workers, S3 file handling/PDF isolation and Next.js administration. It also has a direct local summarizer behind a small interface; this bypasses the legacy PROCESSORS/worker registry and uses no generative AI. The original completed-V0 description differed from the starting source.

The continuation implements the described text-summary/direct slice; see [direct service](DIRECT-SUMMARY.md) and [the roadmap](../ENGINEERING/MASTER_ROADMAP.md). Default Compose uses DB/migrator/API plus the optional text bot. Existing infrastructure stays in docker-compose.legacy.yml; its presence does not prove demand. PDF isolation, durable financial receipts and existing data must be assessed before any removal. The Digital Store remains independent.

Minimal readiness needs only migrated PostgreSQL. Legacy readiness/CI still cover old dependencies; direct/minimal checks qualify the selected slice. Legacy startup uses its explicit Compose file. Paid/provider/deployment readiness still needs actual staging.

## Historical FOUNDATION-001 acceptance (superseded source snapshot)

This milestone delivers the runnable processes, Compose dependencies, Caddy routes, baseline migration, structured logging, health endpoints, and CI. The Alembic revision is intentionally empty: adding speculative business tables before their invariants and transactions are implemented would create a misleading financial schema. No service fulfillment, wallet balances, orders, payment endpoints or customer uploads are active. The visible web page is a placeholder, not an admin dashboard.

API liveness: `GET /api/health/live`. API readiness: `GET /api/health/ready` probes PostgreSQL, Redis and the configured S3 bucket via a signed `HeadBucket` request. Next.js: `GET /web-health`. ARQ's health key monitors worker operation; the Telegram profile uses a fresh heartbeat after a successful bot API connection. Caddy routes `/api/*` to FastAPI and all other paths to Next.js. The bundled S3Mock is for development/CI and is never a production data store.

## Historical CORE-001 prerequisites (not a new-work mandate)

Implement an immutable wallet ledger with reservation uniqueness, order price snapshots and explicit state transitions, job attempts with retry exhaustion, S3 file validation and quality checks, and delivery events. Only then enable a paid Telegram service and the corresponding authenticated admin view. Integrate payment top-ups separately after webhook signature and idempotency tests. Do not mistake the foundation-stage `/start` response for an order flow.

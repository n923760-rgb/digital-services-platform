# Architecture contract — v1 foundation

This repository implements the `APPROVED FOUNDATION` v1.0 specification. The final brand, domain, payment provider, AI models, S3 provider and prices remain open decisions and belong in configuration or adapters. Changes to locked decisions require a recorded architecture decision.

## Boundaries

Telegram and HTTP are transport adapters. New customer channels may invoke application services but must never own the service registry, orders, jobs, pricing, wallet or templates. Domain transitions and financial ledger transactions will be implemented in `packages/python/platform_core` (or additional domain packages) in CORE-001. External AI, payment, file and notification providers require adapters. Work that takes time executes in ARQ workers. PostgreSQL holds metadata; S3-compatible storage holds customer files. The Digital Store remains independent and can only be linked to.

## FOUNDATION-001 acceptance

This milestone delivers the runnable processes, Compose dependencies, Caddy routes, baseline migration, structured logging, health endpoints, and CI. The Alembic revision is intentionally empty: adding speculative business tables before their invariants and transactions are implemented would create a misleading financial schema. No service fulfillment, wallet balances, orders, payment endpoints or customer uploads are active. The visible web page is a placeholder, not an admin dashboard.

API liveness: `GET /api/health/live`. API readiness: `GET /api/health/ready` probes PostgreSQL, Redis and object storage. Next.js: `GET /web-health`. ARQ's health key monitors worker operation; the Telegram profile uses a fresh heartbeat after a successful bot API connection. Caddy routes `/api/*` to FastAPI and all other paths to Next.js.

## CORE-001 prerequisites

Implement an immutable wallet ledger with reservation uniqueness, order price snapshots and explicit state transitions, job attempts with retry exhaustion, S3 file validation and quality checks, and delivery events. Only then enable a paid Telegram service and the corresponding authenticated admin view. Integrate payment top-ups separately after webhook signature and idempotency tests. Do not mistake the foundation-stage `/start` response for an order flow.

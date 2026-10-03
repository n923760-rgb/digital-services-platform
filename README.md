# Digital Services Platform

Saudi digital services platform for one developer, Arabic first/RTL, built as a Modular Monolith. Business operations are not enabled yet. The default runtime implements one gated [direct text-summary slice](docs/DIRECT-SUMMARY.md). Existing PDF/financial history is retained in the legacy configuration; [scope](docs/SCOPE.md) records the reset.

## Product direction

**Telegram is the first customer channel**. The architecture is Python/FastAPI + aiogram + PostgreSQL with domain modules in `platform_core`. Prefer one service and direct execution until an actual owner-confirmed trigger justifies another feature or infrastructure. Keep handlers thin, financial writes atomic, failures classified/logged with an explicit policy, external providers behind simple adapters, and schema changes migration-only now that Alembic exists.

The default service is a local text summarizer with direct execution and Stars invoices. Customer copy explains that it selects original sentences rather than using generative AI. Its small Summarizer interface supports a later owner-selected provider. No growth trigger was supplied; Redis/ARQ, S3/PDF isolation and Next.js stay in legacy source/configuration and do not run by default. See [direct summary](docs/DIRECT-SUMMARY.md).

Repository engineering rules and the central reusable reference are linked from [AGENTS.md](AGENTS.md) and [PROJECT-SOURCES.md](PROJECT-SOURCES.md); follow the one [engineering roadmap](ENGINEERING/MASTER_ROADMAP.md) for current qualification and remaining work.

## Minimal local startup

Requirements: Docker with Compose V2. Loopback port 8100 must be available. Paid operations stay gated off.

```bash
cp .env.example .env
docker compose up -d --build --wait db migrate api
curl --fail http://127.0.0.1:8100/api/health/ready
```

Check `docker compose ps` and `docker compose logs api`. Alembic completes before API startup; no Redis, worker, storage emulator or web UI is started.

For Telegram, set a valid `TELEGRAM_BOT_TOKEN` in the secret store/untracked `.env`, then use `docker compose --profile telegram up -d --build telegram-bot`. The default entrypoint is `apps.telegram_bot.v0`: /services, /summary, /orders, /cancel, /terms and /paysupport. Checkout stays off without qualified configuration; do not start two pollers for one token.

The optional [private unpaid Word trial](docs/OFFICE-TRIAL.md) adds `/word` for allowlisted users only. It is disabled by default, formats supplied text without generating content, and requires an approved isolated bot/database for runtime qualification. It does not add a catalog product or enable payments. [Codex handoff](docs/CODEX-HANDOFF.md) records the bounded next step.

Initialize an OWNER through `docker compose exec -it api python -m platform_core.admin_bootstrap`. Configure the owner-selected price using `python -m platform_core.summary_setup --price-stars <owner-value> --reason '<reason>'` inside the API container. Credentials are entered interactively. `--activate` also requires SERVICE_ACTIVATION_ENABLED; checkout requires both Telegram flags and actual terms/support. This change selects no live price or launch configuration.

Before switching an existing stack, resolve outstanding legacy orders, then stop its bot/worker/API/web/Caddy with `docker compose -f docker-compose.legacy.yml stop telegram-bot worker api web caddy`. The new bot refuses startup with outstanding legacy work. Project/database-volume names are preserved; never remove volumes to simplify architecture.

## Optional product administration

The owner confirmed a current need for service products managed from the existing panel. The [product catalog](docs/PRODUCT-CATALOG.md) supports creating drafts, later name/description/Stars-price edits and explicit activation. The direct bot reads supported active products from PostgreSQL through /services; no restart is required. Its current execution method is local text summarization; registering a product does not implement another capability.

Run `docker compose --profile admin up -d --build --wait api web caddy` and open http://127.0.0.1:8101/admin. For this loopback HTTP setup only, configure ADMIN_COOKIE_SECURE=false in the untracked configuration and recreate API; secure cookies remain the default. Reuse interactive OWNER bootstrap. The optional panel requires no Redis/storage/worker. Do not use the CI override against live data or enable paid checkout before actual staging and owner terms/support/prices.

## Preserved legacy stack

PDF/admin/storage instructions below apply to `docker-compose.legacy.yml`. Set `COMPOSE_FILE=docker-compose.legacy.yml` or add `-f docker-compose.legacy.yml` for those commands. The old stack remains available for continuity/recovery and does not run by default.

The PDF merge conversation is persisted in PostgreSQL but remains **off by default** (`TELEGRAM_ORDERS_ENABLED=false`). The flag alone does not make a production service safe: an enabled registry entry, configured Stars prices/terms/support and qualified real payments/refunds, full document safety checks and operational controls are still required. The Compose deployment now includes a no-network PDF processor container with a private shared volume and resource limits. Never enable public uploads against the bundled development S3 emulator.

To create the first administrator after migrations, use an interactive terminal: `docker compose exec -it api python -m platform_core.admin_bootstrap`. Enter a unique username and a password of at least 12 characters at the prompts. The command refuses to create another owner after the first one exists. Visit `/admin` for the operations dashboard. OWNER can view audit events and register/edit disabled services and categories; OPERATOR has read-only operational access. Activation remains off by default and cannot make the service production-ready by itself. For local HTTP only, set `ADMIN_COOKIE_SECURE=false` in your untracked `.env` before starting the API; always keep it `true` with HTTPS in production. The admin session lasts up to 12 hours, and login and admin writes require a matching browser Origin.

The owner-selected customer payment is **Telegram Stars directly per order**. The gated native XTR path stores whole-Star prices, terms-bound invoices, durable paid receipts and refund state without funding or converting the SAR wallet. See [Stars configuration and qualification](docs/TELEGRAM-STARS.md). TELEGRAM_STARS_ENABLED remains false, and terms/support/Stars prices are unset until owner configuration and authorized live qualification.

The earlier provider-independent SAR payment kernel stores wallet top-up intents and signed-provider event receipts. It checks the provider, reference, amount and SAR currency before crediting once in the same database transaction. There is **no checkout endpoint, live provider adapter or public webhook**; the signature adapter in tests is only a test fixture. Do not fund customer wallets using a simulated provider. See [payment integration requirements](docs/PAYMENTS.md).

To run the Python checks locally, use the locked Python toolchain and [dependency installation steps](docs/DEPENDENCIES.md), then `ruff check apps packages tests migrations scripts`, `alembic upgrade head`, and `pytest -q` against a dedicated test PostgreSQL database. For the web app, use the qualified Node version in [dependency inputs](docs/DEPENDENCIES.md), run `npm ci`, `npm run typecheck`, and `npm run build` inside `apps/web`.

## Layout

- `apps/api`: FastAPI HTTP transport and readiness probes.
- `apps/telegram_bot`: aiogram channel entrypoint, no business logic.
- `apps/web`: existing Next.js Arabic RTL operations UI; OWNER writes and OPERATOR reads. Its expansion requires an actual trigger.
- `packages/python/platform_core`: settings, logging, worker and health utilities.
- `docs/FILES.md`: internal file validation and retention contract.
- `migrations`: Alembic revision history.
- `infrastructure/caddy`: reverse proxy configuration.
- `infrastructure/backup`: PostgreSQL snapshot scripts and CI restore check.
- `docs/BACKUP-RECOVERY.md`: operational backup and recovery procedure.
- `docs/SERVICE-REGISTRY.md`: audited service administration and activation gate.
- `docs`: architecture decisions and milestone acceptance.

## Deployment notes

For a public domain, set `SITE_ADDRESS` to the domain and point DNS to the host; Caddy obtains TLS certificates when reachable. Replace every demonstration password and credential. Never commit `.env`. PostgreSQL, Redis and the local S3 emulator have private Compose networking only; Caddy is the sole public entrypoint. **The included S3Mock is for local development and CI only: it must be replaced with a production S3-compatible provider before handling customer files.** Configure `OBJECT_STORAGE_ENDPOINT`, credentials and the pre-created bucket for that provider, and remove the emulator service in the production Compose override. The backup container creates local PostgreSQL snapshots; follow [backup and recovery](docs/BACKUP-RECOVERY.md) to establish encrypted off-host copies and verify recovery before production. Qualification requirements apply to the selected live service and its actual dependencies; the historical V1 specification does not authorize adding more infrastructure.

The Digital Store is a separate product and does not share this wallet, orders, or database. No store integration is included in FOUNDATION-001.

Known-advisory checks run against locked Python runtime and npm production dependencies in read-only CI; see [coverage and update steps](docs/DEPENDENCY-AUDIT.md). A successful scan is time-dependent and does not certify production readiness.

Completed source review and qualified repairs: [Arabic review checkpoint](ENGINEERING/REPORTS/2026-10-01-POST_REPAIR_REVIEW.md), [evidence index](ENGINEERING/EVIDENCE/2026-10-01-QUALIFIED_CHANGES.md), and [remaining engineering gates](ENGINEERING/MASTER_ROADMAP.md). Telegram remains the customer channel; this repository is not a qualified paid production release.

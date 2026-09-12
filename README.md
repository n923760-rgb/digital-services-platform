# Digital Services Platform — FOUNDATION-001

Independent modular-monolith foundation for the approved Saudi digital services platform. The project name and domain are deliberately provisional. Business operations are not enabled yet. The internal CORE-001 [PDF merge and financial workflow](docs/CORE-001.md) is under development; it does not accept live orders.

## Local startup

Requirements: Docker with Compose V2. Port 80 must be available.

```bash
cp .env.example .env
docker compose up -d --build --wait db redis object-storage migrate api worker web caddy
curl --fail http://localhost/api/health/ready
curl --fail http://localhost/web-health
```

Check `docker compose ps` and `docker compose logs api worker` for service status. The database migration runs to completion before the API starts. The local S3 test bucket is initialized automatically.

For Telegram, set a valid `TELEGRAM_BOT_TOKEN` in `.env`, then run `docker compose --profile telegram up -d --build telegram-bot`. `/start` responds with a clear foundation-stage message; no paid orders are accepted yet. Keep the bot token secret. To avoid webhook/polling conflicts, only one bot instance should poll a token.

The PDF merge conversation is persisted in PostgreSQL but remains **off by default** (`TELEGRAM_ORDERS_ENABLED=false`). The flag alone does not make a production service safe: an enabled registry entry, authorized wallet funding, isolated PDF processing and operational controls are still required. Never enable public uploads against the bundled development S3 emulator.

To create the first administrator after migrations, use an interactive terminal: `docker compose exec -it api python -m platform_core.admin_bootstrap`. Enter a unique username and a password of at least 12 characters at the prompts. The command refuses to create another owner after the first one exists. Visit `/admin` for the read-only dashboard. OWNER can view the audit API; OPERATOR can view operational data but cannot view audit events. Administrative write operations are not yet exposed. For local HTTP only, set `ADMIN_COOKIE_SECURE=false` in your untracked `.env` before starting the API; always keep it `true` with HTTPS in production. The admin session lasts up to 12 hours, and the login endpoint requires a matching browser Origin and Redis rate limiting.

The provider-independent payment kernel stores wallet top-up intents and signed-provider event receipts. It checks the provider, reference, amount and SAR currency before crediting once in the same database transaction. There is **no checkout endpoint, live provider adapter or public webhook**; the signature adapter in tests is only a test fixture. Do not fund customer wallets using a simulated provider. See [payment integration requirements](docs/PAYMENTS.md).

To run the Python checks locally, use Python 3.12 and `pip install -e '.[dev]'`, then `ruff check apps packages tests migrations`, `alembic upgrade head`, and `pytest -q` against a dedicated test PostgreSQL database. For the web app, use Node 22, run `npm install`, `npm run typecheck`, and `npm run build` inside `apps/web`.

## Layout

- `apps/api`: FastAPI HTTP transport and readiness probes.
- `apps/telegram_bot`: aiogram channel entrypoint, no business logic.
- `apps/web`: Next.js Arabic RTL foundation and authenticated read-only admin dashboard.
- `packages/python/platform_core`: settings, logging, worker and health utilities.
- `docs/FILES.md`: internal file validation and retention contract.
- `migrations`: Alembic revision history.
- `infrastructure/caddy`: reverse proxy configuration.
- `docs`: architecture decisions and milestone acceptance.

## Deployment notes

For a public domain, set `SITE_ADDRESS` to the domain and point DNS to the host; Caddy obtains TLS certificates when reachable. Replace every demonstration password and credential. Never commit `.env`. PostgreSQL, Redis and the local S3 emulator have private Compose networking only; Caddy is the sole public entrypoint. **The included S3Mock is for local development and CI only: it must be replaced with a production S3-compatible provider before handling customer files.** Configure `OBJECT_STORAGE_ENDPOINT`, credentials and the pre-created bucket for that provider, and remove the emulator service in the production Compose override. Set up durable backup and restore procedures before production. The V1 production checklist in the approved specification remains mandatory.

The Digital Store is a separate product and does not share this wallet, orders, or database. No store integration is included in FOUNDATION-001.

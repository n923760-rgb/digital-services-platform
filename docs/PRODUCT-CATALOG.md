# Owner-managed service products

## Confirmed scope

On 2026-10-02 the owner requested adding products and later changing prices in the panel so products appear in Telegram. The actual-trigger question was answered **“نعم؛ خدمات ينفّذها البوت”**. This authorizes current service-product management; it does not authorize file sales, another processor/provider, queue infrastructure or a paid launch.
Reuse the existing authenticated Arabic admin UI/API and PostgreSQL. Web/Caddy run only with the admin Compose profile. No Redis/ARQ/storage worker is required for direct products or admin login.

## Owner journey

1. Start the optional local panel, establish OWNER using the existing interactive bootstrap and sign in.
2. Choose or create a category. Register a product with its unique slug, Arabic name/description, optional whole-Star price and supported execution method.
3. The product is saved disabled. Registration cannot enable it. A price and the existing SERVICE_ACTIVATION_ENABLED gate, explicit availability confirmation and a reason are required for activation.
4. After activation, customers opening /services, /start or /summary see enabled, priced, supported products from enabled categories. The menu re-reads PostgreSQL each time; no bot restart or broadcast is required. This initial menu is bounded to 50 products.
5. Customers select a product, send text, review its freshly quoted price and complete purchase terms, then request that exact invoice. Terms are sent in full before the payment button, without truncating consent.
6. Edit name, description or Stars price later using the current revision and a reason. Updates/audit commit atomically. A stale panel edit returns 409 and reloads. Stale pre-checkout prices are rejected; an already approved payment retains its original invoice/order price.
7. Disabling removes the product from new listings/checkout; existing accepted orders retain their receipt/refund/delivery handling.

## Execution boundary

Product UUID/slug is independent of processor_key. Migration 0018 binds historical summarize-text/merge-pdf rows to their existing executor. New direct products may use the implemented **local extractive text summary** with its exact 4,000-character schema. They share that actual capability; changing names/descriptions does not implement translation, generative AI or another service. No arbitrary code or JSON workflow is executed from the panel.
An unfinished service can be stored as a draft with no executor and cannot be activated/sold. Another execution method requires an explicitly scoped implementation with its actual trigger confirmed. The preserved PDF path remains in the legacy stack; the direct bot only advertises supported text-summary products.

Private selection reuses the existing PostgreSQL workflow, with wallet locking and one active workflow per customer. Switching products cancels the previous unpaid offer. Re-selecting the same product preserves its offer. Confirmation binds product ID, exact input digest, price, terms/revision and buyer; equal-price products cannot be substituted. Direct summaries still create no jobs or SAR writes. Delivery and permanent-failure/refund rules remain in [the direct contract](DIRECT-SUMMARY.md).

## Optional local administration

Default startup remains DB/migrator/API, with Telegram opt-in. For local HTTP on loopback only, set ADMIN_COOKIE_SECURE=false in the untracked configuration and recreate API; keep true for HTTPS deployments.

```bash
docker compose --profile admin up -d --build --wait api web caddy
docker compose exec -it api python -m platform_core.admin_bootstrap
```

Open http://127.0.0.1:8101/admin. Secure-cookie default is unchanged; no login credentials are generated or committed for the owner. Do not expose this local HTTP binding publicly. Owner-select final terms/support/price and qualify a real isolated bot/payment/refund before launch; checkout flags remain off.
The optional proxy uses a separate internal subnet (default 172.31.0.0/29) and trusts only its Caddy address plus loopback, never arbitrary forwarded headers. PRODUCT_PROXY_NETWORK_SUBNET / PRODUCT_TRUSTED_PROXY_IP / PRODUCT_API_PROXY_IP can be set coherently to avoid host/network overlaps. The old 172.30 proxy and legacy configuration remain unchanged.

## Authentication and evidence

Minimal API reuses Argon2 credentials, opaque secure/HttpOnly/SameSite cookies, server-side OWNER/OPERATOR permissions, strict browser Origin and append-only auditing. Its login source/account/pair counters use hashed identities in PostgreSQL: stable key lock order, fixed expiry, all three increments in one transaction, bounded expired-row cleanup and fail-closed infrastructure errors. The legacy API keeps its existing Redis limiter. No runtime bypass/fallback silently disables limits.

CI-only tests/compose.catalog.yml enables local HTTP and synthetic service activation on an isolated DB, explicitly disables billing and has no bot token. Never use that override or catalog_smoke on a live deployment; the smoke creates ephemeral test administrators/products. It checks actual HTTP cookies/Origin/CRUD/revisions/catalog and two independent clients' forwarded-header rejection. Built-web Chromium uses a synthetic API and checks Arabic RTL, product creation, duplicate submission, later name/price editing and existing regressions. Telegram/provider calls in tests are synthetic. Final exact-source IDs/results belong in the PR body.
No real payment/refund, external AI call, owner credential change, public deployment or production migration is performed by this source change.

# Direct text summary — small selected slice

The owner's 2026-10-02 scope describes one text-summary service and direct execution. The follow-up “كمل” continues that scope. No measured trigger for queues/UI expansion was supplied; the earlier service/background questions were not answered separately. This implementation follows the described summary/direct baseline, without claiming an observed growth trigger. The optional provider question remains open; the implemented default is a local extractive summarizer, explicitly described in customer copy. No external AI/model/account/cost was selected.

## Application and provider boundary

platform_core/text_summary.py contains validation and the small Summarizer interface. LocalSummarizer chooses up to three original sentences by word frequency and retains their original order. It supports Arabic/plain text and caps results at 1,800 characters. This is not generative AI, a semantic-quality benchmark or a guarantee of a good summary. Inputs are 20–4,000 characters with letters. The provider is injected into execute_summary; an external implementation can later use the same interface after its actual need/provider selection is confirmed.

platform_core/summary_orders.py owns quote, execution, result/delivery and failure state. Telegram handlers parse/private-check input and invoke it. API v0 exposes health only, not an unauthenticated summary/payment endpoint.

## Paid direct journey

An enabled summarize-text service with an OWNER-set whole-Star price and configured terms/support is required. The bot presents the local algorithm/price/terms before requesting the accepted offer's XTR invoice. The immutable invoice binds a SHA-256 of the input alongside buyer/price/terms/revision; raw text is separate with expiry, and updates to its accepted snapshot are rejected.

Existing Stars owner/currency/amount/checkout/receipt/refund rules apply. The minimal entrypoint accepts checkout/fulfillment only for summarize-text. A successful receipt atomically creates one order/charge history without a jobs row, reserve or SAR conversion. QUEUED remains an existing database order-state name for accepted work; there is no dispatch queue, ARQ process or Redis dependency in this runtime.

The handler calls execute_summary directly. It claims one attempt atomically, invokes the provider outside database locks with a five-second bound, and persists the result/state atomically. Replay reuses the cached result. An actual successful send returns a receipt before DELIVERED/COMPLETED is recorded atomically. Concurrent refunds block completion. Provider/invalid-output failures record FAILED plus REFUND_REQUESTED atomically.

## Explicit error and recovery policies

Invalid input/offer is logged by sanitized classification and rejected with guidance. Receipt mismatches are logged and retained REJECTED. Provider failures are logged without response bodies, request a refund and propagate; unexpected faults are classified at the handler boundary and return a safe failure notice. Transport/DB failures retain durable receipts/unresolved work for investigation.

A send error can follow an accepted message: it stays AWAITING_FULFILLMENT with cached output and a logged uncertain-delivery state. /orders, /summary, /start or a payment interaction drains a bounded inbox batch and resumes relevant accepted orders/refunds. Restart drains billing and resumes up to twenty accepted/results-awaiting orders; additional work is handled on later interactions. A PROCESSING attempt interrupted by shutdown/crash is failed/refunded on one-poller startup, not automatically run/charged again. Refund retries retain the sixty-second spacing and positive-provider/history-evidence requirement. There is no unattended refund scheduler here; outstanding cases need repeat interaction/operator support.

Exactly-once sending is not promised. Accepted send followed by a crash/DB failure may produce another message on retry, never another charge/order. Disputes and history beyond the latest 100 transactions need operator reconciliation. Actual staging is required before paid activation.

## Persistence, retention and migration

Migration 0017 adds expiring inputs/results and an immutable input digest to invoices. It registers summarize-text disabled with no Stars price, preserves all SAR/PDF/Stars history, and refuses destructive downgrade. Application rollback retains the additive schema. No create_all/manual schema changes.

Existing internal FILE_RETENTION_DAYS is used for text expiry (1–365 days here), not a newly approved privacy policy. Expired text cannot be checked out/executed/read as a pending result. Raw text is physically purged on startup/new quote activity; an idle process does not promise timed physical deletion. Financial invoices retain only the input hash and purchase terms. Final privacy/retention and actual recovery remain launch decisions.

## Startup and configuration

Default docker-compose.yml runs PostgreSQL, its one-shot Alembic migrator and a DB-only FastAPI health adapter; the opt-in telegram profile runs apps.telegram_bot.v0. No Redis, S3, PDF parser, ARQ worker, Caddy or Next.js process is required. API binds loopback port 8100 and exposes health only. This is a source/local startup change, not a production deployment.

The bot authenticates with Telegram before opening the application database or running expiry cleanup/interrupted-order recovery. Missing/malformed tokens, rejected authentication and transport failure stop startup with a sanitized classification; no order/refund state is changed. Constructed bot sessions are closed even when authentication fails. After authentication, the existing legacy-work guard still runs before recovery.

The previous stack is preserved verbatim in docker-compose.legacy.yml, including its volume/project name. Both use the same database volume by default for continuity; do not run both bots against one token. Resolve outstanding legacy accepted/reserved orders before switching; the new bot refuses startup while they exist. Stop the old bot/worker/UI only after resolving its work. Never delete volumes or financial/migration history.

Run admin_bootstrap locally to establish OWNER, then authenticate the summary_setup CLI to set the owner-selected price/reason. --activate additionally requires SERVICE_ACTIVATION_ENABLED; new checkout requires both Telegram flags and actual terms/support. No example price is a recommendation; this PR changes no production flags.

PDF/admin/files/storage contracts apply to the preserved legacy configuration. Legacy commands use COMPOSE_FILE=docker-compose.legacy.yml or explicit -f. Existing backup scripts remain available for the database through the appropriate configuration; off-host recovery is not certified.

## Evidence boundary

Provider/bot calls in tests are fake; PostgreSQL is disposable. Historical-stack regressions remain alongside new direct-path cases and an actual minimal Compose smoke without Redis/storage/workers. Final source/runs/results live in the PR body. No actual Stars charge/refund, real bot journey, external AI call, production migration or deployment was performed.

# Owner-managed service products — preparation and boundaries

## Authority and source

Owner requested finishing remaining work and a panel to add products/edit prices and expose additions in Telegram. Asked whether current need exists and whether products are bot-executed services or file sales; answer **“نعم؛ خدمات ينفّذها البوت”**. This authorizes this coherent management/catalog slice. No new queue, provider, file sales, additional business processor or paid activation is inferred.
Verified starting main 84d31b574f8d5779c8c335c257b72cae300da0b3, tree fc8bdd676c08a1cb76a4a0d1c744276ff2459c59; no open PR. Central reference unchanged at 641e4f9e45da109257ba1f38752b94604c2e4531. Root/source/roadmap, relevant scope/registry/Stars/direct/financial/recovery contracts and admin/Arabic/Telegram/release skills read. Repository API/existing external CI available; local shell/browser/provider NOT RUN. No subagents.

## Smallest implementation

Reuse existing administration instead of another dashboard. Add explicit known executor binding independently of product slug, OWNER name/description/Stars-price editing with revision/audit, fresh bot catalog and persisted private selection using the existing workflow. New products remain drafts; only enabled/priced/schema-compatible summary products reach the direct bot. Current execution is local extractive summary, not a newly implemented business capability. Unsupported entries remain inactive.

Migration 0018 preserves old financial/history data and binds existing executor identities; it also adds expiring hashed login counters so the selected admin API needs PostgreSQL only. Counter increments are atomic/ordered across clients and infrastructure failures fail closed. The legacy Redis limiter/configuration remains.
Optional admin profile reuses Next.js/Caddy and strict same-Origin/server permissions/cookie/proxy boundaries. Separate internal proxy subnet and loopback-only port 8101; default service runtime still has no Redis/ARQ/storage/web worker. No dependency lock or public deployment change.

Payment confirmation now also verifies the product ID. Switching products cancels the previous unpaid offer; pre-checkout rechecks price, original buyer/input/terms, while already approved payment honors its original amount. Whole-Star order snapshots and receipts remain separate from SAR, direct execution creates no jobs, and verified delivery/refund transitions retain atomic domain handling. Complete terms precede the pay button without Unicode truncation.

## Meaningful validation

Disposable PostgreSQL/HTTP tests cover draft visibility, activation/withdrawal, live rename/price, paid snapshot and no-job fulfillment, product-switch late-charge refund, stale price rejection, same-price identity rebinding, private callback ownership/persistence and menu refresh.
Admin route cases cover anonymous/OPERATOR/OWNER, forged Origin, registration replay, arbitrary executor rejection, revision conflicts, activation gating and immutable audit. Concurrent PostgreSQL limiter tests and fail-closed outages protect the DB-only path.
Built Chromium tests preserve all historical RTL/auth/pagination regressions and add real product-form interaction, duplicate submission and later name/price edits against synthetic API. Optional Compose smoke uses an isolated DB and ephemeral generated admin credentials to verify actual HTTP login/cookies/Origin/CRUD/catalog plus two independent proxy clients and direct-header spoof rejection.
Final full diff/source identities, exact Foundation/advisory IDs/results are recorded in the reviewable PR; this preparation does not claim premature PASS.

## Remaining dependent work

The request does not supply a disposable real bot/environment, business prices/final terms/support, privacy/retention or public launch authority. No real charge/refund, provider call, owner credential change, production migration or deployment is performed. Do not apply tests/compose.catalog.yml or catalog_smoke to live data. New execution methods need confirmed actual need and their own implementation before activation. Broadcast/notification to all customers is not included; catalog refresh occurs when opened.

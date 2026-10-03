# Offline bot acceptance — existing CI, no live environment

## Authority and source

On 2026-10-03 the owner selected preparation/testing of the current bot before launch, then clarified “ما عندي حاليا تجريبي فيه طريق أخرى” and accepted continuing with existing GitHub Actions. Latest clarification supersedes the earlier reported server availability. This authorizes bounded qualification of existing behavior, not another service/provider, infrastructure or live payments.
Verified base main 40971fb6d6c894ed2c6913f8e3bb454c0f8c21fa/tree 2747349833216d768541a5b97dd132f6c55bf2a4; only separate Word draft PR #46 was open at inspection. Preserve that draft's source and no-implicit-merge scope. Central governance unchanged at 641e4f9e45da109257ba1f38752b94604c2e4531.
Root authority, source map, canonical roadmap, scope/direct/Stars/financial contracts and financial/Telegram/release skills reviewed. Execution capabilities: repository API/existing CI; no local shell, SSH, real bot or owner runtime.

## Coverage gap and bounded implementation

Existing domain/adapter tests prove separate catalog/finance/delivery properties but do not route the entire selected-product-to-result journey through the real aiogram Dispatcher. Add one acceptance file using locked SDK Bot/Update/Message/callback/checkout/payment types and a small BaseSession fixture. The transport returns typed responses without any network and fails on unsupported methods/downloads. It refuses to confirm other disposable tests' pending refunds.

Three selected-product scenarios cover success, changed pre-checkout price and uncertain result delivery. The customer opens the actual menu, chooses its product, receives full terms and the priced confirmation, requests/replays one persisted invoice, rejects a foreign payer, approves checkout and receives a synthetic persisted payment. Post-approval catalog price changes retain the purchased amount. Same-update and new-update charge replay must retain one order/PAID/DELIVERED event, one delivered result, zero jobs and no SAR wallet balance change. Uncertain send retains PAID/cached result until /orders retries and obtains a synthetic receipt. Logs must not contain the synthetic transport body.
A fourth case routes disabled checkout, supported commands, unknown command, text, photo and ignored group input; no invoice/order may be created.

DB behavior and the built-in local summarizer are real in disposable CI; Telegram responses are synthetic. Persist-before-dispatch is modeled using the production inbox function; existing polling tests separately verify offset/DB-failure behavior. This does not run a real Telegram long-poller/authentication/payment/refund.

## Review and validation

Changed scope: tests/test_offline_bot_journey.py, the existing Arabic trial guide, canonical roadmap and this report. No product handler/domain change, workflow change, dependency/lock, migration, provider, credentials or actual billing/activation setting. Test-local prices/flags/admin credentials are synthetic isolated fixtures, not business choices or launch settings.
Review full diff, actual schema/SDK method signatures, private identities, DB isolation, no-network transport and links. Do not add prose-mirroring tests or rerun green CI unnecessarily. Exact final source/tree, required Foundation/advisory runs and actual counts/results belong in the PR body; this preparation does not claim premature PASS.

## Remaining evidence

No current approved trial host/bot is available. Actual Telegram authentication/menu/invoice/message/refund, production deployment and database recovery remain NOT RUN. The automation qualifies only its stated cases. Keep paid defaults off; resume the existing isolated runbook when an environment becomes available. No new product feature or stage expansion is inferred.

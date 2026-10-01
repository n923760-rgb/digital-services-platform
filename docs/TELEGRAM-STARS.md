# Telegram Stars — direct payment per order

Owner selected Telegram Stars and **direct payment for each order**. Native prices are whole Stars (XTR); there is no exchange rate, SAR wallet funding or internal Stars balance. The existing SAR ledger/payment history remains separate and append-only.

## Customer flow and price administration

OWNER configures an integer base_price_stars for each service through the revisioned, same-Origin, audited service API/admin form. Prices are initially unset; no live service/price is selected or enabled automatically. The engineering cap is 100,000 Stars, not a recommended business price. Fractions, booleans, zero and negative values are rejected. Leaving an edit price blank preserves the previous price; disable the service to withdraw an offer. Existing SAR prices/history are preserved for prior internal paths; new bot catalog/quotes use Stars.

Private PDF intake produces a revisioned Stars quote with the configured purchase terms. The button explicitly agrees to those terms and requests that exact offer's invoice. The stored invoice includes amount, owner, ordered inputs, quote revision, full accepted terms and their digest. Changed files/price/terms invalidate checkout. A repeated button returns the same invoice; an already-paid order is not invoiced again. Forwarded invoices have a start_parameter link, and server-side owner checks reject a different payer independently.

sendInvoice uses XTR, empty provider_token and exactly one LabeledPrice; no card/payment-provider credentials are needed. Pre-checkout checks private buyer identity, payload, amount, currency, service availability, original ordered inputs/expiry and terms. Its database work has a five-second deadline with bounded connect/close time, leaving time for Telegram's required answer within ten seconds. Approval does not create a job or establish payment. A second distinct checkout query for the same invoice is rejected; the buyer must review a fresh offer after an abandoned checkout.

Only a successful_payment received from the configured bot's authenticated HTTPS polling is a paid receipt. There is no public payment webhook or HMAC fixture pretending to verify Telegram. A charge ID is bound once, and concurrent/replayed receipts create one XTR order and job atomically. The order has price_snapshot_stars and zero SAR amount; no SAR reserve/credit/capture occurs. Price changes after checkout approval honor its original amount. If payment arrives after cancellation/input changes/expiry, an unavailable service or disabled fulfillment gate, it is recorded for refund rather than executed. Additional distinct charges for one invoice are also refunded.

## Durable receipt handling

Polling inserts minimal payment/refund fields into telegram_payment_inbox before advancing getUpdates offset. Bot ID and update ID deduplicate transport receipts. If insertion fails, that update is not acknowledged. Ordinary handlers run as tasks so an upload does not hold up pre-checkout. As with the previous aiogram default, global update/handler-load qualification remains open. Shutdown cancels ordinary tasks; billing receipts survive in PostgreSQL.

A worker drains bounded inbox transactions independently of whether new checkout is enabled. Domain mismatches become REJECTED and appear in the admin attention counter; database failures retain pending data and require operational investigation. Other receipt types/customer text are not copied into this financial inbox. One polling instance per bot token remains mandatory. Legacy SAR confirmation buttons cannot create new customer orders.

## Delivery, failure and actual refund

Telegram collects Stars before processing; application DELIVERED recognition is appended only after a real result-message receipt. PAID, DELIVERED, REFUND_REQUESTED and REFUNDED events are append-only. A permanent processing/delivery failure requests a full Telegram refund; a SAR RELEASE is not used.

The worker selects at most five eligible refund charges, commits retry timestamps and releases database locks before API calls. It calls refundStarPayment with the stored buyer and Telegram charge ID. Eight-second API/reconciliation bounds and a minimum sixty-second retry spacing leave failed refunds pending. Only a positive provider response, an authenticated refunded_payment update, or matching outgoing getStarTransactions evidence can mark REFUNDED. Error wording alone is not success. Refund confirmation checks charge/invoice, XTR amount and buyer; it preserves historical events and blocks further order completion. In-flight sends can still race an external refund: exactly-once sending is not promised.

A timeout/crash after provider success is reconciled against the latest 100 transactions, matching charge ID, whole-Star amount, outgoing user, invoice transaction type and original payload. Older history, provider disputes/chargebacks and off-host post-restore reconciliation still require a qualified operator procedure; unresolved cases stay pending, not falsely refunded. Monitor the admin pending-refund and pending/rejected-inbox counters. Customer status shows refund progress without revealing provider charge IDs.

Migration 0016 preserves SAR records and adds Stars tables/columns. Its downgrade intentionally refuses financial-history deletion: application rollback keeps the additive schema. Production migration and any destructive recovery need separately scoped owner authority.

## Launch configuration and remaining gates

TELEGRAM_STARS_ENABLED=false, TELEGRAM_ORDERS_ENABLED=false and SERVICE_ACTIVATION_ENABLED=false remain defaults. Checkout also requires nonempty TELEGRAM_PAYMENT_TERMS and TELEGRAM_PAYMENT_SUPPORT, supplied through deployment configuration. /terms displays the actual configured purchase terms; /paysupport gives the configured payment-support instructions/contact. The repository does not invent final business terms, prices, dispute/refund policy, branding or an operator SLA. These fields alone do not certify launch readiness.

Before activation, qualify an authorized disposable bot with actual invoice/checkout/paid receipt, owner/forwarding/replay cases, delivered output, API failure/restart and actual refund/history confirmation. Verify the bot's Stars account, support handling, disputes/chargebacks, production S3/IAM/document safety, monitoring, independent DB + object recovery and post-restore transaction reconciliation. Test fixtures and CI do not charge/refund real Stars. No bot token should be placed in chat or Git.

## Current official sources

Read from Telegram's public HTTPS documentation in isolated no-credential CI run [36939338230](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36939338230), job 110626921705:
- [Digital goods and Stars](https://core.telegram.org/bots/payments-stars), captured SHA-256 8e09f3e13f920530d2663d76b4f91520c02bda6e7fff3677730861106f74bcda.
- [Bot API](https://core.telegram.org/bots/api), captured SHA-256 a76411fdb18555e7fe01c92e4476c348694f1d6442e551ea9f4b29f648e792fa; sendInvoice, answerPreCheckoutQuery, SuccessfulPayment, refundStarPayment, RefundedPayment, getStarTransactions, StarTransaction and TransactionPartnerUser sections.
- Relevant generated types/methods were compared with locked aiogram 3.31.0; dependencies were not changed.

Final source qualification belongs to [PR #40](https://github.com/n923760-rgb/digital-services-platform/pull/40) and exact-source CI logs. This contract describes behavior and outstanding live qualification; it is not a production payment certification.

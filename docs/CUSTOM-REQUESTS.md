# Custom service requests — text intake

The Telegram «➕ اطلب خدمة» shortcut opens one durable `COLLECTING` draft per user and channel. A single 10–2000 character text message submits it as `NEW`; repeated deliveries of the same message key return the original request, including concurrent retries. `/start` can resume a draft and «إلغاء» cancels an unsent draft. Idempotency keys and draft uniqueness are scoped to a channel, so another channel can use the same domain service later. Data and transition logic are in `platform_core.custom_requests`, outside Telegram handlers.

The admin overview and bounded review list show `NEW` and `IN_REVIEW` requests only to an authenticated admin with `admin:view`. Only OWNER (`admin:manage`) can start review or decline a request. Decline is allowed only after review starts, and only the assigned administrator can perform it. Every transition checks an expected revision under a row lock and writes an immutable audit event in the same transaction. Decline reasons are 10–500 characters and are not exposed to customers by this increment.

This remains a controlled review increment: no AI triage, quote, order, wallet reservation, customer notification or execution follows a transition. The bot tells the customer the price will be reviewed and no funds are taken. Do not promise a response SLA or enable paid fulfillment based on these records alone.

Attachments, voice and image submissions, customer-facing decline notifications, quotes and request-to-order conversion are future increments; they require authenticated file handling, a durable notification boundary, customer confirmation and payment integration. This text-only route does not make the public paid-service flag safe to enable.

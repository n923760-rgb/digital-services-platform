# Custom service requests — text intake

The Telegram «➕ اطلب خدمة» shortcut opens one durable `COLLECTING` draft per user and channel. A single 10–2000 character text message submits it as `NEW`; repeated deliveries of the same message key return the original request, including concurrent retries. `/start` can resume a draft and «إلغاء» cancels an unsent draft. Idempotency keys and draft uniqueness are scoped to a channel, so another channel can use the same domain service later. Data and transition logic are in `platform_core.custom_requests`, outside Telegram handlers.

The admin overview and review list show new requests only to an authenticated admin with `admin:view`; the list is capped at 50 and includes customer text and Telegram ID. This is a **review-only** first increment: no AI triage, quote, order, wallet reservation, notification or execution follows a submission. The bot tells the customer the price will be reviewed and no funds are taken. Do not promise a response SLA or enable paid fulfillment based on the presence of a `NEW` record alone.

Attachments, voice and image submissions, admin disposition, customer quotes and request-to-order conversion are future increments; they require authenticated file handling, transitions with audit, customer confirmation and payment integration. This text-only route does not make the public paid-service flag safe to enable.

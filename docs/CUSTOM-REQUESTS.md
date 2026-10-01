# Custom service requests — text intake

The Telegram «➕ اطلب خدمة» shortcut opens one durable `COLLECTING` draft per user and channel. A single 10–2000 character text message submits it as `NEW`; repeated deliveries of the same message key return the original request, including concurrent retries. `/start` can resume a draft and «إلغاء» cancels an unsent draft. Idempotency keys and draft uniqueness are scoped to a channel, so another channel can use the same domain service later. Data and transition logic are in `platform_core.custom_requests`, outside Telegram handlers.

The admin overview and bounded review list show `NEW` and `IN_REVIEW` requests only to an authenticated admin with `admin:view`. Only OWNER (`admin:manage`) can start review or decline a request. Decline is allowed only after review starts, and only the assigned administrator can perform it. Every transition checks an expected revision under a row lock and writes an immutable audit event in the same transaction. Decline reasons are 10–500 characters and are not exposed to customers by this increment.

This remains a controlled review increment: no AI triage, quote, order, wallet reservation, proactive customer notification or execution follows a transition. The bot tells the customer the price will be reviewed and no funds are taken. Do not promise a response SLA or enable paid fulfillment based on these records alone.

Attachments, voice and image submissions, proactive decline notifications, quotes and request-to-order conversion are future increments; they require authenticated file handling, a durable notification boundary, customer confirmation and payment integration. This text-only route does not make the public paid-service flag safe to enable.

The bot explicitly asks for text-only review intake; links in descriptions remain text and are not fetched. Unsupported media receives a private-chat explanation. Documents sent while a review draft is open do not enter the PDF upload workflow or consume that draft.

«📋 طلباتي» reads the latest ten submitted Telegram review requests and Telegram orders owned by the sender. NEW/IN_REVIEW/DECLINED are shown in Arabic, together with paid-order processing/delivery status. Unsent drafts and other-channel requests are excluded. Internal descriptions and decision reasons are not returned by this status query. It is a customer-initiated read, not a promise of automatic notifications, pricing, execution or response time. Existing result retrieval remains «📁 ملفاتي».

## Admin review pages

The authenticated review endpoint retains its array response and maximum 50 rows per page. To read older entries, pass both `before_updated_at` (timezone-aware timestamp copied without truncation) and `before_id` (UUID) from the last item. Incomplete/invalid cursor pairs return 422; the usual admin:view permission still applies. The queue uses descending (updated_at, id), so equal timestamps do not duplicate or skip entries when reading older pages.

The admin console renders one bounded page, with older/latest navigation, retry on failure and stale-response rejection after logout or refresh. A full page may require one extra fetch to establish there are no older entries. Requests are mutable: updated records can move toward the newest page; this is not snapshot isolation. After a triage action the console refreshes to the newest queue. Revision checks remain authoritative.

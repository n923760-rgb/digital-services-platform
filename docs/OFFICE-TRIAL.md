# Private unpaid Word trial

Owner-authorized experiment, not a paid service, production launch or general
Office expert. It formats supplied text using the unchanged deterministic
[Word executor](OFFICE-DOCX.md). It does not write/rewrite content, use a model,
read uploads, edit existing DOCX files, create CVs or implement Excel/PowerPoint.
The service catalog, orders, wallet, Stars and existing file-library paths are
unchanged. No dependency, database migration or new infrastructure is required.

## Closed by default

`OFFICE_TRIAL_ENABLED=false`, `OFFICE_TRIAL_USER_IDS=[]` and
`OFFICE_TRIAL_TTL_SECONDS=900` are the committed defaults. The allowlist is a
JSON list of positive Telegram user IDs, with at most 20 entries. Do not put
tokens, customer text or actual account IDs in committed examples or chat.
Enabling the experiment requires an owner-approved isolated bot and disposable
database, using the existing minimal runtime. The bot still performs its normal
database startup/recovery checks; this is not a database-free standalone bot.
Use one poller per bot token. Do not reuse production credentials/database.
Keep `TELEGRAM_ORDERS_ENABLED`, `TELEGRAM_STARS_ENABLED` and
`SERVICE_ACTIVATION_ENABLED` false. Trial activation is not paid-service approval.

## Trial interaction

Only a private chat whose ID matches the non-bot sender is accepted. Ownership
and the current allowlist/flag are checked again for every retrieval. An
allowlisted owner can send `/word` for instructions or one message containing:

```text
/word تقرير العمل
النص المطلوب تنسيقه.

فقرة أخرى تحتوي على نص عربي وEnglish.
```

The command payload is limited to 4,000 characters, with a nonempty title on the
first line (maximum 200 characters) and a nonempty body. Blank lines separate
paragraphs; interior spacing and line breaks are preserved. Existing formatter
validation rejects invalid XML characters and submitted bidi controls. The output
is an editable `document.docx`, not PDF or generated prose. Mixed RTL/Latin text
contains invisible direction helpers; copied text is not byte-identical to input.
The formatter documentation describes this limitation and the logical comparison.

## Temporary state and truthful delivery

There is one latest file per owner in process memory. TTL defaults to 900 seconds
and may be configured from 60 to 3,600 seconds. These are engineering bounds, not
an approved retention policy or SLA. Combined retained DOCX bytes are capped at
8 MiB, and request replay tombstones are bounded to 20 distinct owners per process
lifetime. Rotating through more owners requires restarting this trial process.
All files, receipts and replay state disappear on restart; no durable recovery or
exactly-once promise is made. Do not send sensitive or confidential data.

Replaying the same Telegram message does not generate a new artifact or extend
expiry. A newer request replaces the old token. Expired/replaced messages cannot
regenerate the old request within the same process. Concurrent delivery is claimed
under a lock; a new request cannot replace a live unexpired send. Generation runs
off the event loop. Periodic/lazy cleanup removes expired cache references.

Delivery is acknowledged only using an actual returned Telegram chat/message
receipt, never a fabricated success. Network delivery has an internal 15-second
timeout, not a customer performance guarantee. Cancellation propagates. Provider
errors/timeouts leave delivery uncertain; replay does not automatically resend.
The customer may explicitly use the resend button while the file remains valid,
which sends identical cached bytes and may create a duplicate if Telegram already
accepted the earlier send. Expiry/replacement during remote I/O cannot overwrite
a newer file's receipt. Errors log sanitized codes/class names, never request text,
tokens or provider exception bodies.

Expiry revokes application retrieval only: it does not delete delivered Telegram
messages or downloaded copies. `protect_content` is a Telegram delivery option,
not secure deletion or a confidentiality guarantee. In-flight references may
retain bytes beyond cache cleanup; no immediate memory-wipe guarantee is made.

## Qualification still required

Automated tests cover pure domain behavior, actual aiogram message models and
real Dispatcher.feed_update routing with typed SDK responses over a no-network
synthetic transport. Offline journeys cover /word help/intake, the bot username
suffix, returned document receipts, message replay, uncertain sends/explicit
resend, current flag/allowlist/private-chat checks and foreign/expired/replaced
retrieval denial. They assert no invoice/refund calls or customer financial
creation in disposable PostgreSQL. This is not live Telegram evidence.
Final exact-head CI evidence belongs in PR #46, not an
assumed pass from an earlier formatter revision. A real private-bot journey,
Microsoft Word desktop/mobile opening/editing, realistic Arabic samples and owner
acceptance remain untested. The later owner instruction “ادمج و كمل بدون توقف”
authorizes engineering merge after exact-source CI and review. It does not
authorize deployment, trial activation, payments or a new AI provider.
See the [trial report](../ENGINEERING/REPORTS/2026-10-03-OFFICE_TELEGRAM_TRIAL.md)
and [Codex handoff](CODEX-HANDOFF.md).

See the [merge qualification report](../ENGINEERING/REPORTS/2026-10-03-OFFICE_MERGE_QUALIFICATION.md).

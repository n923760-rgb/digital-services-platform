# Summary startup authentication boundary

## Source and authority

Owner continued the existing implementation/review with “تمام كمل”. This is a correction to existing startup behavior, not a new feature or infrastructure addition. No growth trigger, provider choice or launch authorization is inferred.
Verified starting main 82cbcd1d46808ca4b62e7396653dc4d8ea8c9cab, tree c69d2a4199b89d3cd08fbfb29d718c818d0556b9; no open PR. Central reference remains 641e4f9e45da109257ba1f38752b94604c2e4531. Root/source/roadmap, direct/Stars/scope contracts and local Telegram/release workflows read. Repository API/external CI available; local shell/runtime NOT RUN. No subagents.

## Finding and correction

FACT: apps/telegram_bot/v0.py opened PostgreSQL and called recover_interrupted_summaries before constructing Bot and awaiting get_me. That recovery atomically changes PROCESSING orders to FAILED and requests Stars refunds. An invalid/rejected token or a Telegram connection failure therefore could follow a financial state change made by a startup that never authenticated.

Authenticate the configured bot first. Missing/malformed tokens, Telegram authentication rejection and connection timeout stop startup with a sanitized error classification; provider exception bodies are suppressed from the raised startup error. Always close a constructed bot session. After successful authentication, retain the legacy-work guard, expiry cleanup, interrupted-work recovery and billing order. Existing domain transactions, payment adapters and migration history remain unchanged.

## Validation boundary

Four failed-startup regressions cover missing token, constructor rejection, Telegram unauthorized response and transport timeout. They require zero application DB connections or billing calls and safe logs/errors; authenticated legacy-work rejection must still block purge/recovery and close both connections.
Run existing exact-source Foundation/advisory checks and review every complete changed patch/source blob before ready/merge. Final run IDs, results and source/tree identities belong in the PR body; this report does not claim a premature PASS.

## Remaining dependent work

Actual bot/payment/refund qualification, owner prices/final terms/support and privacy/retention remain unresolved. A question asks whether an isolated test bot/environment exists; no answer is invented. No token is requested in chat, no live charge/refund/deployment/production migration or activation is performed. New queues/UI/services still require an actual confirmed trigger.

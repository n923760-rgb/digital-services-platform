# Authorized Repairs and Telegram Product Direction

Date: 2026-10-01 UTC. Controller: Codex through GitHub API/MCP.
Owner instruction: continue and merge; customer product must be a Telegram bot.
Scope: independently repair DSP-014 and DSP-001; establish project authority/reference/local skills and Telegram product direction.
No local shell or real Telegram/provider environment was available.

## DSP-014 — qualified and merged

[PR #24](https://github.com/n923760-rgb/digital-services-platform/pull/24) changed only SQLAlchemy to SQLAlchemy[asyncio]>=2.0,<3 in pyproject.toml.
Task head: fb8796ed25795ebac0d6964bd424f4a8feb52cbf.
[PR CI 36883954993](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36883954993): Python, web and Compose PASS.
Python log: Ruff PASS, all migrations completed, 61 tests passed.
Squash merge: c5e4993064473802f58409f522c0735d4b9de9c7.
The previously recorded missing-greenlet failure remains historical evidence; required asyncio dependencies now install through the supported extra. Broad reproducible dependency locking (DSP-010) remains open.

## DSP-001 — qualified and merged

[PR #25](https://github.com/n923760-rgb/digital-services-platform/pull/25) adds persisted quote_revision, advances it on new inputs and each quote, binds it into the compact Telegram callback, and checks it under the workflow lock before order creation/replay.
Task head: 72c2816365166d654073b20afc6e4b009deab641.
[PR CI 36884655014](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36884655014): Python, web and Compose PASS.
Python log: Ruff PASS, migration 0013_telegram_quote_revision at head, 71 tests passed.
Squash merge: d2937cb622349ceb590e22b1e8b22a29e3241481.

Meaningful regression cases: old-price offer versus new quote; adding inputs invalidates old offer both before/after requoting; another customer's workflow rejected; same-offer replay and concurrent confirmation preserve one reservation/order; callback carries customer ID and displayed revision; callback payload fits Telegram's 64-byte bound; malformed/legacy callback rejected before order logic.
Existing workflows start at revision zero and need a fresh quote. Unversioned old buttons deliberately fail closed.
This proves the database/callback correction under the tested CI runtime; actual Telegram message/send and operator-browser staging remains NOT RUN.

## Product direction

FACT (owner decision): customer interface is a Telegram bot. Prioritize private-chat menus, text intake, quote consent, uploads where authorized, order/status, delivery and file retrieval.
The existing web app remains an operations/admin tool; a new customer website is outside current requested scope.
The financial and state core stays channel-independent. This decision does not remove existing administration or authorize new public paid services.

## Governance qualification

Root AGENTS.md links the central Master Governance, project-specific rules and six local skills.
PROJECT-SOURCES.md, one ENGINEERING/MASTER_ROADMAP.md, immutable baseline/CI history and this report preserve continuity.
README and architecture guidance distinguish Telegram customer scope, the admin web surface and historical foundation milestone.
Files are prepared/reviewed through API; no shell execution is claimed. Final documentation PR checks must be attributed to its own head, separately from the repair heads above.

## Remaining gates

DSP-001 and DSP-014 are repaired; DSP-002–DSP-013 retain the remaining code/runtime/product gaps described in the roadmap. See the roadmap for current findings.
Real payment/provider selection, refunds/reconciliation, production S3/IAM/malware controls, quota/admission, operational recovery and actual Telegram staging remain required before enabling paid customer operations.
No tokens/credentials/settings, deployment, production database, DNS or paid feature flags were changed.

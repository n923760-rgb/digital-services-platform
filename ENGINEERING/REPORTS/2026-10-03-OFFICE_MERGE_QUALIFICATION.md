# Office engineering merge qualification

Date: 2026-10-03. Repository: n923760-rgb/digital-services-platform.
Central reference: 641e4f9e45da109257ba1f38752b94604c2e4531.
Starting main: b2fb384da5bb5914619c4b76a5c6610080b05518;
tree f4d32373273473945e1719ca58032c475c6865ad.
Starting PR #46 head: 695ec6eb0aadd1b46bed5d16a456b838157f8301;
tree c2c36c0c626ce15500990e4f012887e64f628ad7.

## Authority and bounded problem

FACT: owner prioritized professional Office work and repository review, then
explicitly instructed “ادمج و كمل بدون توقف” after receiving the Office review.
This authorizes the named engineering merge after source qualification, replacing
the earlier draft-only restriction. It does not authorize deployment, payment
activation, production migrations or purchasing/choosing an AI provider.

FACT: the current implementation formats supplied text into editable Arabic DOCX
with one deterministic template; it does not write/edit uploaded documents,
analyze Excel or generate PowerPoint. Those are desired future possibilities,
not current implemented or approved outcomes. The actual-trigger/first-task
question has been asked; the selecting answer is still UNKNOWN. Do not market the
existing formatter as general professional Office intelligence.

## Source review and integration

FACT: all 15 original Office changed files, implementation, domain/adapter tests,
configuration and documents were reviewed. The starting head's Foundation push
37149313145 (Python job 111279617480) passed Ruff and 222 tests plus 33 subtests;
Foundation PR 37149315047, advisory push 37149313166 and PR 37149315020 were green.
These are historical starting-head results, not this combined candidate's proof.

FACT: main advanced through PR #45 (trial guide) and PR #47 (offline summary/Stars
acceptance). Comparing the original Office base 1d948707fa55d144d435dc971247c5c8c127a95f
to starting main found four changed paths; none overlapped Office's 15 paths.
The candidate is main's exact tree plus the reviewed Office blobs and this bounded
qualification. Its ordered commit parents are existing Office head and current
main, preserving published history without a force push.

This round changes tests/test_offline_bot_journey.py, docs/OFFICE-TRIAL.md,
docs/CODEX-HANDOFF.md, the canonical ENGINEERING/MASTER_ROADMAP.md and this report.
Original Office runtime source is preserved. PR #45/#47 documentation and all four
summary/Stars acceptance cases remain present. No new dependencies, migrations,
catalog bindings, provider calls or deployment workflows are introduced.

## Offline evidence design

Use the existing actual aiogram Dispatcher.feed_update and typed SDK transport
with disposable PostgreSQL. Extend only the synthetic transport with GetMe and
SendDocument responses; unsupported API methods still fail and no Telegram
network/download is allowed. Document responses contain the bounded input bytes'
size/MIME and actual synthetic returned chat/message IDs, not invented application
delivery success. Existing fixture refunds remain unconfirmed.

Eleven Word cases cover:
- command help/invalid/overlimit/bidi input and correct command entity length;
- bot username suffix, generation, returned owner receipt and same-message replay;
- uncertain send with retained bytes and explicit same-artifact retry;
- disabled flag, absent allowlist, group and wrong private chat denial;
- foreign allowlisted owner, exact expiry, replacement and disabled retrieval.

Each case checks that no invoice/refund is sent and no customer DB user/financial
path is entered. Existing pure domain tests cover cancellation, concurrency,
cache limits, restart and immutable/passive XML/ZIP output. This does not claim
exactly-once remote delivery or durable trial storage.

## Qualification and remaining evidence

Capabilities: repository API and existing external CI only. Local shell/tests,
renderer, real Microsoft Word and connected Telegram runtime are NOT RUN.
Final candidate Foundation Python/web/Compose and advisory workflows must pass
on the exact published SHA before merge; record the SHA/tree/run IDs and actual
counts in PR #46. No historical PASS is substituted for new source validation.

Real Telegram file receipt/resend and Microsoft Word desktop/mobile open/edit
remain NOT RUN because an approved trial environment is unavailable. Prior
six-page rendering and Python-docx roundtrip are historical formatter evidence;
they are not repeated here as fresh or native-client proof.

Office trial, paid checkout and activation remain disabled in committed defaults.
User-set prices/terms/support, real payment/refund and recovery are separate
qualification gates. No credentials, customer text or production changes belong
in this task.

## Exact next bounded action

After the explicitly authorized engineering merge, select the first actual Word
task and its professional acceptance criteria from the pending owner answer.
If generative content is selected, obtain the owner's provider/budget choice,
use a small domain adapter and evaluate real outputs before adding payment.
Otherwise qualify the existing formatter using synthetic non-sensitive text in
an approved isolated bot and native Word client when available. Do not
automatically expand to Excel, PowerPoint, CV, queues or new frameworks.

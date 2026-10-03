# Codex handoff: Word first

Repository: `n923760-rgb/digital-services-platform`.
Office work is tracked in PR #46 on `feat/office-docx-experiment`.
The latest owner instruction, “ادمج و كمل بدون توقف”, explicitly authorizes its
engineering merge after exact-source qualification. Continue that same PR until
merged; do not create overlapping work. Deployment and paid activation remain
separate, unapproved actions.
Re-fetch live main, PR head/tree and central governance before every change.
This checkpoint was prepared against main
`1d948707fa55d144d435dc971247c5c8c127a95f` and formatter parent
`589af2c83c792ac22faa41e1b2f59d3c6851eeef`; they are historical source anchors,
not assertions that the branch still has those heads.

## Authority and reading order

Read root `AGENTS.md` and `PROJECT-SOURCES.md`, the live central governance source
they identify, and `ENGINEERING/MASTER_ROADMAP.md`. Then read applicable repository
skills (file security, Telegram workflows, Arabic UI and release readiness),
`docs/SCOPE.md`, `docs/DIRECT-SUMMARY.md`, `docs/FILES.md`,
`docs/TELEGRAM-STARS.md`, `docs/OFFICE-DOCX.md`, `docs/OFFICE-TRIAL.md` and the
two Office task reports under `ENGINEERING/REPORTS/`.

The owner wants excellent paid-quality office work, prioritizing Word first,
then Excel/PowerPoint, and deferring CV/other services. The owner explicitly
authorized the current private unpaid Word trial with “تمام عادي”, then asked to
finish/save it and continue in Codex. This authorizes this bounded experiment,
not all desired future services, a provider subscription, production activation
or guaranteed quality. Actual customer demand and launch readiness remain unknown.
PR #45's trial guide and PR #47's offline bot acceptance are now merged.
Preserve both when updating Office from main. The canonical roadmap records the
later Office priority and explicit merge authority without erasing the historical
deferral. The question about the first concrete professional Office task and its
actual trigger has been asked; no answer selecting that task/provider/budget has
yet been supplied. Continuing the existing trial does not choose them implicitly.

## Implemented versus desired

- The deterministic stdlib executor produces editable DOCX from supplied text,
  using one fixed Arabic formal template. It is not generative AI or an Office expert.
- `/word` is an opt-in, allowlisted private experiment with bounded temporary
  memory, replay protection, owner/expiry checks and receipt-based delivery.
- No upload/edit workflow, model provider, CV service, Excel/PowerPoint capability,
  service-catalog registration, payment change or durable file store was added.
- The current default summary service and historical financial paths remain intact.

Read PR #46's final evidence for the exact current source head. The authored
trial report records 35 local stdlib tests and compile checks; the actual aiogram
adapter tests require the locked CI environment. The formatter's earlier visual
evidence covers six synthetic rendered pages and a Python-docx edit roundtrip,
not Microsoft Word, a real Telegram journey or universal compatibility. Do not
repeat those as new live runtime evidence.

## Next bounded step

The current API-only continuation adds real-dispatcher offline Word acceptance
to the existing synthetic SDK/disposable PostgreSQL tests. See the
[merge qualification report](../ENGINEERING/REPORTS/2026-10-03-OFFICE_MERGE_QUALIFICATION.md)
and PR #46 for the exact-head CI outcome; synthetic receipts are not actual
Telegram delivery. No trial server is currently available.

After the authorized engineering merge, qualify one private, unpaid Word journey
using an owner-approved isolated test bot/database and synthetic
non-sensitive text: help, generation, actual file receipt, resend, expiry, denied
ownership and Arabic/English Word desktop/mobile opening/editing. Record actual
versions, observations and failures. If the approved environment is unavailable,
report that concrete blocker; do not acquire credentials, deploy or repurpose a
production bot/database. Never request tokens or provider keys in chat.

Only after this evidence, propose one bounded Word-quality improvement addressing
an observed need. If content generation is wanted, the owner must select/authorize
the provider and operating budget; merely calling a paid model does not prove
accuracy. Use deterministic document checks plus rendered/real-client QA. Keep
business logic in `platform_core` and thin Telegram handlers. Default to direct
execution; do not add n8n, multiple agents, Redis, S3 or new frameworks without an
actual approved trigger. Payment and production gates stay closed.

Do not expand to Excel, PowerPoint or CV automatically. Stay with Word until the
owner's quality acceptance and the next explicit scope decision.

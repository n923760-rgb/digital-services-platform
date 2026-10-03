# Codex handoff: Word first

Repository: `n923760-rgb/digital-services-platform`.
Continue the existing draft PR #46 on `feat/office-docx-experiment`; do not start
an overlapping feature branch, merge, deploy or activate payments implicitly.
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
Draft PR #45 contains an earlier Office deferral in the roadmap. Do not silently
overwrite that PR or create another roadmap: flag reconciliation against the later
owner request during the next governed planning/review step.

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

First review the exact-head CI and full diff. Then qualify one private, unpaid
Word journey using an owner-approved isolated test bot/database and synthetic
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

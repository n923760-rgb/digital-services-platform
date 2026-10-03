# Private unpaid Word Telegram trial — 2026-10-03

## Source and actual trigger

Main checked: `1d948707fa55d144d435dc971247c5c8c127a95f`.
Existing draft PR #46 formatter parent:
`589af2c83c792ac22faa41e1b2f59d3c6851eeef`.
Central governance checked:
`641e4f9e45da109257ba1f38752b94604c2e4531`.
Root/project-source/roadmap instructions and applicable repository skills were
read before work. This is a coherent continuation of that still-unmerged formatter
branch against unchanged main, not a second competing feature/roadmap.

The explicit scope question was: “هل المحفّز صار موجود فعلاً؟ هل تريد الآن تجربة
خدمة Word داخل البوت، بدون دفع وللاختبار فقط؟” The owner's answer was “تمام عادي”.
The concrete trigger is the owner-requested unpaid bot experiment, not measured
customer demand or an inferred launch requirement. The later request to focus on
professional Office services prioritizes Word, with CV/other services deferred;
it does not make the existing formatter an expert. After asking to continue in
Codex, the owner said “تمام كمل” to finishing/saving this handoff.

PR #45's earlier roadmap deferral remains untouched. Its reconciliation against
this later request is explicitly flagged in the handoff rather than silently
editing the canonical roadmap or conflicting with that open PR.

## Changes and invariant preservation

Added a pure single-process trial module and thin aiogram adapter. Private
chat/owner and current enable flag/allowlist are checked server-side. One latest
artifact per owner, 4,000-character command payload, TTL 60..3,600 (default 900),
20 lifetime owners and 8 MiB retained DOCX bytes bound the experiment. Defaults
are closed. Replay tombstones, delivery claims and actual Telegram receipts avoid
automatic duplicate resends and false confirmation. Uncertain delivery is explicit;
manual retry may duplicate an accepted remote send. Cancellation propagates,
send attempts are internally timeout-bounded, and errors log sanitized codes or
exception classes. Expiry/replacement cannot attach an old receipt to a newer file.

No new dependency, migration, service registration, provider, durable store,
financial write or infrastructure is introduced. The formatter source and tests
remain unchanged. Existing orders/Stars/activation defaults remain false; legacy
history and existing startup/database checks are preserved. This trial cannot
be run against production merely because it does not charge. No merge, deploy,
activation, external coordination or real token use was performed.

The file-security skill led to repeated owner/expiry checks and bounded memory;
Telegram workflows led to real receipt-based acknowledgement and explicit uncertain
delivery; Arabic UI led to truthful Arabic trial copy; release-readiness led to
exact-source CI qualification and separate NOT RUN runtime gates.

## Evidence at authoring

- Python 3.12.14: 35 local stdlib Office tests PASS (18 unchanged formatter tests
  plus 17 trial domain tests); compileall for apps/packages/tests PASS.
- Real aiogram model tests were added for handler routing, disabled/unauthorized
  intake, callback ownership, exact bytes, retry, expiry, cancellation, timeout and
  sanitized logs. They were NOT RUN locally: the scratch runtime lacks locked SDK,
  database and test dependencies. Existing full CI must qualify this exact head.
- Earlier unchanged formatter evidence: six inspected synthetic rendered pages
  (mixed text, long document, punctuation and edited roundtrip). This is historical
  same-renderer evidence, not a newly run bot/Word qualification.
- Real Telegram bot, Microsoft Word desktop/mobile, production deployment,
  paid service and owner runtime acceptance: NOT RUN.

Final exact-head Foundation (Python/web/Compose) and dependency-advisory evidence
will be attached to PR #46 after the source is committed; do not infer a pass from
the formatter parent or from these local checks.

## Next and limitations

Follow `docs/CODEX-HANDOFF.md`: one approved isolated unpaid runtime/real-client
qualification first. Files and receipts are lost on restart. TTL revokes cache
retrieval, not already delivered/downloaded copies or secure memory erasure.
No durable recovery, exactly-once guarantee, SLA, writing/rewrite intelligence,
native Word universal compatibility or paid-ready claim is made. Word-quality
expansion requires a concrete bounded next decision; Excel/PowerPoint/CV remain
outside this change.

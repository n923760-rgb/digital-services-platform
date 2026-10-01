# DSP-009 — truthful intake and customer status
Baseline: dfae4f1a4b60dc56e6bb72444d803eaa60e03653, 2026-10-01. No open PRs; owner authorized continuing repairs and qualified merges without stopping.
Applied root authority, canonical roadmap, dsp-telegram-workflows and dsp-arabic-ui. Central reference previously read at 641e4f9e45da109257ba1f38752b94604c2e4531. API/external CI available; local/browser/actual Telegram NOT RUN.

FACT: greeting advertised photo/voice/file intake without corresponding review handlers. Reviews persisted triage state but customers lacked a status read and could confuse review submission with execution.
Repair: truthful text-only intake and no automatic link fetching; private fallback for unsupported media; document during active review stays out of PDF upload; remove unsupported availability promises. Add read-only latest-ten customer-owned Telegram review/order status through «📋 طلباتي». Exclude drafts/other channels, never return descriptions or internal reasons, preserve financial behavior and flags.
Review files: new core/customer adapter status modules, bot main/custom request copy, five PostgreSQL/adapter tests, custom request contract, canonical roadmap and this report. No migration/dependency/provider or financial writes.
Validation at preparation: external exact-head CI pending; local commands NOT RUN. Associated PR records exact head/run/test totals and actual merge state. Previous PR #27 passed 90 tests in run 36902438700.
Limits: user pulls status; automatic notifications, actual Telegram delivery, response SLA, quotes and execution remain unqualified. Customer-visible decline conveys outcome without exposing operator-only reason. Browser rendering/accessibility NOT RUN.
Next authorized bounded diagnosis: DSP-008 long PDF jobs and worker health, followed by DSP-006/007 admin proxy/login throttling.

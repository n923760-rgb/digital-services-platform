---
name: dsp-arabic-ui
description: Review Arabic RTL admin and Telegram product copy, mobile layout, accessibility and interaction states.
---

# dsp-arabic-ui

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Read apps/web/app/layout.tsx, page.tsx, admin/page.tsx and customer-facing Telegram copy. Derive supported features from handlers/registry rather than aspirational text.
2. Trace state ownership for login/expiry/logout, fetch errors, loading/empty states, service revision conflicts and triage. Prevent stale success/errors or duplicate submissions; preserve server-side permissions and consent boundaries.
3. When a browser is available, capture the exact source/artifact and test 320/360/390px plus desktop, Arabic long text, RTL with LTR identifiers, 200% zoom, keyboard/focus, input labels, error announcements and touch targets.
4. Check padding/min-width/table overflow, readable statuses/currency and explicit pending/error recovery. Keep developer details out of customer flows unless needed for an administrator's decision.
5. Product copy must match available intake and notification/SLA capability. Do not imply voice/photo processing, paid service availability or guaranteed response while those flows are absent.
6. For authorized UI edits run affected TypeScript/build checks and meaningful browser journeys. Without browser execution report potential layout issues as INFERENCE and rendering/accessibility NOT RUN; don't fabricate screenshots or performance.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

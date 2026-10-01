# Digital Services Platform — Agent Instructions

## Authority and canonical source

Current explicit owner instructions take priority. Apply this repository's AGENTS.md, the referenced Master Engineering System, and applicable domain contracts. Skills are methods, not authorization.
Canonical repository: https://github.com/n923760-rgb/digital-services-platform
Official/default branch: main. Reverify branch, live HEAD, open/conflicting PRs and scoped instructions before every repository-dependent task. Historical SHAs in reports are not current-source claims.

## Primary reusable reference

- Master rules: https://github.com/n923760-rgb/engineering-governance/blob/main/MASTER_GOVERNANCE.md
- Navigation: https://github.com/n923760-rgb/engineering-governance/blob/main/GLOBAL_REFERENCE.md
- Project adoption: https://github.com/n923760-rgb/engineering-governance/blob/main/docs/NEW_PROJECT_ADOPTION_PROMPT.md
- Reference reviewed for initial adoption: commit 641e4f9e45da109257ba1f38752b94604c2e4531.
Read the reference when available, compare later rule changes before applying them, and record the revision used. Its latest main may contain unreleased changes. Never claim to have read a remote document you could not retrieve. If unavailable, use the repository's verified local instructions, report the unavailable reference, and stop only work that actually depends on missing authority.
Keep this product's facts here; the central reference remains project-agnostic.

## Session and engineering records

Declare verified execution capabilities: CLI/lab, repository API, external CI, browser/runtime, or advisory only. Do not infer shell/runtime access from repository write access.
Read PROJECT-SOURCES.md and ENGINEERING/MASTER_ROADMAP.md after live-source verification.
One canonical roadmap: ENGINEERING/MASTER_ROADMAP.md.
Reports: ENGINEERING/REPORTS/. Sanitized evidence indexes: ENGINEERING/EVIDENCE/.
A new/re-baseline first round is read-only and produces a Master Engineering Baseline Report before implementation. Review/audit/diagnosis alone does not authorize source changes. Prior explicit owner implementation instructions persist; do not ask again for already authorized ordinary work.

## Owner-approved product direction

The owner confirmed on 2026-10-01 that the customer product is a Telegram bot. Prioritize private Telegram journeys, menus, intake, consent, fulfillment and customer status. The existing web app is an operations/admin surface; a separate customer website is not in the requested scope. Preserve the channel-independent domain core and server-side authorization. Do not remove working admin tooling just because the customer channel is Telegram.

## Product boundaries and invariants

- Telegram/HTTP/web are adapters. Application state, prices, wallet, orders and job transitions belong in platform_core and PostgreSQL.
- SAR amounts remain integer halalas; owner selected direct Telegram Stars payments per order. XTR amounts are whole Stars in separate invoices/charge history and order snapshots; never reinterpret or convert SAR ledger history. Wallet entries are the source of financial truth; lock the wallet row for writes. Preserve idempotency, append-only history and one reserve/settlement per order.
- Application delivery recognition occurs only after actual delivery receipt. Telegram collects XTR before processing; preserve its paid charge separately and refund through Telegram on permanent fulfillment failure. SAR capture remains after delivery. Terminal processing/delivery failure releases held funds. Do not equate ledger RELEASE with a provider refund.
- Bind customer confirmation to the exact offered price and inputs. Follow the live roadmap for DSP-001 qualification; versioned callbacks are a server-enforced consent boundary.
- Enforce owner/file/expiry and admin permissions server side. React visibility is not authorization.
- Production worker PDF parsing must remain in the no-network sandbox with limits and no application secrets. Signature checks/active-content rejection are not malware clearance.
- TELEGRAM_ORDERS_ENABLED and SERVICE_ACTIVATION_ENABLED default off. Do not enable paid operations without an authorized, qualified launch task.
- S3Mock and demonstration credentials are development/CI only.
- At adoption no payment adapter existed. Current selected integration is direct Telegram Stars (docs/TELEGRAM-STARS.md), gated off pending live qualification. Payment fixtures cannot fund customers or prove real Stars charges/refunds.
- The Digital Store remains independent. Do not integrate its wallet/database by assumption.
Read README.md and docs/CORE-001.md, PAYMENTS.md, FILES.md, SERVICE-REGISTRY.md, CUSTOM-REQUESTS.md and BACKUP-RECOVERY.md for the affected subsystem.

## Change and Git policy

Use one bounded confirmed problem or coherent feature per branch/PR, based on live main. Prefer an isolated worktree when shell access exists; in API mode use a dedicated branch and review the full diff.
No ordinary direct main writes, force pushes, published-history rewrite or tag moves.
Do not combine audit findings into one implementation PR or perform opportunistic refactoring.
Before a final commit: review every file/full diff, scope, secrets and relevant validation. API-only sessions must perform the closest repository-state/diff equivalent and identify unavailable shell checks.
Open a reviewable PR; leave unqualified changes as draft. Do not merge without explicit current owner authority.

## Validation

Required toolchain derived from source: Python 3.12.14, Node 22.23.3, PostgreSQL 16, Redis, Docker Compose V2 and Linux PDF resource controls.
Python setup: use the exact hashed build/dev requirements and no-dependency editable install in docs/DEPENDENCIES.md; run scripts/verify_dependency_artifacts.py and pip check. Set TEST_REDIS_URL to isolated Redis for limiter tests.
Static check: ruff check apps packages tests migrations scripts.
Database/test checks: alembic upgrade head; pytest -q; alembic current.
Run database tests only against a dedicated disposable migrated PostgreSQL database; financial tests preserve history.
Web checks in apps/web: npm ci; npm audit --omit=dev; npm run typecheck; npm run build; isolated tests/browser npm ci and Chromium checks in ci.yml (synthetic API, not live-backend proof). Review lock/fingerprint changes only in a bounded dependency task; never bypass hash validation or use floating installs during ordinary work.
Compose qualification follows .github/workflows/ci.yml in an isolated test deployment. Never run infrastructure/backup/restore_smoke.sh against production: it writes a seed row to its configured source DB even before creating its restore target.
Select the smallest meaningful proof, then affected regressions. Do not claim local PASS from historical CI or a different SHA. Documentation-only edits need link/schema/diff review, not new tests that mirror prose.
Foundation CI job names: python, web, compose. Dependency advisory audit has job audit; qualify both exact-source workflows. See docs/DEPENDENCY-AUDIT.md for coverage and unavailable-scan handling. Reverify actual run/check names and exact source; protection is not assumed.
Use PASS / FAIL / BLOCKED / UNKNOWN / NOT RUN / SKIPPED truthfully.

## Relevant local skills

Skills under .agents/skills/ are repository workflows, not installed external plugins. Read the relevant SKILL.md before using it:
- dsp-financial-safety: wallet/order/payment/settlement review.
- dsp-telegram-workflows: customer flows, quote consent, callbacks and retries.
- dsp-file-security: uploads, ownership, PDF isolation and retention.
- dsp-admin-security: sessions, permissions, Origin, proxy and throttling.
- dsp-arabic-ui: RTL, mobile layout, keyboard/accessibility and truthful messages.
- dsp-release-readiness: exact-source CI, production prerequisites and recovery.
Use only skills relevant to the bounded task. Skill availability does not prove browser, provider or lab capability.

## Protected actions and stop conditions

Merge, tag, release, signing, production deployment, DNS, protected production migrations, credential changes, destructive/billing actions and repository protection/settings changes require explicit owner authorization for that action.
Never commit secrets, .env, provider tokens, signing material, test/production credentials, customer files or raw private descriptions.
Stop dependent mutation on uncertain identity/source, conflicting current work, missing authority, secret exposure, unclear production impact or unavailable required validation. Continue independent authorized work and report the exact limitation.
Reports identify source, scope, files, causal evidence, validation actually run, external run IDs, unresolved risks and exact next task. Do not fabricate performance, visual or production safety claims.

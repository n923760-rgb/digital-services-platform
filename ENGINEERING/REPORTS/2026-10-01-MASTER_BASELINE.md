# MASTER ENGINEERING BASELINE REPORT

Date: 2026-10-01 UTC
Controller: Codex through GitHub API/MCP
Repository: n923760-rgb/digital-services-platform
Official branch used for this baseline: main (live default branch; no separate release branch designation found)
Verified source: b90dccda7175b7f77dfe8cba4b3bc573d283a299
Reference: engineering-governance at 641e4f9e45da109257ba1f38752b94604c2e4531
Round: READ-ONLY MASTER RE-BASELINE, completed before governance authoring.
Execution: repository API reading available; Git/shell, Docker, PostgreSQL, browser and live-provider execution unavailable in this session.

## خلاصة المراجعة

المشروع أساس تقني لمنصة خدمات سعودية، وليس منصة جاهزة لاستقبال طلبات مدفوعة. توجد نواة مالية ومعالجة PDF معزولة ولوحة تشغيل عربية وطلبات نصية للمراجعة. الدفع الحقيقي، تشغيل خدمات متعددة، والتأهيل الإنتاجي ما زالت غير مكتملة. آخر CI على المصدر المحدد ناجح، لكنه لا يثبت تشغيل تيليجرام الحقيقي أو سلامة تجربة الجوال أو التعافي الإنتاجي.

الأولوية: تأهيل تعليمات المشروع وبيئة الاختبار، ثم تشخيص تأكيد عروض السعر القديمة وإصلاحه في مهمة مستقلة. تبقى الخدمات المدفوعة والرفع العام معطّلة أثناء استكمال الدفع، حماية الملفات، التعافي، والاختبارات التشغيلية.

## A. PROJECT IDENTITY

FACT: Python package digital-services-platform and web package digital-services-platform-web both declare version 0.1.0. Saudi-facing SAR wallet and Arabic RTL interface. Brand/domain are provisional; the Digital Store is a separate product. No homepage URL or release is registered in repository metadata.
UNKNOWN: production domain, actual running deployment, intended traffic, approved full V1 business specification, prices, provider agreements and revenue/cost assumptions. Repository docs refer to an approved specification without containing its full business requirements. Profitability and competitive differentiation cannot be established from source alone.

## B. LIVE REPOSITORY STATE

FACT: public repository, default branch main, branch API reports protected=false, rulesets API returns an empty list. Source SHA above verified using branches/main. Tree response was not truncated. All nonempty text files were retrieved; source-focused review concentrated on domain, adapters, configuration, migrations and UI. Empty marker/package files were listed.
FACT: 22 returned PRs are closed and merged; no open PR among this complete set (repository metadata open_issues_count=0). Latest merge: PR #22, audited custom-request triage, 2026-09-19. No releases returned.
UNKNOWN: organisation-level policy outside returned APIs, deployed state, unpublished local work.
Main protection changes are a separate owner-protected repository-settings decision.

## C. CURRENT CANONICAL SOURCE

Use the current live main on this repository for new work. b90dccda7175b7f77dfe8cba4b3bc573d283a299 is historical audit attribution, not a permanent current-HEAD claim.
The central governance repository supplies reusable rules; this project's own source supplies product facts. Never copy another project's credentials, infrastructure, SHAs or runtime assumptions.

## D. EXISTING REPOSITORY GOVERNANCE

FACT: no AGENTS.md, scoped AGENTS.md, PROJECT-SOURCES.md, ENGINEERING/MASTER_ROADMAP.md, or local skills were present in the baseline tree.
Existing contracts: README and docs/ARCHITECTURE.md, CORE-001.md, FILES.md, PAYMENTS.md, SERVICE-REGISTRY.md, CUSTOM-REQUESTS.md, BACKUP-RECOVERY.md.
FACT: architecture documentation still describes an empty business migration and no dashboard; later source implements both. README's introduction also understates the available review intake. Preserve those historical milestone facts but distinguish them from current capability.

## E. BUILD / RELEASE CONFIGURATION

FACT: Python >=3.12, setuptools, FastAPI, asyncpg, aiogram, ARQ, Alembic, boto3, pypdf and Argon2. Web: Node 22 in CI/Docker, Next.js 15, React 19, TypeScript.
FACT: 12 sequential Alembic revisions ending at 0012_custom_request_triage. Docker Compose includes PostgreSQL 16, Redis 7, development S3Mock, migrations, backup, API, worker, PDF sandbox, web, Caddy, and an optional Telegram profile.
FACT: Python, JavaScript and base-image versions are ranges/mutable tags; no dependency lockfile is in the tree. Web uses npm install rather than npm ci.
No release pipeline, image publication, production override or frozen production artifact record found. HTTPS is configured by Caddy when a domain is supplied.
Local build/test execution in this session: NOT RUN.

## F. APPLICATION / SYSTEM ARCHITECTURE MAP

Private Telegram messages -> aiogram handlers -> platform_core application functions -> PostgreSQL durable state.
Admin browser -> Caddy -> FastAPI -> server-side session/permission check -> platform_core or bounded read SQL.
PostgreSQL PENDING jobs -> periodic ARQ dispatch -> worker -> private-volume PDF sandbox -> S3 output -> delivery_outbox -> Telegram receipt -> ledger capture.
PostgreSQL stores metadata and financial history; S3 stores customer bytes. Redis transports scheduled work and stores login limits, not the authoritative wallet.
FACT: only merge-pdf is an executable registered processor; registering ai/manual/template/hybrid types does not implement those processors.

## G. AUTHORITATIVE STATE / OWNERSHIP MAP

| State | Owner | Durable rule |
| --- | --- | --- |
| Available/held funds | wallet_transactions + wallet row lock | integer halalas; immutable entries; per-wallet idempotency; unique reservation/settlement per order |
| Order price/input | orders + order_files | confirmation transaction snapshots price and reserves funds |
| Job execution | jobs + job_attempts | row-locked claims; bounded attempts; stale recovery |
| Delivery/charging | delivery_outbox + external receipt | capture after successful delivery; terminal failure releases funds |
| File access/retention | files + owner user + S3 | ownership, readiness, expiry and size checks |
| Telegram quote | telegram_workflows | mutable quoted price and attachments; stale button gap below |
| Registry | services/service_categories | revision conflicts, default disabled, audited owner writes |
| Admin access | admins/admin_sessions/role_permissions | Argon2id; hashed opaque tokens; expiry/revocation; server checks |
| Custom requests | custom_service_requests | draft/message idempotency; assigned review; revision and audit |

INFERENCE: transaction design provides a sound internal foundation, but does not prove production consistency under every crash/network/locking scenario.

## H. FEATURE / SUBSYSTEM INVENTORY

Implemented internally: wallet credit/reservation/capture/release; payment intent/event accounting; durable jobs; PDF merge; delivery retries; completed-file retrieval; registry/category administration; role-limited operations dashboard; text request intake and owner triage.
Off by default: Telegram paid-order workflow and new service activation.
Missing/incomplete by design: real payment adapter/checkout/webhook, refunds/reconciliation operations, AI/manual fulfillment, custom-request quote-to-order conversion, customer status/decline notifications, customer web ordering, store URL/integration.
Do not advertise disabled/internal features as ready services.

## I. PLATFORM / RUNTIME CONTRACT

Current surfaces: Arabic browser admin/placeholder home, private Telegram bot, Linux Docker service runtime.
PDF resource controls use Linux resource/signal facilities. This does not establish native Windows runtime support.
Required runtime evidence: separate-account authorization; mobile/desktop admin; actual Telegram sends and restarts; real S3 credentials/expiry; payment sandbox verification; worker crashes; disk/storage outages; recovery.
Actual deployment topology and supported browser/device matrix: UNKNOWN.

## J. TEST INVENTORY

FACT: 17 Python test files, 53 statically named test functions, some parametrized. This is a source inventory, not a collected/passed test count.
Coverage present: ledger idempotency and contention; order rollback/snapshot; job claim/exhaustion/stale recovery; payment signature boundary/replay; owner/operator sessions/permissions/Origin; PDF safety/sandbox; file ownership/expiry; Telegram catalog callbacks/workflow; service registration/revision; custom request intake/triage; readiness and backup freshness.
Integration fixtures connect to DATABASE_URL and persist financial history. Only use a migrated disposable PostgreSQL database.
No browser E2E suite, real Telegram/payment-provider test, performance suite, or disaster-recovery proof found. Existing repricing test refreshes the quote and confirms by workflow ID; it does not distinguish old and new buttons.

## K. CI / AUTOMATION INVENTORY

Historical exact-source CI: PASS, externally executed by GitHub Actions, not by this controller.
[Run 35433969664](https://github.com/n923760-rgb/digital-services-platform/actions/runs/35433969664), head b90dccda7175b7f77dfe8cba4b3bc573d283a299, completed success.
Jobs verified via jobs API: python PASS; web PASS; compose PASS.
Python steps include packaging, Ruff, migrated PostgreSQL pytest, alembic current.
Web includes TypeScript and Next build.
Compose includes configuration/sandbox boundaries, boot, backup freshness, restore smoke, worker-to-PDF-sandbox smoke and health probes.
This review did not rerun CI. Full console logs, collected test totals and artifact contents were not retrieved.
No dependency vulnerability scan, browser E2E or release artifact identity gate found.

## L. SECURITY / PRIVACY BOUNDARIES

FACT: admin HttpOnly/Secure/SameSite strict cookie, hashed session token, Origin checks and database roles/permissions; immutable audit events; no unauthenticated wallet write or payment webhook.
FACT: file ownership and completed-order checks are server side. PDF sandbox has no network, runs non-root/read-only with dropped capabilities and resource limits, rejects active PDF content, and is not given application secrets.
FACT: .env is ignored; bundled credential values are demonstration settings. Do not use them in production.
FACT: Compose app database credentials use the same configured PostgreSQL identity as bootstrap/migrations/backup. No separate least-privilege production role contract is implemented here.
UNKNOWN: production IAM, secret store, malware scanning, host hardening, log redaction, deletion/privacy process and Saudi privacy/commercial policy readiness.
Do not include customer descriptions, tokens, credentials or file bytes in public evidence.

## M. CURRENT EVIDENCE COVERAGE

| Claim | Result | Limit |
| --- | --- | --- |
| Repository identity, source and public policy reads | PASS | point-in-time API evidence |
| Historical exact-source CI jobs | PASS | external run above |
| Local lint/build/test/Compose | NOT RUN | no shell/runtime tools |
| Real Telegram/provider/S3 staging | NOT RUN | no live integration exercised |
| Mobile/accessibility rendering | NOT RUN | no browser |
| Production backup restore/performance | UNKNOWN | repository documents prerequisites, not operational proof |
| Release readiness | BLOCKED | incomplete integration and qualification |

No production security or runtime PASS is inferred from static inspection.

## N. RISK / GAP LEDGER

Priority is engineering order, not a CVSS score. FACT describes code/configuration; predicted runtime impact remains INFERENCE until reproduced.

### DSP-001 — P1 — stale confirmation accepts a newer quote
FACT: [quote button](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/telegram_bot/pdf_workflow.py#L52) encodes only workflow ID. [quote persistence](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/packages/python/platform_core/telegram_workflow.py#L137) overwrites the quoted price on that same workflow; confirmation reads its current files/price, not a quote version.
Trigger: display quote A -> change service price or append inputs -> display quote B -> press the still-visible button on A. INFERENCE: confirmation accepts B although the clicked message describes A. Repeated buttons are not proof of consent to the newest price.
Required diagnosis: deterministic PostgreSQL and callback test, with both messages preserved, changed price and changed inputs. Proposed bounded remedy: immutable quote identity/revision bound to button, files and price; invalidate old confirmation. Runtime reproduction NOT RUN. Block paid-order enablement until resolved.

### DSP-002 — P1 release gap — no live payment or refund/reconciliation path
FACT: docs/PAYMENTS.md and router inventory show no checkout/public webhook/live provider adapter. Test HMAC is a fixture.
Required: owner selects provider; authenticated top-up initiation; raw-body signature/account/amount/status validation; replay/out-of-order tests; refunds/disputes/reconciliation and failure operations. Expected incomplete milestone, not a claim of a payment exploit.

### DSP-003 — P1 release gap — production storage and recovery unqualified
FACT: Compose uses development S3Mock and same-host PostgreSQL snapshots. Docs require production S3 and encrypted off-host recovery. UNKNOWN: external controls actually deployed.
Required: production override, separate least-privilege DB roles/IAM, customer-file protection and malware policy, encrypted independent backups including S3 objects, recorded restore and financial reconciliation. Do not enable public uploads based on health checks alone.

### DSP-004 — P2 — uploads persist before the attachment limit is checked
FACT: [upload adapter](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/telegram_bot/pdf_workflow.py) calls upload_file before attach_pdf validates max_files. Active workflow existence alone passes preflight. Rejected eleventh/later files can therefore be stored without an attached workflow input. No per-user upload-byte/request quota appears.
INFERENCE: with upload flag enabled, repeated rejected uploads consume storage until retention cleanup. Required: quota/admission control, attach-race handling and cleanup of unreferenced uploads; test concurrent last-slot uploads and cancellation during upload. Currently disabled externally by default.

### DSP-005 — P2 — aggregate PDF size checked after input materialization
FACT: [processor](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/packages/python/platform_core/processors.py#L29) loads all selected input bytes before sandbox/client checks the 40 MiB aggregate bound. With ten default-limit files, up to roughly 200 MiB can be materialized before rejection, plus copies.
Required: metadata total admission check and bounded aggregate reading, then test memory under slow storage/maximum inputs. Actual memory/performance NOT RUN.

### DSP-006 — P2 — proxy identity and login throttling need qualification
FACT: Compose trusts forwarded headers only from 127.0.0.1; Caddy is a separate container. [login](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/api/admin.py#L150) keys limits by request.client.host + username.
INFERENCE: default deployment sees Caddy's peer IP for different clients, creating a shared per-username limit and allowing one client to lock out another for the window. Required: two-client proxy test; deliberately scoped trusted proxy configuration, never blanket trust untrusted headers. There is also no separate source-wide limiter against many username attempts.

### DSP-007 — P2 — login limit increment/expiry is not atomic
FACT: [login](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/api/admin.py#L155) uses separate INCR and EXPIRE calls. If first increment succeeds and expiry fails, a retry can retain a non-expiring key.
Required: atomic Redis script/transaction with timeout semantics; fault-injection regression. Runtime Redis failure NOT RUN.

### DSP-008 — P2 — PDF heartbeat follows blocking processing
FACT: [sandbox loop](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/packages/python/platform_core/pdf_sandbox.py) touches heartbeat after scanning/processing; parser can wait up to 75 seconds. Compose requires heartbeat <10 seconds with 10-second checks and five retries.
INFERENCE: long valid processing can mark a working sandbox unhealthy. Required: bounded long-job runtime diagnosis; liveness distinct from processing duration; restart/outage tests. No production outage claimed.

### DSP-009 — P2 product gap — promise and actual intake disagree
FACT: bot /start invites images/files/links/voice, while custom-request intake is text-only; document messages enter the gated PDF flow, and there are no photo/voice intake handlers. No customer decline/review notification follows owner triage.
Impact: users may send unsupported media or wait without visible progress.
Required: clear supported input messaging now; later separately scoped attachment/notification/status flow. Customer response SLA is an owner decision.

### DSP-010 — P2 release gap — reproducibility and supply-chain evidence missing
FACT: no lockfiles, range dependencies/mutable Docker tags, npm install, no vulnerability scan in CI.
Required: resolve/lock dependencies and production images in a separate reproducibility task, retain artifact hashes/SBOM as applicable, qualify updates and chosen versions. No specific CVE or compromised dependency is asserted.

### DSP-011 — P2 — narrow-screen layout needs correction/verification
FACT: [body](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/web/app/layout.tsx#L6) uses 3rem margins; [triage input](https://github.com/n923760-rgb/digital-services-platform/blob/b90dccda7175b7f77dfe8cba4b3bc573d283a299/apps/web/app/admin/page.tsx#L231) has minWidth 260 inside a padded card. INFERENCE: a 320–360px viewport can exceed available card width.
Required: browser evidence at 320/360/390px, zoom and keyboard focus; responsive spacing and labeled triage input; pending submissions, network errors and expiry behavior. Static inspection cannot certify overflow/accessibility.

### DSP-012 — P2 governance gap — unprotected main and no engineering authority
FACT: branch protected=false, no rulesets returned, no AGENTS/engineering roadmap in baseline. Required: proposed governance files and separately authorized GitHub protection/check settings.
Settings are intentionally not changed by this audit.

### DSP-013 — P3 — documentation and operational scalability
FACT: architecture milestone claims lag source; bounded dashboard endpoints have no pagination; API opens new DB connections for identity, permission and query separately; custom-request records have no lifecycle retention policy in source.
INFERENCE: stale guidance, hidden older requests and DB connection pressure will matter with growth.
Required: doc reconciliation, product-specific pagination/retention decisions, measured connection pool/query planning in separate tasks. No load threshold is invented.

## O. PROPOSED REPOSITORY AUTHORITY MODEL

Current explicit owner instructions -> root AGENTS.md -> referenced Master Governance -> scoped domain contracts -> task/result evidence.
Local skills guide methods; they cannot grant merge, production or secret authority.
One coherent problem/feature per branch and PR. Preserve published history. No ordinary direct main writes.

## P. PROPOSED PROJECT-SOURCES MODEL

Root PROJECT-SOURCES.md links central reference, local authority, contracts, canonical roadmap, reports/evidence, local skills and lab requirements. It stores stable resource locations, not live tokens/IPs/temporary state.
Central reference stays project-agnostic; adopt it per project rather than claiming automatic global installation.

## Q. PROPOSED MASTER ENGINEERING ROADMAP STATE FOR /ENGINEERING/MASTER_ROADMAP.md

Proposed initial gates:
1. repository authority and a qualified test lab;
2. stale-quote consent diagnosis/remediation;
3. upload/resource, proxy/throttle and sandbox-liveness tasks separately;
4. owner-selected payment integration and reconciliation;
5. production storage/security/privacy/recovery qualification;
6. Telegram/browser E2E, reliability and load evidence;
7. exact-source/artifact candidate and owner release decision.
No roadmap was written during this read-only baseline. A later authorized governance authoring round may instantiate this state.

## R. ENGINEERING LAB PLAN

Use a disposable nonproduction Linux test environment with Git/worktrees, Docker Compose, isolated PostgreSQL/Redis/S3Mock and a browser. Reproduce existing deterministic tests first.
Add approved staging for Telegram/payment/production-S3 boundaries; credentials stay outside Git.
Host provider, sizing and spend remain owner decisions. No infrastructure purchase or deployment performed.

## S. REQUIRED LAB TOOLCHAIN FOR THIS EXACT REPOSITORY

Git, Python 3.12, pip/build, Ruff/pytest/pytest-asyncio, PostgreSQL 16/client tools, Node 22/npm/TypeScript, Docker+Compose V2, Caddy, browser automation where available.
Commands from current repo: pip install -e '.[dev]'; ruff check apps packages tests migrations; alembic upgrade head; pytest -q; alembic current; in apps/web npm install, npm run typecheck, npm run build.
Full integration tests and restore_smoke require disposable databases. restore_smoke inserts into its configured source DB before creating a restore target: never point it at production.

## T. CONTROLLER / EXECUTOR OPERATING MODEL

Controller verifies live source/scope, traces owners, selects deterministic proof and reviews complete diff/evidence.
Executor may be a qualified CLI/lab/CI runner; receives one bounded task with source identity, allowed files, checks and stop conditions.
This baseline used one controller; no additional agents were spawned. Roles do not imply delegation or new permission.

## U. EVIDENCE / REPORT STORAGE MODEL

Canonical roadmap ENGINEERING/MASTER_ROADMAP.md; detailed reports ENGINEERING/REPORTS/; sanitized indexes ENGINEERING/EVIDENCE/.
Evidence records source SHA, external run IDs, conditions and truthful result vocabulary. Do not upload customer files/secrets.
This report is the completed read-only deliverable; persisting it in a later authorized documentation PR does not retroactively turn the audit into an implementation round.

## V. OWNER-PROTECTED DECISIONS

Merge, tags/releases, deployment, protected production migration, DNS, credentials, signing, destructive operations and repository protection changes need explicit owner scope.
Open product decisions: branding/domain, provider, approved launch service/pricing/SLA, refunds, privacy/retention, budget and production target.
The user's prior request authorizes preparing project AGENTS.md/reference integration; it does not authorize release or production enablement.

## W. EXACT NEXT ENGINEERING ROUND

First: a coherent governance documentation PR implementing AGENTS.md, resource map, canonical roadmap/report/evidence and relevant local skill instructions under the owner's existing request.
Then: one independent DSP-001 task in a qualified disposable PostgreSQL environment. Verify old/new quote callback behavior before changing code; add meaningful consent regression and review affected Telegram paths.
No source fixes, settings changes, merges or deployment were performed during this baseline.

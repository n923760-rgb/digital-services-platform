---
name: dsp-release-readiness
description: Assess exact-source CI, operational prerequisites, provider/storage recovery and production release readiness.
---

# dsp-release-readiness

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Verify live main, relevant PRs, source SHA, complete diff, actual CI check names/results and release state. Read README, Compose/Dockerfiles, CI and backup/payment/file contracts.
2. Separate historical CI, local/lab execution, browser/Telegram/provider staging and production evidence. Select existing deterministic checks first; don't rerun green CI as an experiment.
3. Check locked/resolved dependencies, production image/artifact identity, provider signature/account/reconciliation, production S3/IAM, quotas/malware controls, secrets/TLS, least-privilege DB roles, monitoring and rollback.
4. Recovery must cover both PostgreSQL financial state and referenced S3 objects, independent encrypted off-host copies, restoration time/data loss and post-restore provider-event reconciliation.
5. restore_smoke.sh requires a disposable source DB: it inserts a marker there even when restore uses a new DB. Never use production just to obtain a smoke PASS.
6. Produce a release-blocker matrix tied to one exact source and artifact/deployment hash. Green CI cannot approve merge/deploy/activation; report owner decisions and missing evidence without performing protected actions.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

---
name: dsp-admin-security
description: Review FastAPI admin authentication, authorization, browser Origin, cookies, proxy identity and Redis throttling.
---

# dsp-admin-security

Read root AGENTS.md and PROJECT-SOURCES.md, then the canonical roadmap and the relevant contracts. Verify repository/branch/live HEAD and available execution capabilities. Current owner scope controls read-only versus implementation work. One confirmed problem or coherent feature per branch/PR; no unrelated fixes. Preserve secrets and use sanitized evidence.

## Workflow

1. Read apps/api/admin.py, main.py, admin_auth.py, admin_bootstrap.py, config.py, admin/security migrations, Caddy and Compose.
2. Enumerate read/write routes, identity and permission dependencies, disabled-account/session expiry/revocation, Argon2, cookie flags/path, Origin checks and atomic audit writes. UI role visibility never replaces server permission.
3. Verify login-limit keys, source trust, username/source-wide controls, INCR/expiry atomicity and Redis fail-closed behavior. Test two independent clients behind the actual proxy and malicious forwarded headers; never trust all external forwarded headers by convenience.
4. Use disposable migrated PostgreSQL and tests/test_admin_security.py plus relevant registry/triage tests. Cover unauthenticated and OPERATOR/OWNER behavior, forged Origin, replay/expiry, write conflicts and limiter outages.
5. Browser/proxy behavior requires actual browser/Compose evidence; unit HTTP fixtures alone are insufficient. Avoid public probing or changing real credentials/settings under an audit.
6. Produce exact-source route/permission findings and bounded remediation proof. Record unavailable runtime NOT RUN; no unproven "secure" verdict.

## Deliverable

An attributable finding/result with FACT / INFERENCE / UNKNOWN / BLOCKED classification, actual PASS / FAIL / NOT RUN / SKIPPED evidence, exact source and next bounded action. Update the one canonical roadmap only when mutation is authorized; never create a competing plan.

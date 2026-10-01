# Expired-file cleanup retry fairness

أثبت الاختبار أن تعذّر حذف أقدم ١٠٠ ملف يمنع الوصول إلى الملفات المنتهية التالية. الإصلاح يرتب الانتظار حسب تاريخ الانتهاء للملف الجديد ووقت آخر محاولة للملف المعاد، مع إبقاء مدة الاحتفاظ والجدول وحد الدفعة كما هي.

## Authority and source

Owner authorized continued bounded implementation and merging of qualified changes. Repository/API and external CI capabilities only; local commands NOT RUN. Verified base main: dad592bc5a0e65f2c84c1381f75984001e50d27c, tree 70748ffe41df8a18d1d5794832f8f4f7ab8a6155. No competing open PR existed. Root AGENTS.md, PROJECT-SOURCES.md, canonical roadmap, file/recovery contracts and file-security/release-readiness skills were read. Central reference main remains 641e4f9e45da109257ba1f38752b94604c2e4531.

## Confirmed cause and reproduction

FACT: selection by retention_until always reselects the same 100 oldest failed objects. Per-object exception isolation alone cannot advance past a failed full batch.
Regression-only source 9423ce7d3191555883aa5639df9b338b83a18ef6, Foundation push run [36937601796](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36937601796), python job 110621419722: FAIL at the second cleanup result (0 >= 1); 108 existing tests PASS and one new regression FAIL. Disposable PostgreSQL and synthetic object storage; no production/customer data.

## Bounded correction

Migration 0015_file_cleanup_retry adds nullable cleanup_attempted_at and a partial expression queue index. The existing expired/non-EXPIRED filter, 100-row limit and FOR UPDATE SKIP LOCKED remain. Ordering is COALESCE(cleanup_attempted_at, retention_until), then UUID. Updating attempt time in the same transaction rotates committed failed attempts behind older waiting work while preserving expiry/status. Fresh expiries cannot automatically overtake older retries, unlike sorting all never-attempted rows first.
Only existing provider OSError isolation remains; programming/database errors and shutdown cancellation propagate and roll back metadata/attempt timestamps. Object deletes remain idempotent because provider effects cannot be rolled back.

Files: platform_core/files.py, migration 0015, tests/test_files.py, docs/FILES.md, this report and the canonical roadmap. No schedule/retention/resource-policy, wallet/order, dependency, customer-facing flow or launch-flag change.

## Qualification plan and evidence boundary

The final PR [#39](https://github.com/n923760-rgb/digital-services-platform/pull/39) body and exact-source run logs are authoritative for final qualification; this is a preparation snapshot, not a premature PASS claim.
Required proof: new full-batch regression (later healthy progress, retry retention/recovery, fresh-expiry ordering), unexpected-failure transaction rollback, existing ownership/expiry/provider isolation regressions, migrated disposable PostgreSQL suite, Foundation python/web/compose and dependency advisory audit. Final full diff and source/run identity reviewed before ready/merge.

Production provider/lifecycle/IAM, permanent lock contention, backlog throughput, elapsed-time SLA and live Telegram remain NOT RUN/UNKNOWN. Hourly 100-row capacity is unchanged; monitor failures/backlog and qualify production recovery separately. No deployment, production migration or paid-feature activation performed.

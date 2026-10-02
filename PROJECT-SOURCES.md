# Project Sources

Repository: https://github.com/n923760-rgb/digital-services-platform
Official branch: main; always retrieve live HEAD rather than treating a stored SHA as current.
Owner-confirmed direction (2026-10-02): Saudi/Arabic-first platform, one developer, Modular Monolith; Telegram is the first channel. New features/complexity require an actual owner-confirmed trigger. [Scope decision](docs/SCOPE.md). Owner-selected payment: Telegram Stars, directly per order; native whole-Star XTR accounting with no SAR conversion. [Stars contract](docs/TELEGRAM-STARS.md). Web is the existing operations/admin console, not a requested customer storefront.
Local authority: [AGENTS.md](AGENTS.md).
Reusable primary reference: [Master Governance](https://github.com/n923760-rgb/engineering-governance/blob/main/MASTER_GOVERNANCE.md).
Reference navigation: [Global Reference](https://github.com/n923760-rgb/engineering-governance/blob/main/GLOBAL_REFERENCE.md).
For another project: use the central [Universal Project Start Prompt](https://github.com/n923760-rgb/engineering-governance/blob/main/docs/NEW_PROJECT_ADOPTION_PROMPT.md), derive that project's live facts, then generate its own AGENTS.md. This integration does not automatically install instructions in other repositories.

## Canonical engineering records

- [Master roadmap](ENGINEERING/MASTER_ROADMAP.md)
- [Read-only baseline](ENGINEERING/REPORTS/2026-10-01-MASTER_BASELINE.md)
- [Qualified repair report](ENGINEERING/REPORTS/2026-10-01-AUTHORIZED_REPAIRS.md)
- [Evidence index](ENGINEERING/EVIDENCE/2026-10-01-BASELINE.md)
- [Local skill catalog](.agents/skills/README.md)

## Source and contracts

[README](README.md), [architecture milestone contract](docs/ARCHITECTURE.md),
[financial/order core](docs/CORE-001.md), [payments](docs/PAYMENTS.md),
[files](docs/FILES.md), [registry](docs/SERVICE-REGISTRY.md),
[custom requests](docs/CUSTOM-REQUESTS.md), [recovery](docs/BACKUP-RECOVERY.md).
The current architecture contract separates the intended small baseline from existing source and historical foundation acceptance. The continuation implements the described direct text-summary slice with a local provider interface; [contract](docs/DIRECT-SUMMARY.md). Old infrastructure remains in docker-compose.legacy.yml, default Compose is minimal. No generative AI or live paid launch is inferred. Existing Alembic history remains authoritative.

Application owners: packages/python/platform_core/. Adapters: apps/api/, apps/telegram_bot/, apps/web/.
Schema: migrations/. Build/dependencies: pyproject.toml, apps/web/package.json, Dockerfiles and docker-compose.yml.
CI: .github/workflows/ci.yml. Dedicated lab plan/toolchain: baseline sections R–T.

No permanent host provider or qualified production/lab environment is established by these documents. Verify actual capabilities before execution. Do not store transient IPs, credentials or runtime locks here.

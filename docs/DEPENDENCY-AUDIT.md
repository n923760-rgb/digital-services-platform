# Dependency advisory checks

The read-only `Dependency advisory audit` workflow runs on pushes, pull requests, manual dispatch and weekly. It installs isolated pip-audit 2.9.0 from `requirements/audit.txt` using hashes and audits the committed Python runtime requirement names/versions through the public PyPI advisory service. `--strict` rejects skipped dependencies; `--disable-pip` avoids resolving or executing app packages. Hash presence in that mode is not content verification: Foundation CI separately verifies fingerprints and performs hashed installs/pip check.

The npm production graph uses its committed integrity lock, `npm ci --ignore-scripts` and `npm audit --omit=dev`. Foundation web CI also runs production npm audit before the actual build/browser checks. Any reported vulnerability, skipped dependency, registry/report failure or invalid/empty Python report fails qualification. No advisory IDs are suppressed.

Public JSON responses and exact source SHA are retained in job logs; package names/versions are public repository data. No customer bytes, provider account or tokens are sent to scanners.

Known-advisory evidence is time-dependent. This scan excludes OS/container layers, development/build/browser/auditor dependencies, vendored bundles, application-specific vulnerabilities, signing/SBOM/deployed artifact identity and live providers. Zero reported advisories is not proof of safety or release readiness.

For a bounded auditor-tool update, change `requirements/audit.in`, use the pinned resolver versions documented in `docs/DEPENDENCIES.md` to generate a complete hashed audit lock, review all tool dependency deltas, then qualify its isolated install and the exact-source workflows. `scripts/emit_audit_lock.py` emits public chunks when the executor exposes only CI logs. Do not resolve tools or application dependencies during ordinary runtime tasks.

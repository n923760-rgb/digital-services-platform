# CI Qualification Addendum — DSP-014

Date: 2026-10-01 UTC.
Round: qualification of the documentation adoption PR after the completed read-only baseline.
Repository: n923760-rgb/digital-services-platform.
PR: https://github.com/n923760-rgb/digital-services-platform/pull/23
Tested PR head: 180324216ca932b27e3fcdc293c086e7680671ab.
PR job checkout used GitHub's synthetic merge commit 1040da41ea2801174e7a646b72bcf14248c07c82.
Base application source: b90dccda7175b7f77dfe8cba4b3bc573d283a299.
Controller retrieved complete decoded failed-job logs through GitHub API; no local commands ran.

## Observed results

[PR CI 36882378686](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36882378686):
- web: PASS (job 110437107296).
- python: FAIL (job 110437107246), first causal failure at alembic upgrade head.
- compose: FAIL (job 110437106992), migrate container exits 1 before dependent application qualification.

[Push CI 36882315759](https://github.com/n923760-rgb/digital-services-platform/actions/runs/36882315759) independently returned web PASS, python FAIL and compose FAIL. Its logs were not additionally retrieved because the full causal PR logs already establish the problem.

The Python job's install/package/Ruff steps succeeded; pytest never ran after migration failure.
Compose restore, PDF smoke and API readiness qualification did not run after startup failure.
Historical baseline CI PASS remains attributed to its original source/time; it does not supersede this new clean-install failure.
Results here certify only these actual commits, not later documentation or code commits.

## DSP-014 — P1 build blocker — missing SQLAlchemy asyncio dependency

FACT: pyproject.toml declares SQLAlchemy>=2.0,<3 without the asyncio extra or explicit greenlet. migrations/env.py imports sqlalchemy.ext.asyncio.
FACT: both Python install and Compose build resolved SQLAlchemy 2.1.1. The successful installation list contains SQLAlchemy but no greenlet.
FACT: both failed-job logs contain:

    ModuleNotFoundError: No module named 'greenlet'
    ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed.

The runtime diagnostic explicitly recommends the sqlalchemy[asyncio] install target.
This occurs on importing the asyncio engine during alembic upgrade head, before database migrations can execute.
The documentation PR changes no pyproject.toml, migration, Dockerfile, workflow or application source. The complete diff is documentation/instructions only. Therefore a defect in dependency declaration is exposed by fresh dependency resolution, not a changed schema or business implementation.

The missing required extra is causally established; why a previous installation supplied greenlet was not investigated and remains UNKNOWN.
This is concrete evidence for the reproducibility risk DSP-010, but fixing the missing runtime dependency and implementing broad lockfiles should remain separate bounded tasks.

## Next bounded task

Before DSP-001 runtime diagnosis:
1. Verify live main and open PR state.
2. Authorize/scope one dependency correction task from official source.
3. Prefer the minimal supported declaration SQLAlchemy[asyncio]>=2.0,<3 so the package selects its required asyncio dependencies.
4. In a qualified disposable lab, clean-install the package and prove importing sqlalchemy.ext.asyncio, alembic upgrade head, existing Python tests and Compose startup/affected checks.
5. Review complete dependency-only diff and exact-source CI in a separate PR.

No application/dependency fix, CI weakening, rerun, merge, settings change or production operation was performed under this documentation review.

## Documentation verification already completed

All 12 initial new files were read back from head 180324216ca932b27e3fcdc293c086e7680671ab and matched authored contents.
23 local Markdown links and six SKILL frontmatter/name matches checked: PASS.
One initial documentation commit, additions only: PASS.
Local code/runtime checks: NOT RUN (API-only session).
Governance PR remains draft until the build blocker and its qualification are resolved; its files are reviewable now.

# Reproducible dependency inputs

Python 3.12.14 and Node 22.23.3 are the qualified CI toolchain for this resolution. Runtime/dev/build/sandbox requirements are exact PyPI pins with SHA-256 hashes; runtime and dev versions agree, and sandbox pypdf matches the worker. package-lock.json fixes the npm graph and integrity records. Docker base/service images and GitHub actions use immutable digests/commit SHAs rather than moving tags.

Install against a disposable test environment:
- pip install --require-hashes -r requirements/build.txt
- pip install --require-hashes -r requirements/dev.txt
- pip install --no-deps --no-build-isolation -e .
- pip check; python scripts/verify_dependency_artifacts.py
- Set DATABASE_URL and TEST_REDIS_URL to isolated PostgreSQL/Redis, migrate and run pytest.
- In apps/web use npm ci, npm run typecheck and npm run build.

The application Dockerfile installs hashed build/runtime requirements and its own package without dependency/build re-resolution. The sandbox installs only its hashed parser lock; the web image uses npm ci. Compose image digests still support the provider's published manifest architectures, but qualification in this round is Linux CI only. No production images were deployed.

requirements/resolution.json records the generation source, input hashes, exact resolver/toolchain and image identities. Resolution ran in read-only GitHub Actions run 36907947844 at 2a602272e8b7b13fbe5b91d749a5abbfc918233d; it emitted public lock data in bounded JSON log chunks for API-mode adoption. Final install qualification is recorded on the associated PR's exact head, not implied by generation success.

For updates use the manual Resolve dependency locks workflow or the same pinned pip-tools 7.5.0/pip 25.1.1 commands in an isolated workspace. The workflow uses read-only repository permissions and does not commit, merge or deploy; review the resulting files and update every matching Docker/CI image/action reference and resolution fingerprint in one dependency-update PR. Run the full locked CI suite before merge. Changing a manifest requires regeneration rather than bypassing fingerprints.

Locking prevents silent re-resolution; it is not vulnerability scanning, a guarantee about upstream publishers, bit-for-bit application artifact reproduction, image signing or a production release decision. Independent off-host recovery, payment/Telegram staging and launch qualification remain required.

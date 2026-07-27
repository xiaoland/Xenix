# Contributing

## Workflow

1. Follow the repository [`AGENTS.md`](AGENTS.md), the [working protocol](docs/00-meta/working-protocol.md) for non-trivial work, and the nearest local `AGENTS.md` for the files being changed.
2. Identify the canonical owner through the [documentation index](docs/README.md) before changing product, architecture, unit, or runtime truth.
3. Load [implementation taste](docs/00-meta/implementation-taste.md) only for non-trivial code changes that shape boundaries, data, authority, naming, abstraction, or complexity.
4. Keep changes explicit and local to the owning surface. Update durable docs when a verified contract, guarantee, operation, or recovery path changes.

## Branch Promotion and Release

- `develop` is the mutable integration line. An ordinary push to `develop` does not
  run Native CI.
- Promote accepted work through one same-repository GitHub PR whose head is
  `develop` and base is `main`. Native CI is scoped to PRs targeting `main`; its
  stable `Native CI Gate` check is required before merge.
- Do not locally merge `develop` into `main` and push the result. Do not open
  feature-branch PRs directly to `main`.
- A merged promotion makes its resulting `main` state release-eligible but does not
  release it. Release starts only when an immutable `v<project-version>` tag is
  pushed on an eligible promotion result.
- A release tag may select the current or an older eligible promotion result.
  After creating the local tag and before pushing it, run
  `pdm run release-identity --require-tag --require-promotion --repository xiaoland/Xenix`.
  The remote release workflow repeats this check.
- A historical target must already contain the supported release workflow and
  protocol. Because GitHub resolves a push workflow from the tagged ref, the local
  preflight is the rejection boundary for older pre-protocol commits.
- Never move or delete a pushed release tag. Product corrections use a new version;
  transient infrastructure failures rerun the unchanged tag.

## Development Commands

- Python `3.14.2` is the project and packaged runtime.
- `pdm install` installs project dependencies.
- `pdm run dev` runs the desktop application.
- `pdm run test` runs the manifest-owned test topology.
- `pdm run pytest --promotion-shard <name>` runs one Promotion semantic shard;
  `pdm run pytest --direct <pytest selectors/options>` is the explicit targeted
  single-process route.
- `pdm run lint` runs Ruff over source, tests, scripts, and benchmarks.
- `pdm run typecheck` runs the strict Mypy slice over typed boundary modules.
- `pdm run check` regenerates/checks Agent Skills, runs Ruff and Mypy, validates
  the test manifest and native OCR lock, then compiles the Python tree.
- `pdm run i18n-extract` and `pdm run i18n-compile` update Qt translations.
- `pdm run package` builds the Windows bundle.
- `pdm run smoke-package` verifies the packaged executable.

Use the smallest verification set that proves the affected contract. Run `pdm run test` and `pdm run check` when the change has repository-wide or uncertain impact.

## Change-Specific Review

- UI changes follow the nearest local UI guidance. Cross-unit interaction or authority changes are reviewed against
  [Product TDD](docs/20-product-tdd/README.md).
- Storage changes are reviewed against [Storage Ownership](docs/20-product-tdd/storage-ownership.md); migrations also follow [Local State Evolution](docs/40-deployment/local-state-evolution.md).
- Runtime changes use the [Deployment index](docs/40-deployment/README.md); packaging changes follow [Packaging](docs/40-deployment/packaging.md) and the packaged smoke gate.
- New cross-unit ML states or result semantics update the
  [ML Task Lifecycle](docs/20-product-tdd/ml-task-lifecycle.md); runtime locations
  remain Deployment or source truth.

## Testing Intent

- Avoid adding a narrow regression test for every fixed bug. A past failure is evidence to inspect the durable contract, not by itself a reason to preserve a tiny test forever.
- Prefer high-signal tests that protect stable behavior: golden tests for deterministic payloads, projections, migrations, and artifact shapes; integrated tests for UI/service/storage/ML adapter boundaries; and E2E or smoke tests for critical user workflows.
- Add lower-level unit or boundary tests when they protect a stable contract, isolate high-risk logic, shorten feedback for expensive failures, or cover config resolution, logging, resource loading, ML task orchestration, storage boundaries, migrations, or data-loss risks.
- Do not add tests that only restate facts already guaranteed by source definitions, type contracts, enum membership, schema definitions, data models, or incidental implementation details.

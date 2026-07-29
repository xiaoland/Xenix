# TP-21 — Packaging and Operations

## Outcome

Make the managed AMD feature reproducible and supportable from a packaged Xenix
build without bundling GPU runtimes/models or leaking remote secrets.

## Owned Mutation

- `xenix.spec` and required resource collection;
- `scripts/verify_packaged_smoke.py`;
- a separate bounded AMD packaged-smoke entrypoint; generic
  `knowledge_packaged_smoke.py` remains AMD-free;
- `docs/40-deployment/runtime-state.md`;
- `docs/40-deployment/packaging.md`;
- diagnostic bundle integration and packaging tests.

Release workflows/publication remain out of scope unless separately authorized.

## Behavior

- product manifests/self-test assets are packaged; large runtimes/models are exact
  on-demand acquisitions;
- packaged runtime uses isolated app/target roots and declares cache locations;
- diagnostic bundle projects redacted installation/generation/phase/manifest and
  supervisor facts, never credentials/tokens/live URLs/private content;
- restart, unsupported cell, repair-required, disconnect, cleanup, and target
  evidence have operator guidance;
- packaging does not depend on the feasibility lab or developer SSH config.
- AMD resource/source collection is one explicit optional collector rather than
  the current unconditional whole-tree behavior; generic smoke/diagnostics import
  no AMD module.
- ROCm/vLLM/RapidOCR target runtimes remain on-demand manifest acquisitions and do
  not become unconditional desktop `pyproject.toml`, lock, or PyInstaller
  dependencies.

## Acceptance

- fresh packaged runtime begins with no AMD installation/provider;
- packaged Private SSH guided flow reaches the same service boundary as TP-19;
- resource manifests/digests are present and immutable;
- diagnostic secret scan passes;
- unsupported-cell failure is actionable and non-mutating;
- clean shutdown/restart and exact cleanup are documented and exercised.
- with the AMD collector/check disabled and AMD source/resources absent, generic
  package, diagnostics, smoke, and packaged smoke pass and contain no AMD payload.

## Verification

- `pdm run test`;
- `pdm run check`;
- `pdm run smoke`;
- `pdm run package`;
- `pdm run smoke-package`.

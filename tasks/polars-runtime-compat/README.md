# Polars Runtime Compatibility

## Objective & Hypothesis

Packaged Xenix fails on another machine with `RuntimeError: unknown feature flag: 'sse3'`.

Hypothesis: the shipped Polars runtime is the default `_polars_runtime_32`, whose build flags require modern CPU features. Release packaging should include the Polars compatible runtime and prefer it so old or constrained CPUs can import Polars during startup and packaged smoke paths.

## Guardrails Touched

- Packaging/dependency boundary: `pyproject.toml`, `pdm.lock`, `xenix.spec`
- Deployment knowledge: `docs/40-deployment/development.md`
- Runtime behavior should stay unchanged except Polars native runtime selection.
- Do not use `POLARS_SKIP_CPU_CHECK` as a production fix.

## Current Understanding

- Current local Polars runtime build flags include `+sse3,+ssse3,+sse4.1,+sse4.2,+avx,+avx2,+fma,+bmi1,+bmi2,+lzcnt,+pclmulqdq,+movbe`.
- `polars._plr` prefers `rtcompat`, then `rt64`, then `rt32` when those runtime packages are available.
- Current installed and packaged output only show `_polars_runtime_32`.
- Official Polars guidance for old CPUs is `polars[rtcompat]`.
- After dependency update and sync, local `import polars` reports `runtime=rtcompat`.
- PyInstaller `collect_dynamic_libs()` returns no entries for Polars runtime packages because their core artifact is a Python extension module; `hiddenimports` must carry `_polars_runtime_compat._polars_runtime`.

## Verification

- Confirm dependency resolution installs `polars-runtime-compat==1.42.1`. Done.
- Confirm local `import polars` loads with compatible runtime available. Done: `runtime=rtcompat`.
- Confirm PyInstaller spec collects `_polars_runtime_compat` into `dist/xenix/_internal`. Done: packaged output includes `_polars_runtime_compat/_polars_runtime.pyd` and `_polars_runtime_32/_polars_runtime.pyd`.
- Run targeted compile/checks and packaged smoke. Done:
  - `pdm run package`
  - `pdm run smoke-package`
  - `pdm run check`

## Next Step

Ready for review. Distribute the rebuilt `dist/xenix/` onedir bundle, not only `xenix.exe`.

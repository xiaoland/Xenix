# Xenix Native

Xenix Native is a local desktop workbench for business data analysis through conversation, built with Python and PySide6 Qt Widgets.

Repository routing and knowledge ownership start in [AGENTS.md](AGENTS.md). Use the local [contributor guide](CONTRIBUTING.md) for setup, feedback loops, testing, and release rules; the optional SVC corpus provides additional working-method guidance through `svc lookup`.

## Quick Start

```powershell
pdm sync --clean -G :all
pdm run prepare
pdm run dev --isolated
```

Use Python 3.14.2 and PDM 2.26.6. The authoritative Python and dependency constraints are declared in [pyproject.toml](pyproject.toml) and [pdm.lock](pdm.lock); project-local environment selection is declared in [pdm.toml](pdm.toml).

Contributor, test, translation, and packaging commands are owned by [CONTRIBUTING.md](CONTRIBUTING.md).

`--isolated` starts with a disposable runtime home. Use `pdm run dev` for your normal persistent workspace. Run `pdm run verify` for the local static, offline acceptance, and isolated desktop smoke gates; focus a test with `pdm run test tests/test_job_scheduler.py -q`.

## Layout

- `src/xenix` contains the application package, bootstrap code, UI, runtime config, storage services, logging, and exception handling.
- `tests` contains the offline acceptance portfolio, opt-in runtime/storage fixtures, offscreen UI contracts, native Windows smoke, and separately invoked live Agent benchmarks.
- `scripts` contains developer helpers used by `pdm run`.
- `ml` contains legacy model scripts; native ML implementation lives under `src/xenix/services/ml`.
- `docs` stores durable project knowledge.
- `tasks` stores volatile task packets, working evidence, and historical execution records; it is not a durable source of current product or architecture truth.
- `xenix.spec` is the canonical Windows PyInstaller `onedir` spec.

## Documentation Model

- PRD: [docs/10-prd/README.md](docs/10-prd/README.md)
- Product TDD: [docs/20-prd-tdd/README.md](docs/20-prd-tdd/README.md)
- Unit TDD: [docs/30-unit-tdd/README.md](docs/30-unit-tdd/README.md)
- Deployment: [docs/40-deployment/README.md](docs/40-deployment/README.md)
- Contributor workflow: [CONTRIBUTING.md](CONTRIBUTING.md)
- Application assembly and cleanup: [composition design](docs/30-unit-tdd/application-composition.md)
- Data cleaning ownership: [cleaning design](docs/30-unit-tdd/data-cleaning.md)
- SVC corpus baseline: [svc.json](svc.json)

For packaged delivery, see [Packaging](docs/40-deployment/packaging.md). For resolved application paths, persisted state, and recovery, see [Runtime State](docs/40-deployment/runtime-state.md).

# Xenix Native

Xenix Native is a desktop machine-learning workbench for non-technical business users. Product scope and vocabulary are owned by [`docs/10-prd/`](docs/10-prd/README.md).

## Repository Map

- `src/xenix/ui/`: PySide6 Qt Widgets UI
- `src/xenix/services/`: service and orchestration boundaries
- `src/xenix/services/storage/`: SQLite models, repositories, migrations, and storage layout
- `src/xenix/services/ml/`: native ML execution, registry, and adapters
- `tests/`: automated verification
- `scripts/`: development, diagnostics, translation, and packaging helpers
- `docs/`: durable project knowledge
- `tasks/`: task packets
- `ml/`: legacy model scripts; leave intact unless a task explicitly targets them

## Knowledge Owners

- Product what and why: `docs/10-prd/*`
- Cross-unit technical contracts, when admitted: `docs/20-prd-tdd/*`
- Unit design and local seam guidance, when admitted: `docs/30-unit-tdd/*`
- Runtime, packaging, migration, observability, and recovery truth, when admitted: `docs/40-deployment/*`
- Contributor workflow and testing policy: `CONTRIBUTING.md`
- Nearer `AGENTS.md` files are additive for their subtree.
- `tasks/` are task packets, they are volatile.

## Development Workflow

- Runtime and tooling: Python `3.14.2`, PDM, PySide6/Qt Widgets, pytest, and PyInstaller.
- Install/run: `pdm install`, then `pdm run dev`.
- Verify the full manifest topology with `pdm run test`; use `pdm run pytest --direct <pytest selectors/options>` for a focused single-process run. Also run `pdm run check` and `pdm run smoke`; package with `pdm run package` and verify with `pdm run smoke-package`. Use these PDM entries instead of bare `pytest` so repository setup and isolated temp paths apply.
- Diagnostics: `pdm run diagnostic-bundle`; use GammaRay when available for widget hierarchy, properties, geometry, visibility, and events.
- Windows runtime home: `%LOCALAPPDATA%\Xenix` (normally `%USERPROFILE%\AppData\Local\Xenix`), overridden by `XENIX_APP_HOME`.
- Primary debug files: `state\xenix.db`, `logs\xenix.log`, `config\agent_settings.json`, and `config\ml_workers.json` under the runtime home.
- Detailed packaging, runtime-state, observability, migration, and recovery procedures: [`docs/40-deployment/`](docs/40-deployment/README.md).

## Execution Rules

- Commit only after an explicit user command; include only the approved task scope by default.
- High-risk storage, runtime, packaging, Agent Harness, ML lifecycle, and Chatbot changes start with the nearest local instructions plus the owner above.

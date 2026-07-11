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
- `tasks/`: active task-local state
- `ml/`: legacy model scripts; leave intact unless a task explicitly targets them

## Knowledge Owners

- Working protocol, task control, Mutation Gate, and documentation quality: [`docs/00-meta/working-protocol.md`](docs/00-meta/working-protocol.md)
- Non-trivial implementation judgment: [`docs/00-meta/implementation-taste.md`](docs/00-meta/implementation-taste.md)
- Product behavior, scope, and business language: [`docs/10-prd/`](docs/10-prd/README.md)
- Cross-unit contracts and technical decisions: [`docs/20-product-tdd/`](docs/20-product-tdd/README.md) and its [`adr/`](docs/20-product-tdd/adr/README.md)
- Agent Harness internal design and local seam guidance: [`docs/30-unit-tdd/`](docs/30-unit-tdd/README.md) and the nearest local `AGENTS.md`
- Runtime, packaging, migration, observability, and recovery: [`docs/40-deployment/`](docs/40-deployment/README.md)
- Contributor workflow and testing policy: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Mechanically enforceable facts: source, configuration, schemas, tests, assertions, or automation
- Volatile tasks: retain a top-level entry only while its latest recursive modification is within the previous `7 x 24` hours; delete older entries directly, with no archive or promotion review.

High-risk storage, runtime, packaging, Agent Harness, ML lifecycle, and Chatbot changes start with the nearest local instructions plus the owner above. Use [`docs/README.md`](docs/README.md) to reach the exact durable document instead of copying its contract here.

## Development Workflow

- Runtime and tooling: Python `3.12`–`3.14`, PDM, PySide6/Qt Widgets, pytest, and PyInstaller.
- Install/run: `pdm install`, then `pdm run dev`.
- Verify: `pdm run test [pytest args]`, `pdm run check`, and `pdm run smoke`; package with `pdm run package` and verify with `pdm run smoke-package`. Use the PDM test entry instead of bare `pytest` so repository setup and isolated temp paths apply.
- Diagnostics: `pdm run diagnostic-bundle`; use GammaRay when available for widget hierarchy, properties, geometry, visibility, and events.
- Windows runtime home: `%LOCALAPPDATA%\Xenix` (normally `%USERPROFILE%\AppData\Local\Xenix`), overridden by `XENIX_APP_HOME`.
- Primary debug files: `state\xenix.db`, `logs\xenix.log`, `config\agent_settings.json`, and `config\ml_workers.json` under the runtime home.
- Detailed packaging, runtime-state, observability, migration, and recovery procedures: [`docs/40-deployment/`](docs/40-deployment/README.md).

## Execution Rules

- For non-trivial work, read [`docs/00-meta/working-protocol.md`](docs/00-meta/working-protocol.md) and follow its permission boundary.
- Load [`docs/00-meta/implementation-taste.md`](docs/00-meta/implementation-taste.md) only when a change shapes structure, boundaries, data, authority, naming, abstraction, performance, or complexity.
- Read the nearest local `AGENTS.md` before editing a governed subtree; local rules are additive.
- Prefer code, configuration, schemas, tests, and automation for facts they can enforce directly.
- Commit only after an explicit user command and include only the approved task scope by default.

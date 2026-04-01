# Domain Glossary

## Product Terms

- Native app: the desktop application running as a single local process.
- Work item: a persisted unit of user ML work and selection state.
- Dataset registration: metadata pointer to a user-managed source dataset.
- Trained model: canonical model artifact tracked by metadata and stored on filesystem.

## Architecture Terms

- UI layer: Qt Widgets views under `src/xenix/ui/`.
- Service layer: orchestration and validation layer under `src/xenix/services/`.
- ML adapter: service-owned bridge to model execution logic.
- Persistence adapters: SQLite repositories and filesystem ownership logic.

## Documentation Terms

- PRD: product what and why (`docs/10-prd/`).
- Product TDD: cross-unit technical truths (`docs/20-product-tdd/`).
- Unit TDD: hard local unit design memory (`docs/30-unit-tdd/`).
- Deployment layer: runtime/ops truth (`docs/40-deployment/`).
- Task layer: volatile planning and execution records (`tasks/`).

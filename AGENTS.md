# Xenix Native

A desktop machine-learning workbench for non-technical business users. Product scope and vocabulary belong to [PRD](docs/10-prd/README.md).

## Repository Map

- `src/xenix/ui/`: PySide6 Qt Widgets desktop
- `src/xenix/services/`: orchestration; `agent/` and `llm/` own conversation boundaries, `storage/` owns persistence, `ml/` owns native ML execution
- `tests/`: verification; `scripts/`: development and packaging tools
- `docs/`: durable knowledge; `tasks/`: volatile task packets
- `ml/`: legacy scripts; modify only when explicitly in scope

## Knowledge Owners

- Product what and why: [PRD](docs/10-prd/README.md)
- Cross-unit contracts: [Product TDD](docs/20-prd-tdd/README.md)
- Internal design and implementation rationale: [Unit TDD](docs/30-unit-tdd/README.md)
- Runtime, packaging, migration, and recovery: [Deployment](docs/40-deployment/README.md)
- Contributor workflow and verification policy: [CONTRIBUTING.md](CONTRIBUTING.md)

Read the relevant owner and applicable subtree `AGENTS.md`; load further guidance when the task needs it. Local instructions apply only within their scope. Keep mechanically enforceable facts in source/configuration and detailed design in its owner, rather than copying either into instructions.

## Development Workflow

- Python `3.14.2`, PDM `2.26.6`, PySide6/Qt Widgets.
- Install: `pdm sync --clean -G :all`, then `pdm run prepare`. Run: `pdm run dev`.
- Focused verification: `pdm run pytest --direct <selectors>`; broad verification: `pdm run test` and `pdm run check`. Startup/runtime changes also use `pdm run smoke --isolated`. Packaging gates and verification selection are in CONTRIBUTING.
- Diagnostics: `pdm run diagnostic-bundle`. Runtime defaults to `%LOCALAPPDATA%\Xenix`, overridden by `XENIX_APP_HOME`; inspect `state/xenix.db`, `logs/xenix.log`, and `config/` only within the authorized task.

## Collaboration

Diagnosis authorizes investigation; implementation requires an authorized target. Preserve unrelated changes. Commit only on explicit request. Scale planning and verification to the task; ordinary work does not require sub-agents or a task packet.

Write documentation for Agents, with each paragraph or list item on one semantic line.

<!-- svc:begin -->
## SVC

Use `svc --help` or `svc <command> --help`.

- `svc status`: inspect project state
- `svc lookup`: read SVC guidance
- `svc task init`: create a task packet
- `svc task grow`: inspect packet shape without changing files
- `svc dev`: manage declared development targets

If `AGENTS.local.md` exists, read it after this file. It is ignored local guidance; shared rules belong here.
<!-- svc:end -->

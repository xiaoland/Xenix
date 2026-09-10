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
- Apply global guidance, this file, and applicable descendant `AGENTS.md` guidance for the files involved. Descendant rules apply only within their stated scope; more specific rules resolve conflicts there, while unrelated inherited constraints remain in force. Direct task instructions and higher-priority platform instructions take precedence.
- Read the relevant owner and local rules when the task touches their contracts; this map is not a requirement to read every owner, Skill, or subtree on every task. Referenced documents provide domain guidance, not authorization to expand the task.
- `tasks/` are task packets, they are volatile.

## Development Workflow

- Runtime and tooling: Python `3.14.2`, PDM `2.26.6`, PySide6/Qt Widgets, pytest, and PyInstaller.
- Install/run: `pdm sync --clean -G :all`, then `pdm run dev`.
- Follow `CONTRIBUTING.md`: use the smallest verification set that proves the affected contract. Use `pdm run pytest --direct <pytest selectors/options>` for focused verification; run `pdm run test` and `pdm run check` for repository-wide or uncertain impact. Use these PDM entries instead of bare `pytest` so repository setup and isolated temp paths apply. Local test lists identify relevant coverage; run the affected routes, not every listed suite by default.
- Run `pdm run smoke --isolated` when application startup or runtime integration changes. For packaging changes, build with `pdm run package` and verify with `pdm run smoke-package`; retain the release gates in `CONTRIBUTING.md`. These commands are not prerequisites for explanation, diagnosis, or documentation-only edits.
- For documentation-only changes, check the diff, relevant references, and rule consistency. After sufficient checks pass, finish; broaden verification only for new changes, failures, unresolved impact, or an explicit acceptance requirement.
- Diagnostics: `pdm run diagnostic-bundle`; use GammaRay when available for widget hierarchy, properties, geometry, visibility, and events.
- Windows runtime home: `%LOCALAPPDATA%\Xenix` (normally `%USERPROFILE%\AppData\Local\Xenix`), overridden by `XENIX_APP_HOME`.
- Primary debug files: `state\xenix.db`, `logs\xenix.log`, `config\agent_settings.json`, and `config\ml_workers.json` under the runtime home.
- Detailed packaging, runtime-state, observability, migration, and recovery procedures: [`docs/40-deployment/`](docs/40-deployment/README.md).

## Execution Rules

- Distinguish diagnosis from implementation. Requests to explain, inspect, review, or diagnose authorize investigation and findings, not automatic source fixes. A request to implement, fix, or optimize a defined target authorizes the necessary edits within that scope; do not ask for the same approval again. Exploration, experiments, spikes, and task packets remain allowed without separate source approval, but do not silently turn them into production changes.
- For authorized implementation, inspect relevant evidence, make the change, perform proportionate verification, and report the result and remaining limitations. Do not stop at a plan unless a plan was requested. If blocked, complete independent in-scope work and identify the concrete blocker; do not claim unverified completion.
- Ask only when missing information materially changes the outcome, scope, risk, or authorization, or the next action exceeds the authorized scope. Otherwise state consequential assumptions and proceed. A newly discovered unrelated issue is a finding, not permission to repair it.
- Preserve existing uncommitted changes. Modify only the task's owning surfaces; do not revert unrelated work to make checks pass.
- Commit only after an explicit user command; include only the approved task scope by default.
- Implementation approval does not by itself authorize deployment, publication, sending messages, credential access or disclosure, or deletion of important data. Require authorization covering the concrete action, honor existing authorization without repeated confirmation, and obey sandbox/tool approval boundaries. Runtime paths above are diagnostic references, not blanket permission to inspect user data.
- Scale planning, diagrams, and review depth to the problem. Use topology or sequence diagrams when they clarify dependencies, ordering, or authority. Ordinary tasks do not require a task packet, multi-model review, or sub-agents; preserve explicit model routing and task-specific workflow requirements when they apply.
- High-risk storage, runtime, packaging, Agent Harness, ML lifecycle, and Chatbot changes start with the nearest local instructions plus the owner above.

## Documentation

- Documentation is written for Agents. Keep each Markdown paragraph or list item as a semantic line; do not hard-wrap prose solely to satisfy a line-length convention.

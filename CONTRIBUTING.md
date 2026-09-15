# Contributing

## Workflow

1. Follow the repository [`AGENTS.md`](AGENTS.md) and the nearest local `AGENTS.md` for the files being changed. If SVC is installed, browse additional working-method guidance with `svc lookup`; local setup and verification do not require it.
2. Identify the canonical owner through the [documentation index](docs/index.md) before changing product, architecture, unit, or runtime truth.
3. Keep changes explicit and local to the owning surface. Update durable docs when a verified contract, guarantee, operation, or recovery path changes.

## Branch Promotion and Release

- `develop` is the mutable integration line. An ordinary push to `develop` does not run Native CI.
- Promote accepted work through one same-repository GitHub PR whose head is `develop` and base is `main`. Native CI is scoped to PRs targeting `main`; its single stable `Native CI` check is required before merge.
- Do not locally merge `develop` into `main` and push the result. Do not open feature-branch PRs directly to `main`.
- A merged promotion makes its resulting `main` state release-eligible but does not release it. Release starts only when an immutable `v<project-version>` tag is pushed on an eligible promotion result.
- A release tag may select the current or an older eligible promotion result. After creating the local tag and before pushing it, run `pdm run release-identity --require-tag --require-promotion --repository xiaoland/Xenix`. The remote release workflow repeats this check.
- A historical target must already contain the supported release workflow and protocol. Because GitHub resolves a push workflow from the tagged ref, the local preflight is the rejection boundary for older pre-protocol commits.
- Never move or delete a pushed release tag. Product corrections use a new version; transient infrastructure failures rerun the unchanged tag.

## Development Commands

- Python `3.14.2` is the project and packaged runtime.
- PDM `2.26.6` is the project workflow frontend; `pdm sync --clean -G :all` makes the project-local virtual environment match `pdm.lock`. Follow it with `pdm run prepare` to generate the ignored Skill catalog and compiled translations before a first static check.
- `pdm run dev` runs the desktop application.
- `pdm run test` prepares runtime resources and runs the complete offline acceptance portfolio in one process. Pass normal pytest selectors directly, for example `pdm run test tests/ml/test_data_cleaning_service.py -q`; `--direct` remains accepted for existing scripts but does not select a different runner.
- `pdm run pytest --direct <pytest selectors/options>` runs a focused selection with the same isolated temporary-path setup.
- `pdm run test-affected` runs only the offline tests affected by source changes via `pytest-testmon`'s coverage-based selection: the first run builds the `.testmondata` baseline (running everything), and later runs re-run only affected tests. `pdm run list-affected` lists the affected set without running. It is a developer aid and never narrows CI.
- `pdm run lint` runs Ruff over source, tests, and scripts.
- `pdm run typecheck` runs the strict Mypy slice over typed boundary modules.
- `pdm run check` checks the existing Skill catalog, runs Ruff and Mypy, validates the native OCR lock, then quietly compiles the Python tree. It never regenerates the catalog to conceal stale output: run `pdm run prepare` explicitly when it reports missing or outdated generated resources. CI follows the same prepare-then-check sequence.
- `pdm run verify` runs static checks, the offline portfolio, and isolated desktop smoke in order. It does not invoke live provider benchmarks or release publication.
- `pdm run smoke` runs the desktop application in smoke-test mode against the platform default home; combine with `--isolated` to use a fresh temp home.
- `pdm run i18n-extract` and `pdm run i18n-compile` update Qt translations.
- `pdm run package` builds the Windows bundle. Use `pdm run package --dist-dir dist/review` while another bundle is running, then `pdm run smoke-package --executable dist/review/xenix/xenix.exe` to verify that output.
- `pdm run smoke-package` verifies the packaged executable.
- `pdm run diagnostic-bundle` creates a local support archive (logs, task logs, install id, database summaries) without the raw database.
- `pdm run release-identity` verifies tag/version/promotion identity before pushing a release tag.
- `pdm run release-controls-audit` audits repository branch-protection and Environment rules.
- The benchmark has no automated tests of its own infrastructure. Verify changes with collection, static checks, saved-report inspection and explicitly selected live tasks or manual Judge calibration as needed.
- Every live benchmark summary prints a trace id and absolute JSON report path; inspect its lifecycle events and exception chain before rerunning a paid cell.
- `pdm run benchmark-agent-harness -- --collect-only -q` and the headed variant collect the same four default representative business tasks without provider calls. Use a concrete `tests/e2e/agent_harness/test_*.py[::test_name]` selector to run a task explicitly; selecting a file also includes its contrast nodes, and the whole directory includes historical cases. `--business-variant confirmation` changes representative tasks; named contrasts keep their own input. Scenarios do not add business-family weight. See the benchmark guide for contrast selectors.
- Run the affected service tests before a paid Agent benchmark; use the complete portfolio when impact warrants it. The commands remain independently executable: benchmark code never imports service tests or reads their reports. Omit `--model` to use the one configured default model, or supply exactly one override. The manual workflow requires both selectors but passes only job success—not test data or reports—across the service-to-Agent ordering edge.
- `pdm run benchmark-agent-harness -- --llm-settings <path> --embedding-settings <path> --judge-llm-settings <path> --judge-model <provider/model>` runs the default portfolio. The campaign task needs configured Knowledge embeddings; all four tasks request Judge evaluation. A task may contain two user requests, sharing one runtime and thread. Sampling and retries follow production behavior without benchmark round/token quotas; the external process deadline still applies to the task, and invocation token cost gates subsequent tasks. Reports preserve both deliveries and per-request usage.
- `pdm run benchmark-agent-harness-calibrate-judge` optionally measures Judge agreement on labelled examples. `pdm run benchmark-agent-harness-evaluate characterize <reports...>` describes all supplied attempts for one task, mode and configuration, including failures; `compare --baseline <reports...> --candidate <reports...>` compares equally shaped cohorts. Policy v3 reports task verdicts, unscored attempts, resource coverage and total Subject tokens per success including failed attempts. `formal` retains the three-headless-plus-one-headed acceptance rule. Calibration and a clean working tree are not prerequisites; v5 and v6 remain separate cohorts. See [the benchmark guide](docs/30-unit-tdd/agent-harness-benchmark.md) for interpretation and limits.

Use the smallest verification set that proves the affected contract. Run `pdm run test` and `pdm run check` when the change has repository-wide or uncertain impact.

### Choosing a feedback loop

| Changed behavior | Focused route | Broader evidence when needed |
| --- | --- | --- |
| Background dispatch, recovery, cancellation | `pdm run test tests/test_job_scheduler.py tests/test_knowledge_job_handlers.py tests/test_job_service.py -q` | Real desktop composition via isolated smoke |
| Data cleaning and registered outputs | `pdm run test tests/ml/test_data_cleaning_service.py tests/ml/test_ml_foundation_profile_cleaning.py -q` | Agent guidance and packaged worker imports |
| Conversation state and callback delivery | `pdm run test tests/ui_models tests/ui/test_chatbot_contract.py -q` | Harness acceptance and native Windows smoke |
| Application assembly or dependency imports | `pdm run check`, then `pdm run smoke --isolated` | Bundle and packaged smoke after import-path changes |
| Documentation only | Inspect changed links, commands, and ownership consistency | No application run unless a runtime claim needs evidence |

### Fixtures and completion

`tests/conftest.py` provides opt-in `app_paths` and `storage` fixtures. `app_paths` resolves a fresh runtime home through production configuration; `storage` applies production migrations and disposes its engine even after a test failure. A test that needs no database requests only `app_paths`. Fixtures that start workers depend on `storage` and release those workers in their own teardown, before the engine closes. Avoid success-only disposal at the bottom of test functions.

Coordinate concurrency with events/barriers and use `JobScheduler.wait_idle(timeout)` when the assertion needs the completed scheduling outcome. Worker entry alone does not mean its terminal database write is visible. A timeout bounds a stuck test; it must not substitute for arranging the tested ordering. The runner reserves a new temporary root for every invocation, including repeated calls from the same process, and preserves explicit `--basetemp` arguments.


## Qt Widget Lab

Use the Widget Lab for the shortest deterministic feedback loop around an admitted Qt Widgets state:

- `pdm run ui-lab -- --list --json` discovers scenario IDs without starting Qt or any application service.
- `pdm run ui-lab -- chat.empty` opens the searchable gallery at one scenario.
- `pdm run ui-capture -- chat.mixed-timeline --output ui-artifacts/local` renders a fixed synthetic state and writes `manifest.json`, `tree.json`, and `actual.png`.
- `pdm run ui-capture-all --output ui-artifacts/scenarios` captures every admitted scenario into a fresh run directory. `--prune-runs` removes only historical Xenix capture run dirs under the output root first. `--verify <run-dir>` checks that every captured scenario has complete artifacts and that the batch is reconciled (expected == captured, no failures).
- `--isolated` selects a unique fresh temp home for smoke and production runs; the real user home is never read, migrated, or written. Combine with `pdm run smoke` or `pdm run dev`.
- `main.history-populated` renders the production history panel (not the full application). `settings.provider-and-ocr` composes the production provider editor and OCR card with in-memory draft/status ports.
- `pdm run pytest --direct tests/ui -q` runs the offscreen widget contracts.
- `pdm run pytest --direct tests/ui_models -q` exercises the pure conversation state and injected execution boundary without constructing a widget.
- `pdm run ui-native-smoke` starts a separate `windows` QPA process for the small exposed/active/focus/dialog and custom-paint tripwire.
- `pdm run ui-artifacts-index` rebuilds the bounded agent-readable inventory for the allowlisted `ui-artifacts/` directory.

Scenarios live in `scripts/ui_lab/` and import production widgets without importing the application composition root. A new scenario must have a stable dotted ID, synthetic non-sensitive data, an explicit viewport/style/locale, a bounded readiness condition, and cleanup for every timer, worker, or window it owns. It must construct without a runtime home, database, network adapter, update check, OCR runtime, or ML worker. Reuse the same factory from interactive, capture, and test paths; do not create a second fixture language or assert pixel equality in ordinary widget contracts.

The capture driver applies the scenario's render identity (style, font, locale) before the scenario builds its widgets. Tests and the gallery follow the same order so that font metrics, translator, and style hints are always resolved before widget construction.

On Windows/offscreen the lab registers the installed Segoe UI faces into the current Qt process when necessary; it never installs or downloads fonts. A missing/mismatched text font rejects capture. Manifests record both the requested font and `QFontInfo`'s resolved font, so icon-font fallback cannot masquerade as a stable render environment. Keep screenshot baselines capture-only until this resolved identity is stable on CI.

When adapting a scenario to pytest-qt, let `qtbot` own widget deletion and use `before_close_func` for the scenario's cleanup. Do not also call the handle's `close()` (which schedules deletion) on a registered widget.

## Change-Specific Review

- UI changes follow the nearest local UI guidance. Cross-unit interaction or authority changes are reviewed against [Product TDD](docs/20-prd-tdd/README.md).
- Storage changes are reviewed against [Storage Ownership](docs/20-prd-tdd/storage-ownership.md); migrations also follow [Local State Evolution](docs/40-deployment/local-state-evolution.md).
- Runtime changes use the [Deployment index](docs/40-deployment/README.md); packaging changes follow [Packaging](docs/40-deployment/packaging.md) and the packaged smoke gate.
- New cross-unit ML states or result semantics update the [ML Task Lifecycle](docs/20-prd-tdd/ml-task-lifecycle.md); runtime locations remain Deployment or source truth.

## Testing Intent

- Avoid adding a narrow regression test for every fixed bug. A past failure is evidence to inspect the durable contract, not by itself a reason to preserve a tiny test forever.
- Prefer a small acceptance portfolio around irreplaceable business outcomes, irreversible data risks, migration/release compatibility, and a few critical cross-boundary workflows.
- Use typed boundary models, mature library guarantees, static analysis, packaged smoke, and clear ownership before adding lower-level behavioral cases.
- Do not add tests that restate source definitions, type/schema constraints, enum membership, library behavior, defensive branches, widget structure, or incidental implementation details.

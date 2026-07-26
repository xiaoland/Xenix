# First Promotion CI Audit

## Result

Promotion PR #111 run `30193238273` did not establish a successful Native CI
sample:

| Job | Result | Evidence |
| --- | --- | --- |
| Promotion Contract | success | same-repository `develop -> main` contract accepted |
| Python 3.12.10 | cancelled | non-UI completed as 650 passed, 4 skipped in 23:46; MainWindow reached 20/64 |
| Python 3.13.14 | cancelled | reached 606 passed, 4 skipped |
| Python 3.14.6 | cancelled | reached 483 passed, 4 skipped |
| Native CI Gate | failure | aggregate test result was `cancelled` |

All three Windows jobs reached the 30-minute job timeout. Setup and dependency
installation cost about 3.3-4.0 minutes; pytest consumed about 25.5-26.5 minutes
before cancellation. The run was neither a test assertion failure nor evidence
of one blocked test.

The suite contains 718 collected cases in 74 files and about 26,000 lines. The
largest observed file groups were:

| File/group | Observed or conservative duration |
| --- | ---: |
| `test_ml_execution.py` | 186-207 s |
| `test_knowledge_import_lifecycle.py` | 127-130 s |
| analysis/data group | up to about 481 s |
| all Knowledge groups | up to about 668 s |
| Agent + LLM group | up to about 339 s |
| ML/platform/release group | up to about 371 s |

## Test-Value Rule

A test earns Promotion CI cost only when it can name a stable contract, detect a
plausible meaningful regression, provide proof not already supplied by a stronger
test, and observe behavior at the owning boundary rather than restating private
implementation.

- Facts already guaranteed by source definitions, types, enums, generated schema,
  Pydantic models, Ruff, or Mypy do not receive duplicate pytest coverage. These
  proof layers run through `pdm run check`, not once per test case.
- Put an invariant into source construction when it can be made impossible to
  violate. If a relationship cannot be expressed by the type/model, assign it to
  an existing compiler, linter, type checker, schema/build preflight, or a real
  boundary test. Do not create an assertion script and call it static analysis.
- Reserve pytest for executable behavior: transformations, state transitions,
  persistence, side effects, failure atomicity, cross-boundary projection, and
  user-visible outcomes.
- Delete a test that only repeats a field definition, removed property, fixture,
  source literal, or behavior already proved by a stronger path.
- Consolidate repeated examples when one table/golden/integrated behavior proof
  owns the contract more directly.
- Replace expensive end-to-end setup when the claimed contract belongs to a
  cheaper boundary; retain a separate acceptance case for the true integration.
- Never delete data-loss, persisted compatibility, process/resource ownership,
  publication authority, secret redaction, or supply-chain proofs merely because
  they are slow.

## Candidate Review Outcome

The initial deletion list was re-reviewed against the final proof allocation
before implementation:

- `test_agent_ai_observability.py` was deleted because the stronger usage
  observability boundary already proves the behavior;
- exact Agent Tool schema, ML catalog, Knowledge format, translation literal,
  source-string, count, default, and prose censuses were removed where the
  authoritative type/model/compiler already owns the claim;
- duplicate decoder/history and mock-fixture examples were folded into stronger
  persisted or integrated boundaries;
- the public-allowlisted legacy failure-detail case was **retained**: it proves a
  privacy-compatible runtime read path that Ruff, Mypy, and Pydantic construction
  cannot establish;
- migration, persistence projection, corrupt-input rejection, archive/cache
  integrity, worker lifecycle, and data-loss proofs were retained for the same
  reason.

## Consolidation Candidates

- Replace the long per-model metadata census in `test_ml_registry.py` with
  catalog-wide invariants, unique keys, service resolution, and representative
  real fit/predict cases.
- Delete scattered Agent tool schema field assertions. Property sets, types,
  enums, required fields, and `additionalProperties` policy belong to strict
  Pydantic input models; provider schemas are projections of those models. Mypy
  binds handler input types to the same model. Keep only real admission,
  invocation, and rejection behavior where execution crosses the registry or
  service boundary; description usefulness belongs to review and Agent
  final-answer benchmarks, not exact-string tests.
- Reduce the 293-line MainWindow language test to locale persistence plus one
  sentinel per major window; translation source/completeness belongs to the
  extract/compile check.
- Consolidate private Qt geometry/style assertions into a small set of resize,
  wrap, visibility, and Windows paint-hazard proofs. Preserve the explicit
  `UserMessageCard` black-panel invariant owned by the UI guidance.
- Fold the token formatter helper case into the real usage rendering boundary.
- Consolidate duplicate startup splash/flush fake-call tests into lifecycle
  behavior proofs.
- Separate password-lifetime proof from parser acceptance. The encrypted-PDF
  lifecycle case currently spends about 61 seconds locally loading the real
  parser to prove that a password is transient and retryable; prove that
  ownership at the attempt/parser boundary and retain independent real PDF
  acceptance coverage. Apply the same reasoning to repeated encrypted OOXML
  cases without dropping promised format support.
- Replace source-string scans of the Paddle native worker with invalid-lock,
  compiled protocol, and packaged-smoke behavior.
- Merge repeated legacy, SVG namespace, benchmark oracle, purchase URL, and
  publication-fixture cases into stronger table, mutation, or persisted-boundary
  tests.

The deletion list alone will not recover the required 12+ minutes. It is a
maintainability and proof-quality correction that must precede topology work.

## Proof Allocation

| Claim shape | Owning proof |
| --- | --- |
| field, enum, required property, generated Agent Tool schema | strict Pydantic source model plus Mypy; no duplicate pytest |
| unused/import/obvious maintainability defects | Ruff |
| parameter, return, Protocol, nullability, and union compatibility | strict Mypy slice with Pydantic plugin |
| catalog uniqueness and valid cross-field combinations | Pydantic construction and registry validators |
| generated portable provider schema | model-derived projector plus one generic public-boundary behavior proof |
| mechanical packaging/lock/resource relationship | named schema/compiler/build preflight |
| description clarity and usefulness | review plus Agent final-answer benchmark |
| accepted/rejected invocation behavior and custom validators | one generic public registry boundary test |
| tool execution result, persistence, side effect, or failure atomicity | focused integration test |
| critical user workflow | smoke/E2E |

## Broader Proof Reallocation

Agent Tool schema assertions are one instance of a broader problem. The
high-confidence migration set also includes:

| Current pytest claim | Better owner | Runtime proof that remains |
| --- | --- | --- |
| `test_ml_registry.py` enumerates the catalog size, every family/task/result axis, parameter default, and tuning grid | strict Pydantic catalog declarations and registry construction own unique keys, completeness, resolvability, and internally consistent policies | representative real fit/apply plus one catalog-metadata persistence/reload boundary |
| `test_knowledge_pipeline_boundaries.py` repeats every suffix, filter label, provider order, registry version, and source-size constant | `KnowledgeFormatRegistry` is the single declaration; construction must fail when a route is incomplete or contradictory | representative probe -> normalize -> route -> parse behavior |
| `test_agent_skill_catalog.py` greps exact Skill names, prose, asset keys, template versions, and scope membership | Skill frontmatter/assets plus `agent-skills-check`; prose has no duplicate test oracle | catalog load, activation, resource read, and one scope allow/deny boundary |
| Agent registry tests enumerate that particular Tool IDs are present or absent | typed composition allowlist, strict Pydantic input models, and Mypy-bound handlers | one registered invocation and one generic unregistered-tool rejection |
| `test_paddle_ocr_worker.py` repeats lock commits, DLL names, hashes, patch phrases, and greps C++ source for protocol words or forbidden subsystems | lock/build schema, `git apply --check`, compiled dependency/include/link allowlist, and native build preflight | real subprocess protocol, message bounds, self-test, deterministic archive, and exact-byte catalog binding |
| `test_resources.py::test_app_icon_is_packaged` only proves that the source icon exists | typed packaging resource manifest and package preflight | frozen application actually resolves and loads the icon |
| `test_build_info.py::test_source_version_is_project_version` compares two readers of the same `pyproject.toml` | `pyproject.toml` is the single source; release identity/static version check owns cross-file consistency | generated build information is read from the packaged product |
| the `.qm` existence assertion inside the MainWindow language-switch test | i18n compile/package preflight | live retranslation and persisted locale behavior |

Some cases must be split rather than deleted:

- embedding configuration defaults and the settings filename are model/source
  declarations; missing configuration causing a disabled adapter with no outbound
  request is runtime behavior;
- the exact cleaning-operation catalog, ordering, summaries, and parameters are
  typed catalog declarations; filtering, payload bounds, and rejection behavior
  remain executable;
- repeated ML workflow assertions for `model_family`, `model_task_kind`,
  `evaluation_kind`, and role schema repeat the catalog and should be removed,
  while training, application, artifacts, persistence, and output semantics remain;
- clustering, anomaly, and summary policy tests should not repeat the same policy
  constructor template for each task. Make invalid combinations impossible at
  construction and retain one representative no-split/no-follow-up behavior proof.

This does **not** justify a central assertion script full of domain-specific
string comparisons. Each domain owns its invariant and `pdm run check` only
orchestrates the appropriate proof mechanism:

- Agent Skill generation/check, Pydantic Tool input models, typed composition,
  and Mypy-bound handlers;
- Pydantic ML catalog construction and registry validators;
- Pydantic Knowledge format catalog construction and provider closure;
- Pydantic OCR lock/catalog parsing plus native-build preflight;
- i18n compiler and packaging preflight.

Exact defaults, counts, labels, and prose that already have one authoritative
source generally need no second assertion at all. A named build preflight is
warranted only for a mechanical relationship that spans authorities and can
drift; it must not be described as a type checker or linter.

Do not misclassify runtime contracts as static merely because their inputs are
schemas, configuration, or manifests. Settings persistence and migration, secret
stripping, release URL safety and frozen-environment precedence, corrupt or
hostile manifest rejection, archive/hash binding, SQLite/ORM/FTS/FK/unique
behavior, `_MEIPASS` resolution, Qt geometry/painting, and process/resource
lifecycle remain executable proofs. Qt style tests may be replaced by stronger
runtime visual/pixel probes, but not by source-string checks.

## Protected Proofs

Retain the following proof families:

- migrations, storage bootstrap, CAS/vector/document deletion and corruption
  handling;
- import worker crash, timeout, cancellation, and whole-process-tree termination;
- release identity, first-parent eligibility, immutable publication, interrupted
  upload convergence, and feed-last authority;
- OCR archive containment, hashes, atomic activation, and self-test;
- Agent/LLM cancellation, pending-frontier atomicity, no duplicate side effects,
  schema rejection before persistence, and secret redaction;
- persisted legacy/historical user data reopening without silent rewriting.

## Proposed Promotion Topology

Keep the public DAG simple:

```text
Promotion Contract
        |
        v
Tests [Python version x semantic shard]
        |
        v
Native CI Gate
```

Recommended first topology is full coverage on Python 3.12, 3.13, and 3.14 with
four semantic shards:

1. `analysis-data`;
2. `knowledge`;
3. `agent-llm-ui`, with MainWindow executed in its own second process;
4. `platform-release`.

This remains one matrix job definition and one stable aggregate gate even though
it schedules 12 Windows executions. Shard ownership must live in one test-suite
manifest, not duplicated YAML file lists. A mechanical guard must prove every
collected test belongs to exactly one shard. `check` runs once per Python version,
not once per shard.

The conservative pre-deletion critical path is about 15.5-16.1 minutes including
dependency setup. This is within the 18-minute target but leaves limited margin;
value reduction comes first. The first rehearsal must also prove that all 12 jobs
can enter one scheduling wave. If runner concurrency serializes them, topology
must be reconsidered rather than hiding queue time with a larger timeout.

Do not introduce `pytest-xdist` initially. Qt, multiprocessing, and native ML
state already require explicit clean-process boundaries.

## Adjacent Release Correction

`Native Release` currently calls `pdm run pytest --junitxml=...`. Any argument
causes `run_pytest.py` to bypass its two-clean-process default and run all tests in
one process. Reporting arguments and topology selection must be separated before
the release rehearsal. Exact-Tag-SHA Release Readiness should remain a focused,
high-value proof plus packaged smoke rather than another accidental monolithic
Promotion suite.

## Acceptance

- every retained case satisfies the value rule;
- every collected Promotion case belongs to exactly one semantic shard;
- all three frozen Python environments pass their assigned full matrix;
- MainWindow remains isolated from the non-UI process;
- `Native CI Gate` remains the only stable aggregate required context;
- at least five successful qualifying runs achieve controlled median `<=18 min`
  with no run over `25 min`;
- failed and timed-out rollout attempts remain visible in evidence rather than
  being filtered out of the timing report.

## Rejected First Implementation Pass

The following is retained as historical evidence, not the accepted design. The
first value-reduction and topology pass moved several assertions out of pytest
but implemented new assertion scripts instead of real static analysis:

- pytest collection fell from `718` cases in `74` files to `685` cases in `73`
  files. One obsolete observability module and the direct-delete candidates were
  removed; exact schema/default/count/prose censuses were removed or reduced to
  their remaining runtime behavior.
- Mechanical cross-authority relationships were temporarily moved into custom
  Agent, ML, and Knowledge assertion scripts. Design review rejected those
  scripts because changing the runner does not change a runtime assertion into
  static analysis.
- `tests/suites.toml` is the only shard/cohort authority. The checker discovers
  every test module, collects pytest once, and rejects missing file ownership or
  duplicate collected node IDs.
- `pdm run test` follows the manifest in clean cohort processes;
  `--promotion-shard <name>` selects a CI shard; `--direct` is required for a
  targeted pytest invocation. JUnit reporting no longer collapses the topology,
  and the MainWindow cohort remains isolated.
- Native CI derives its four-shard matrix from the manifest for all three Python
  versions. Exactly one shard per version owns `pdm run check`; the stable
  `Native CI Gate` remains the aggregate result.
- The encrypted PDF/DOCX/PPTX lifecycle cases retain real decryption, retry,
  retrieval, and password non-persistence, but use the import worker's in-process
  parser seam. Independent unencrypted format cases retain real Docling
  acceptance. The three lifecycle cases fell from roughly `85 s` combined to
  roughly `5 s`.

Historical local Python 3.14 evidence from that rejected pass:

| Shard/cohort | Result | Wall time |
| --- | --- | ---: |
| `analysis-data` | `110 passed` | `59.8 s` |
| `knowledge` | `204 passed, 3 skipped` | `241.8 s` |
| `agent-llm-ui` | `163 passed` | `44.0 s` |
| `main-window` | `63 passed` | `72.0 s` |
| `platform-release` | `142 passed` | `152.8 s` |
| static/domain checks | success; `685` items owned | `18.2 s` |

That pass suggested a local `knowledge` critical path near four minutes, but its
proof architecture was not acceptable and its counts are not final acceptance.

Workflow YAML parses successfully. `actionlint` and a Go toolchain were not
available in the local environment, so the workflow-specific lint proof remains
for CI or a suitably provisioned workstation.

## Design Review Correction

The first pass does not pass design review and must not be committed as-is. It
correctly identified low-value pytest assertions, but confused "not executed by
pytest" with static analysis:

- `check_agent_contracts.py` constructs production registries with dummy
  dependencies and executes assertions;
- `check_ml_catalog.py` dynamically traverses the catalog and repeats structural
  relationships;
- `check_knowledge_formats.py` instantiates production routing objects even
  though their constructors already reject incomplete provider closure;
- `test_suites.py check` invokes pytest collection and therefore remains a test
  harness operation, not static analysis;
- `compileall` proves syntax/import compilation, not type correctness;
- the absence of a linter allowed unused imports left by the refactor to survive
  until manual review.

The corrected proof topology is:

| Claim | Owner |
| --- | --- |
| unused imports, invalid imports, obvious defects, maintainability rules | Ruff |
| parameter/return/Protocol/nullability/union compatibility | a real type checker |
| external JSON/config/worker/tool/storage payload shape | strict Pydantic boundary model |
| valid combinations of task kind, policy, result, and capability | typed models, enums/Literals, discriminated unions, and model/registry validators |
| Agent Tool JSON Schema | generated from its Pydantic input model |
| OCR lock, translation catalogs, packaging inputs | named schema/compiler/build preflight |
| state transitions, persistence, side effects, failure atomicity, user result | pytest |
| shard file ownership and CI matrix | manifest parser/file-level topology validation, without pytest collection |

Pydantic is not itself a static type checker. Its role is to replace
`dict[str, Any]` at trust and serialization boundaries with explicit typed
objects so static analysis can follow internal code while runtime validation
rejects malformed external data. The intended modeling rules are:

- validate once at the boundary and pass validated models internally;
- use `extra="forbid"` for closed external contracts;
- prefer frozen models for identity and declaration values;
- use enums/Literals and discriminated unions instead of stringly typed modes;
- use field/model validators only for genuine local or cross-field invariants;
- derive schemas from models rather than maintaining parallel hand-written
  schema dictionaries;
- keep simple frozen dataclasses for internal values that do not need parsing or
  serialization.

Candidate boundaries for the corrected implementation are Agent Tool
arguments/results, ML catalog/policies, Knowledge format capabilities and
canonical/import worker envelopes, OCR lock data, configuration/task payloads,
artifact metadata, benchmark cases/results, SQLite JSON DTOs, and the test-suite
manifest. SQLModel rows remain persistence models and should not automatically
become domain DTOs merely because SQLModel builds on Pydantic.

Before mutation, run a read-only Ruff and type-checker spike against the current
PySide6, SQLModel, and Pydantic code. The resulting plan must distinguish:

1. issues immediately enforceable repository-wide;
2. legacy type debt requiring staged adoption;
3. boundaries worth converting to Pydantic in this CI/test slice;
4. deeper product refactors that belong in later task packets.

## Corrected Implementation and Local Acceptance

The design-review correction is now implemented locally:

- Ruff is the repository linter with a deliberately small high-signal gate.
- Mypy runs in `strict` mode over explicit typed boundary modules, uses the
  Pydantic plugin, and has no suppression baseline or blanket application-code
  ignore. Full-spike debt remains visible: BasedPyright `basic` reported about
  `1,040` issues and full Mypy about `737`, so pretending the entire legacy tree
  was already typed would have produced a dishonest gate.
- Strict Pydantic models now own the test-suite manifest, Knowledge format
  catalog/provider closure, ML catalog/registry invariants, OCR lock/catalog
  documents, and all production Agent Tool inputs.
- Production Agent Tool schemas are portable projections of those input models.
  The same Pydantic model performs execution admission and is passed to the typed
  handler; the JSON Schema is not maintained as a second authority.
- The rejected `check_agent_contracts.py`, `check_ml_catalog.py`, and
  `check_knowledge_formats.py` scripts are absent. Test manifest validation is
  file/topology validation and no longer invokes pytest collection.
- `pdm run check` now reports its layers accurately: Agent Skill
  generation/check, Ruff, strict Mypy, OCR lock preflight, test-manifest
  preflight, and Python compilation. Translation compilation remains a
  test/build preflight.

Corrected Python 3.14 local acceptance:

| Shard/cohort | Result | Wall time |
| --- | --- | ---: |
| `analysis-data` | `110 passed` | `78.26 s` |
| `knowledge` | `213 passed, 3 skipped` | `250.38 s` |
| `agent-llm-ui` | `165 passed` | `59.78 s` |
| `main-window` | `63 passed` | `88.92 s` |
| `platform-release` | `144 passed` | `183.45 s` |
| repository check | success; `73` files in `4` shards | about `9 s` |

The accepted local total is `695 passed, 3 skipped`. `pdm lock --check`,
translation compilation (`388/388` in both locales), OCR lock consistency,
workflow YAML parsing, `git diff --check`, Ruff, and strict Mypy also pass.

One deliberately concurrent local four-shard rehearsal produced a single
missing derivation-view assertion after the 53 MB PPTX import. That exact case
passed alone in `21.99 s`; the complete Knowledge shard then passed alone as
`213 passed, 3 skipped` in `250.38 s`. This remains visible as local
resource-contention evidence. GitHub's semantic shards run on separate runners,
so the next Promotion run must confirm it does not recur there.

The corrected local critical path is Knowledge at about `4.2 min`. With the
observed GitHub dependency-install baseline, the controlled Promotion estimate is
about `7.5-8.5 min`. This is not remote acceptance: all three frozen Python
versions, 12-job scheduling behavior, and the adopted five-run timing budget
still require Promotion PR evidence.

Workflow YAML parses successfully. `actionlint` is unavailable in this local
environment, so workflow-specific lint remains for CI or a provisioned
workstation.

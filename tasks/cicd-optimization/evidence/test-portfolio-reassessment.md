# Residual-risk Test Portfolio

## Decision

The previous 95-case candidate and 4-shard topology are withdrawn. They still
treated the existing implementation as the source of the test plan. The final
portfolio starts from costly Xenix-owned residual risk after static typing,
boundary models, database constraints, mature dependencies, application smoke,
packaged smoke, and benchmarks receive their proper authority.

The repository now collects exactly **30 pytest cases in 14 files**. There is no
hidden suite, parameter expansion, semantic shard manifest, or custom
pytest-equivalent assertion runner.

## Retained Cases

### Agent and user-facing result continuity — 4

- `test_agent_harness_first_slice.py` (2): Tool exchange and the one canonical
  XTT result survive storage/provider/chatbot composition.
- `test_analysis_profile.py` (2): bounded profile report and structured runtime
  failure are end-user analysis outcomes.

### Knowledge import and retrieval — 7

- `test_knowledge_import_authority.py` (1): a spawned worker produces a typed
  private-stage result and only the parent publishes canonical CAS content.
- `test_knowledge_retrieval.py` (3): Chinese keyword retrieval, semantic recovery
  of a lexical miss, and honest auto/explicit-semantic fallback behavior.
- `test_knowledge_lookup_tool.py` (2): the Agent receives one minimal value and
  may explicitly select semantic mode without a hidden fallback.
- `test_embedding_change_confirmation.py` (1): a user decision authorizes or
  cancels the compatibility-changing vector rebuild.

### Persistence and migration — 8

- `test_storage_bootstrap.py` (2): fresh schema and the oldest material supported
  upgrade preserve authoritative data.
- `test_storage_artifacts.py` (1): artifact ownership remains independent of chat.
- `test_migrations.py` (5): unknown-version rejection, current ORM/FTS/FK shape,
  one supported static fixture, deterministic duplicate repair, and preservation
  of an incomplete supported source shape.

### Release, update, and diagnostics — 11

- `test_release_identity.py` (4): exact promotion result, historical first-parent
  eligibility, side-branch rejection, and tag/project protocol identity.
- `test_release_publication.py` (3): feed-last publication, interrupted same-tag
  convergence, and pre-mutation version-regression rejection.
- `test_runtime_activity.py` (2): update exclusion during active work and verified
  retained database backup.
- `test_update_service.py` (1): user-visible check/download/apply composition.
- `test_diagnostic_bundle.py` (1): useful diagnostics without raw database
  disclosure.

## Explicitly Delegated Proof

Removed tests fell into recurring low-value patterns:

- **type/schema restatement**: invalid field indexes, enum values, Agent Tool
  schema snapshots, configuration coercion, missing primitive keys;
- **implementation-branch mirroring**: one case per defensive `if`, callback,
  retry branch, default, adapter call, or private helper;
- **library re-testing**: Qt widget mechanics, Pydantic validation, database/SQL
  library basics, process/file primitives, model-library behavior;
- **presentation wiring**: shell-open timing, footer cosmetics, right-click target,
  settings-tab wiring, and rebuild-sheet checkbox combinations;
- **combinatorial format/adapter matrices** already covered at the shipped frozen
  package boundary;
- **generic lifecycle matrices** created by the former distributed cancellation
  and synchronous deletion architectures.

The removals are not replaced by another custom script. Ruff, strict Mypy with
the Pydantic plugin, production model construction, constraints, application
smoke, packaged smoke, and live Agent benchmarks retain their distinct roles.

## Measured Result

Local Python 3.14.2 evidence:

| Measurement | Result |
| --- | ---: |
| collection | 30 cases in 2.35 s |
| full portfolio | 30 passed in 10.49 s |
| slowest case | parent/worker Knowledge authority, 2.66 s |
| second slowest | minimal Knowledge lookup, 1.18 s |
| all other cases | below 0.5 s each |

At this size, four Windows runners would multiply dependency installation,
scheduling, reporting, and failure surfaces for no meaningful wall-time gain.
One runner is the higher-ROI topology.

## Admission Rule for Future Tests

A new pytest case is eligible only when all are true:

1. it protects an Xenix product, authority, compatibility, or composition
   decision;
2. static typing/model construction, a database constraint, a mature dependency,
   smoke/package validation, benchmark, or observability cannot prove it more
   directly;
3. regression cost is material to users, data, security, or publication;
4. the case asserts the final observable outcome, not an internal call sequence.

The 100-case limit remains a hard ceiling, not a target. Crossing 50 cases triggers
a portfolio/architecture review before any new case is admitted.

# Native CI/CD Simplification

## Objective

Make native delivery proportionate to Xenix:

- `develop -> main` is reviewed and verified once through a promotion PR;
- one immutable `vX.Y.Z` tag on an eligible `main` promotion result authorizes
  Release and locks the Release SHA;
- Promotion CI uses static analysis and a small residual-risk acceptance portfolio,
  not a mirror of implementation branches;
- Release builds, exercises, and publishes that exact tagged source through the
  existing feed-last protocol.

v1.3.0 is consumed and immutable. v1.3.1 remains paused until this slice is
accepted and the resulting Promotion CI has supplied timing evidence.

## Guardrails

- Keep ordinary Native CI offline and at exactly 30 residual-risk pytest cases.
- Reuse one Agent benchmark case catalog, oracle, Judge, provider matrix, fixture
  hash, and result protocol across headless and headed execution.
- Do not replace the Subject provider or real fixture files with mocks/replays.
- Keep UI execution/integrity evidence separate from semantic answer quality.
- Do not commit, push, mutate GitHub controls, tag, or publish without separate
  authorization.

## Current Promotion Topology

```text
develop
  -> pull request to main
  -> Native CI (one Windows 2022 job, Python 3.14.2)
       -> install frozen dependencies once
       -> Ruff + strict Mypy boundary slice + declarative preflights
       -> 30-case residual-risk pytest portfolio
       -> JUnit evidence
  -> merge result becomes tag-eligible
  -> immutable vX.Y.Z tag
  -> Native Release on exact Tag SHA
```

There is no semantic shard manifest, test matrix, topology generator, synthetic
aggregate Gate, Candidate state, or second Publish dispatch. The single job itself
is the stable required check named `Native CI`.

An ordinary `develop` push does not run Native CI. GitHub's PR target filter owns
`base=main`; contributor guidance and review own the normal `head=develop`
convention. Exact tag preflight independently proves that a release target is a
completed same-repository `develop -> main` promotion result on `main` first-parent
history.

## Boundary and Ownership Corrections

### Knowledge managed process

- The Knowledge child process may write only beneath its private
  `tasks/imports/<import-id>/canonical` staging directory.
- Its request, events, and terminal result are strict Pydantic envelopes.
- The parent process alone validates the manifest and atomically admits staged
  canonical content into the content-addressed store.
- Cancellation authority is the parent-owned managed process boundary. The parent
  terminates the process tree; cancellation callbacks no longer leak through file
  I/O, parsers, OCR adapters, and content storage.
- Partial private staging is disposable. It is never authoritative document state.

### Knowledge document removal

- User deletion deactivates library membership in one database transaction.
- Retrieval and corpus fingerprints select only active membership, so an old
  vector generation cannot remain authoritative.
- Vector convergence is a separate index notification/rebuild concern.
- CAS reachability cleanup and task-log retention are background storage concerns,
  not synchronous delete substeps.
- Re-importing identical content reactivates the same document membership rather
  than manufacturing a new identity.

These ownership changes remove the need for Knowledge-specific matrices around
callback propagation, crash timing, path-by-path cleanup, reference counting, and
delete ordering.

## Proof Topology

- **Ruff** owns syntax, imports, and mechanically expressible lint facts.
- **Strict Mypy + Pydantic** own typed internal continuity and external envelope
  admission for selected trust-boundary modules.
- **Database constraints/migrations** own persistence shape and compatibility.
- **Mature libraries and the OS** own generic file, process, SQL, Qt, and model
  behavior; Xenix tests only material composition decisions.
- **30 pytest cases** own costly Xenix outcomes that cheaper mechanisms cannot.
- **Application smoke** owns boot and primary runtime composition.
- **Packaged smoke** owns the frozen bundle, DOCX/PPTX/native OCR import, lookup,
  deletion, and re-import journey.
- **Agent benchmarks** score the Agent's final analysis/advice; they do not assert
  Tool implementation details.

### Headed end-to-end benchmark

The end-to-end desktop acceptance is a headed execution mode of the existing
Agent Harness benchmark, not an ordinary pytest case or a second case catalog.
It reuses the same real-provider subject matrix, cases, fixture hashes, outcome
oracles, optional Judge, privacy rules, and persisted result protocol.

For each isolated cell, the headed adapter starts the real MainWindow and drives
the case through user surfaces:

- real source files enter through the chat composer file-drop surface;
- Knowledge preparation enters through the Knowledge Workspace file-drop surface
  and must become visible in its document list;
- the configured model is selected in the composer and the case prompt is
  submitted through the UI;
- the adapter waits for the rendered terminal Assistant outcome, then the
  case-owned oracle evaluates the same public Dataset/Artifact/final-answer state
  as the headless benchmark;
- window/service shutdown and isolated SQLite readability are integrity evidence.

UI execution failure and semantic answer quality remain separate result channels.
The adapter is case-agnostic and does not inspect or prescribe Tool traces. Normal
Native CI remains offline with 30 cases; headed execution is an explicit paid
Release/E2E acceptance using external untracked Subject, Embedding, and optional
Judge settings.

The exact retained portfolio and deletion rationale are recorded in
[`evidence/test-portfolio-reassessment.md`](evidence/test-portfolio-reassessment.md).

## Current Truth

- Shared runner lifecycle and the case-agnostic headed Qt adapter are implemented
  locally. The adapter uses the real MainWindow, Knowledge Workspace and composer
  file-drop surfaces, model picker, Send action, stream rendering, task queue, and
  runtime shutdown.
- Result schema v4 records `headless` versus `headed`; cases, outcome oracles,
  Judge dispatch, metrics, privacy boundaries, and persistence are shared.
- Both benchmark commands collect the same three cases offline. `pdm run test`
  remains exactly `30 passed`; `pdm run check` and application smoke pass.
- All three cases have completed through real visible windows, real fixture
  file drops, and `kimi/kimi-k2.6`. Knowledge used the configured
  `qwen3.7-text-embedding` service at batch size 20. Knowledge and chart passed
  semantically; the cleaning cell completed with valid integrity but exposed a
  real model-quality failure.
- Headed lifecycle acceptance found and fixed two process-owned resource leaks:
  desktop logging handlers now close with the application runtime, and the
  benchmark's SQLite integrity connection closes explicitly before isolated
  runtime reclamation.

## Verification

Local implementation evidence on Python 3.14.2:

| Proof | Result | Controlled time |
| --- | --- | ---: |
| Headless/headed benchmark discovery | same 3 cases in each mode | 8.04 s each |
| Full pytest portfolio | 30 passed | 11.58 s |
| Static checks/preflights/compile | passed; strict Mypy covers 18 modules | 4.8 s |
| Application smoke | passed | 77.8 s |
| Frozen package build | passed | 757.6 s |
| Packaged smoke | passed | 91.7 s |

Live headed evidence:

| Case | Execution | Integrity | Semantic | Subject time | Subject tokens |
| --- | --- | --- | --- | ---: | ---: |
| Knowledge rainy-season restock | completed | pass | pass | 65.61 s | 19,349 |
| Revenue by region chart | completed | pass | pass; same-model Judge | 69.21 s | 17,771 |
| April dine-in cleaning | completed | pass | fail | 1,102.37 s | 239,758 |

The cleaning oracle resolved a real output and confirmed report-row, header-row,
and exact-duplicate removal, but found that headers were not promoted, terminal
shape was wrong, and business rows differed. This is a valid benchmark finding,
not an infrastructure or UI failure. Full command/evidence interpretation is in
[`evidence/headed-benchmark-acceptance.md`](evidence/headed-benchmark-acceptance.md).

Remaining acceptance:

- the `main` required context must be transitioned from the removed
  `Native CI Gate` to the single `Native CI` job without opening a merge gap;
- at least five qualifying Promotion runs must record dependency, check, pytest,
  controlled-total, and queue time;

Performance budgets:

| Boundary | Budget |
| --- | --- |
| dependency bootstrap | median `<= 10 min` |
| repository check | `<= 1 min` |
| pytest portfolio | `<= 2 min` |
| controlled Promotion CI | median `<= 12 min` |
| controlled Promotion CI tail | no qualifying run `> 15 min` |
| cold tag Release to canonical feed | `<= 90 min` |

Queue time is reported separately from controlled execution. A `.venv` cache was
rejected after review: it is 2.83 GiB locally, while pull-request caches are scoped
to the PR merge ref and cannot amortize their upload across later promotion PRs.
Dependency-topology work requires its own measured slice if the cold-install budget
is missed.

## Prior P1 Disposition

- Locked native OCR cache and post-restore identity/self-test remain.
- Multipart/resumable OSS transfer and remote byte verification remain.
- Candidate reuse is obsolete; same-tag retry reuses only verified caches and
  byte-identical immutable public objects.
- Broad UI lifecycle automation is removed. Application and packaged smoke own
  shipped composition; only the expensive Embedding compatibility confirmation
  remains as a UI authority case.
- The operator surface remains one preflight/tag procedure and one release
  evidence surface.

## Mutation Boundary

Repository implementation is authorized. Do not commit, push, change GitHub
rulesets/Environments, create tags, or mutate OSS/public feeds without a separate
explicit instruction. Preserve unrelated dirty-worktree changes.

## Next Step

Review the cleaning semantic failure as an Agent-quality finding without weakening
its oracle. Then complete the remote required-check transition and Promotion timing
sample before authorizing v1.3.1.

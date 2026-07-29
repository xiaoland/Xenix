# Implementation Rehearsal and Pre-mortem

This is a mental execution of the plan against known repository behavior and the
real Radeon cell. Findings here alter task order and acceptance; they are not
deferred implementation notes.

## Execution Result

The delivered implementation preserved the no-rollback sequence. Real Cloud
validation found and corrected three recipe/operations hazards before admission:
the exact vLLM wheel filename, mirror-only `.DS_Store` acquisition noise, and
retirement cleanup when an older stopped generation lacked a control lock. A
default AMD package then exposed a malformed generated runtime hook; rebuilding
after the one-line newline correction passed. No failure was handled through
settings rollback, selection rewrite, endpoint persistence, or broad target
deletion.

The remaining hardware/UI walkthroughs are recorded as manual acceptance, not
as an architecture uncertainty.

## P0 Findings

### A removable feature cannot own a core import edge

Deleting only AMD UI is not a hard cut-off if a capability schema imports an AMD
reference, Agent composition imports an AMD factory, storage bootstrap imports an
AMD enum, or generic packaging unconditionally collects AMD resources.

TP-03–07 are therefore owner-neutral substrate. TP-19 may add exactly one
build-owned app composition contribution; TP-20 may add only a generic optional UI
contribution anchor; TP-21 keeps AMD packaging/diagnostics separate; TP-24 proves a
negative build. Old managed refs load as implementation-unavailable and released
AMD tables stay inert—neither can make generic startup fail or trigger fallback.

### Chat disconnect can currently replay a dispatched operation

The current OpenAI-compatible Chat path treats URL/timeout failures as retryable,
and `LLMService` owns retry loops. If an AMD binding disconnects after the server
may have received the request, ordinary retry can duplicate GPU work, streamed
text, or Tool Calls.

TP-04 must therefore introduce a capability-owned, dispatch-aware operation scope:

- one complete/stream pins generation and runtime incarnation across the whole
  outer retry loop;
- retry is permitted only when the attempt is known not to have dispatched;
- after possible dispatch, binding loss fails the current semantic operation;
- the next user operation may rematerialize a binding;
- stream abandonment and generator close release the generation permit in
  `finally`;
- diagnostic errors redact URL and token.

This seam must exist before TP-12 or TP-15.

### OCR authority currently disappears at the spawn boundary

Production Knowledge import constructs Paddle inside the spawned worker. A managed
reference cannot be resolved there because the AMD runtime directory and SSH
session are main-process authorities.

TP-07 must use this sequence:

```text
KnowledgeImportService parent
  -> OcrAttemptFactory.prepare(exact selected provider)
  -> acquire exact-generation permit and memory-only binding
  -> build frozen ordinary OcrSpawnSpec
  -> launch child
  -> child constructs Paddle or KServe/PAGE client without AMD imports
  -> child settles
  -> parent finally releases permit
```

The spec is never persisted in the import request/result/log, and the parent owns
the permit through cancel, timeout, crash, and child exit.

### Embedding binding must not enter `freeze()`

`freeze()` is used for profile inspection and must stay resource-free. One
`embed_texts()` permit covers every batch. If batch 2 may have dispatched before
disconnect, the operation returns no partial vectors and does not retry batch 2,
switch generation, or publish a vector generation.

The managed vector fingerprint uses component generation plus exact
model/tokenizer/manifest identity. It never uses a loopback URL, port, runtime
incarnation, or aggregate profile revision.

## Phase Rehearsal

| Phase | Injected failure | Required behavior and owning task |
| --- | --- | --- |
| Intent/compatibility | Unsupported GPU/ROCm, changed SSH host key, insufficient disk/VRAM, double-click deploy | TP-10 rejects before installation/settings mutation; TP-11 serializes one installation command; no placement/API fallback |
| Acquisition | HF/Xet 401, TLS/source mismatch, prerelease resolution, interrupted download, stale cache lock | TP-10/TP-16–18 use exact refs, hashes, plugin allow-list, generation-owned temp roots, and never publish partial artifacts |
| Install/start | Service port opens before model ready, process/PID/port reused, systemd absent, first compile slow | TP-09/TP-15 use process-group/start/command/incarnation identity and phase-aware deadlines; PID file is never stop authority |
| Self-test | Health passes but Tool, vector shape, PAGE, or ROCm device proof fails | TP-16–18 leave generation unverified and unregistered; no CPU or external-API fallback |
| Registration | Crash after one domain, dirty Settings dialog later saves, G2 reuses key | TP-03–05/07/11 use per-document CAS and generation-specific IDs; restart only ensures missing exact projections; selection stays unchanged |
| First operation | Chat stream disconnect, Embedding batch 2 disconnect, OCR child loses tunnel | TP-04/05/07 and TP-12–14 fail current operation without semantic replay; next operation may get a new binding |
| App restart | Crash after target realization but before verification; partial domain registration | TP-08/11 rebuild desired state from SQLite, fence old incarnation, verify exact realization, and continue only forward |
| Repair | Same path contains wrong digest; requested repair would change manifest | TP-11 repairs only the same exact manifest realization; a technical descriptor change creates a new generation |
| Upgrade | Selected G1 prevents G2 coexistence due VRAM/disk | TP-11 reports G2 `BLOCKED/NOT_READY`; G1 stays selected and operational |
| Retire | Selection races projection mark; stream/child in flight; controller crashes after `RETIRING` | TP-09/11 commit desired absence and close the exact generation gate, drain issued permits, expose `REMOVAL_BLOCKED`, never mutate selection, and never resurrect |
| Cleanup | Stale controller callback sees new process; PID reused; SSH disconnected | TP-09/15 reject cleanup unless generation, owner, start, command, process group, and incarnation all match |
| Feature cut-off | AMD package/resources absent; old DB/settings remain | TP-19–24 keep one optional composition edge; generic startup/package passes; refs are typed unavailable; migrations remain inert |

## Environment Findings That Shape the Design

The captured Radeon Cloud cell has Python 3.12, no preinstalled Python 3.14, uv,
or PDM, no GUI session, and PID 1 is Jupyter rather than systemd. `systemctl`
reports offline. The three feasibility listeners are stopped and the product root
is absent.

Consequences:

- Local Linux acceptance is headless and must bootstrap its declared Python/tool
  runtime or use a packaged self-contained controller;
- neither Local nor SSH placement may rely on systemd or a desktop session;
- process supervision and cleanup are application-owned;
- reachable SSH is a target prerequisite—one-click does not provision the cloud
  instance or start its initial sshd;
- the current lab remains unsuitable for cold acceptance because its ambient
  model/runtime/compile caches already exist.

## Sequence Corrections

The rehearsal rejects these tempting orders:

- SSH installer before settings/capability seams;
- deployment facade before the fake lifecycle kernel;
- KServe adapter before Paddle-neutral Knowledge extraction;
- runtime binding acquisition inside Embedding `freeze()` or the OCR child;
- registration combined with provider selection;
- upgrade implemented by stopping selected G1;
- cleanup authorized by PID, port, or a newly empty permit counter.
- generic-to-AMD imports, import-time factory registration, ambient entry-point
  discovery, or unconditional AMD packaged-smoke/resource collection.

The accepted sequence is represented in [the dependency
graph](dependency-graph.md).

## Verification Hooks Required Before Real I/O

- deterministic failpoint after every lifecycle phase and managed settings write;
- controlled clock, ID, capacity, port allocator, and request deadline;
- process identity/incarnation and late-callback probes;
- SettingsStore CAS/event observer and second-writer process;
- Chat server-received-then-disconnect fixture;
- Embedding later-batch-received-then-disconnect fixture;
- live OCR child, cancel, timeout, and binding-loss fixture;
- acquisition source/bytes/hash/cache tracer;
- log/command/settings/result scanner for tokens, live endpoints, PIDs, private
  content, and host material.
- AMD-absent subprocess, AST import graph, inert old-database/settings fixture, and
  negative package/resource inventory.

These hooks belong in the relevant lower-level tasks, not in a late end-to-end
test-only layer.

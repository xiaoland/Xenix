# Current Adapter Seams

This file records repository evidence for the OCR structural change, the
OpenAI-compatible relationship, and the proposed private SSH AMD deployment module.
It is not an implementation decision.

## OCR: Useful Seams Already Present

`src/xenix/services/paddle_ocr_service.py` already separates several responsibilities:

- `PaddleOcrDeploymentService` owns verified bundle materialization, activation,
  status, repair, runtime resolution, and self-test.
- `PaddleOcrService` is a small invocation facade over the deployment.
- `PaddleOcrSession` owns one reusable child process/model initialization and
  exposes `recognize(...)`.
- the child returns bounded, normalized text regions instead of writing Knowledge,
  SQLite, indexes, or Artifacts.
- `InlineKnowledgeImportWorkerRunner` can inject an OCR object for deterministic
  tests.

These are good starting seams. The service was not designed as a general engine
registry, however.

## OCR: Paddle Leakage to Extract

The production path still binds engine identity above the concrete adapter:

- `src/xenix/services/knowledge_import_worker.py` constructs
  `PaddleOcrService(PaddleOcrDeploymentService(...))` inside the spawned worker.
- `ParseExecutor` types its dependency as `PaddleOcrService`, even though invocation
  mostly uses `is_ready`, optional `open_session`, `runtime_descriptor`, and
  `recognize`.
- PDF and image routing uses `paddleocr-*` route identifiers.
- parser helpers, log names, and provenance fields name Paddle.
- the Workspace service and UI consume `PaddleOcrDeploymentService`,
  `PaddleOcrStatus`, and `PaddleOcrState` directly.
- runtime descriptor validation is structurally useful but fixed to the current
  Paddle-era field set.

The minimum structural change is not a general plugin system. It is:

1. Define engine-neutral OCR facade, session, descriptor, and normalized-result
   contracts at the Knowledge/OCR boundary.
2. Make routing describe semantic OCR decisions rather than an engine name.
3. Move concrete backend construction into an explicit spawn-compatible
   composition/factory input.
4. Keep Paddle as the first adapter and prove no behavior/provenance regression.
5. Add an admitted KServe V2 OCR provider only after the neutral seam and
   standards/output mapping are real. ROCm remains a Local or Private SSH
   deployment/provenance fact rather than an OCR adapter type.

## LLM and Embedding

Chat already has an `AgentProvider` protocol and one
`OpenAICompatibleChatProvider`. `LLMSettings` supports multiple configured provider
instances and model references, but every current `LLMDialect` is
`openai_compatible`. `LLMService` still constructs the concrete provider directly
from static endpoint settings, so the proposed capability-owned factory is a new
seam rather than an existing extension point. The free-form `dialect_config` is not
an acceptable home for a managed generation reference.

Embedding already exposes `EmbeddingService` and immutable `EmbeddingSession`
protocols. `OpenAICompatibleEmbeddingService` is the current implementation and
freezes a compatibility profile for an operation. Its settings support only one
provider instance today.

Consequences:

- An AMD `llama.cpp` or vLLM endpoint that speaks the same HTTP dialect should reuse
  the OpenAI-compatible adapter.
- LLM can accept an automatically registered managed provider after its static
  endpoint fields gain an explicit tagged managed-reference alternative and its
  service receives an LLM-owned provider factory port.
- App composition already creates one LLM and one Embedding settings-service
  instance, but both still write complete JSON documents directly. The Settings
  dialog is long-lived, loads snapshots when constructed, rebuilds whole LLM and
  Embedding settings, and saves them sequentially without revisions or background
  change notification. Singleton identity therefore does not prevent a stale dialog
  from overwriting an AMD registration, and one domain can commit before the other
  fails.
- The required seam is one app-scoped physical settings store with per-document
  revision/CAS, atomic publication, and post-commit events. Domain settings services
  remain semantic owners, are the only consumers of that store, and expose typed
  user-edit and managed-provider commands; UI and AMD deployment call those services
  and never receive the store or submit a complete shared settings document.
- Store notification is only an opaque document revision. Domain settings owners,
  not the store, produce typed/redacted events for UI and read-only snapshots for
  inference.
- LLM conversations persist `selected_fq_model_key`, while settings also distinguish
  default, guard, and title model references. Their owner must define which durable
  references block provider removal and how a non-blocking stale reference fails or
  migrates.
- Embedding needs a compatibility migration to provider instances plus one active
  provider reference before AMD deployment can register rather than overwrite it.
- Embedding `freeze()` is also used for profile inspection and must remain
  resource-free. A managed adapter acquires a generation permit per `embed_texts`,
  and the vector-space identity uses model/tokenizer/component generation rather
  than a dynamic URL.
- AMD target/runtime/artifact identity must supplement embedding profile identity;
  otherwise a changed backend/model generation could incorrectly reuse an existing
  vector index.
- The optional Dedicated Model API is another remote endpoint binding, not an AMD
  wire dialect.
- vLLM's documented OpenAI-compatible serving surface includes Chat/Completions,
  Responses, and Embeddings, but does not define a general structured document OCR
  endpoint. OCR protocol selection therefore follows the separate standards review:
  <https://docs.vllm.ai/en/stable/serving/online_serving>.

## SSH ML Worker

The existing ML worker pool supplies valuable precedent:

- local and SSH execution adapters are selected by local services;
- key/agent-based configuration and remote setup are guided;
- request files are staged, execution occurs remotely, and bounded outputs are
  downloaded;
- task success and Artifacts are finalized locally.

It is not the new inference owner:

- selection currently ignores the declared `capabilities` list;
- it runs bounded batch entrypoints rather than reusable OCR/model processes;
- ADR 0005 explicitly excludes a remote HTTP API or always-on daemon from this
  worker design;
- its failure and concurrency semantics do not define endpoint health,
  port-forwarding, streaming, reconnect, or remote process leases.

A remote AMD target can reuse proven SSH primitives only after separating them from
batch-worker policy. Long-lived inference needs `AmdAiDeploymentService`, a
closeable runtime session, and a durable lifecycle decision.

## Deployment Service Precedent

`PaddleOcrDeploymentService` is the closest deep-module precedent: it owns verified
materialization, immutable generation identity, status, self-test, activation,
repair, and removal without owning Knowledge semantics. The proposed
`AmdAiDeploymentService` applies that lifecycle pattern to one managed AMD
installation and delegates three component deployments plus a Local Radeon or
Private SSH placement controller internally. Paddle's local child-process lifecycle
is a useful local-controller precedent, not evidence that its current runtime is an
AMD backend.

The two lifecycles must never own the same generation. Existing Paddle compatibility
generations remain Paddle-owned. An AMD `ComponentGenerationRecord` is owned by the
desktop installation authority, while its Local/SSH driver owns only the target
realization and observations.

`EmbeddingProfile` is the closest immutable operation-identity precedent. An
`AmdExecutionProfile` may likewise be an immutable resolved value referenced by
`InstallationSpec`, while component manifests own technical release descriptors,
generation records own lifecycle, and live/aggregate status remains a separate
projection.

The current Chat and Embedding configurations persist static `base_url`/credential
facts. Each private SSH capability instead needs its own immutable managed provider
reference containing installation and component-generation identity, with no
secret, URL, port, connection, or health. A shared cross-domain
`ManagedEndpointRef` is unnecessary because component identity is implicit in the
capability settings domain. At app composition, the AMD module registers three
adapters behind the separate capability-owned factory ports; those adapters use an
AMD-private exact-reference runtime directory and construct ordinary
operation-pinned providers. Capability services never resolve endpoints or release
permits. Live listener,
local process or SSH upstream, reconnect/restart, generation fencing, and operation
admission remain inside the private AMD composition/runtime boundary; the detailed
comparison is in
[dynamic endpoint options](dynamic-endpoint-options.md).

The settings persistence evidence and proposed single-writer boundary are in
[settings mutation authority](settings-authority.md). The Local Radeon versus
Private SSH driver boundary is in
[execution placement options](execution-placement-options.md).

OCR has no provider settings today. A new `OcrProviderConfig`, selected-provider
reference, and factory must preserve Paddle as the local compatibility instance and
admit the remote protocol provider without letting either engine name leak into
Knowledge routing.

The production worker constructs Paddle inside the spawned process, so injecting a
main-process factory alone is insufficient. OCR requires a spawn-safe engine-neutral
spec/factory plus neutral status and runtime-descriptor projections. Broad
validation/provider errors can currently collapse into unavailable/no-text
behavior; the neutral contract must distinguish a legitimate empty result from a
typed transport/protocol failure before Knowledge applies its page/document
partial-result policy.

The protocol research and standards-first gate are in
[OCR protocol options](ocr-protocol-options.md).

## UI and Platform

Qt/PySide6 is available on Linux, but interactive Qt Widgets require a usable QPA
window-system path such as X11/xcb or Wayland. The Radeon Cloud guide documents
JupyterLab, SSH, Dedicated Model APIs, and `rc-tunnel`; it does not promise a display
server or remote desktop:

- <https://doc.qt.io/qt-6/linux-requirements.html>
- <https://doc.qt.io/qt-6/qpa.html>
- <https://github.com/AMD-DEV-CONTEST/Radeon-hackathon-2026-07/blob/main/Radeon-Cloud-User%20Guide/README.md>

The repository's accepted packaging and distribution path remains Windows, and ADR
0009 fixes the current OCR bundle to Windows x64. “PySide supports Linux” therefore
means a Linux port is technically plausible, not that Xenix already has a supported
Linux product or that Radeon Cloud can display it. The selected product topology no
longer depends on that possibility.

# AMD Deployment Scheme Review

**Review date:** 2026-07-28
**Verdict:** proceed with a placement-neutral, no-rollback, forward-reconciling
design after the remaining admission conditions below are made executable. This is
a scheme review, not an implementation plan or authorization to change product
code.

## Root Finding

The two original P0 findings had one root cause: the earlier design tried to create
an aggregate transaction across three independently authoritative settings domains
and an AMD deployment domain, then recover with copied before/after snapshots and
compensating rollback.

That premise produced both failures:

1. full settings snapshots duplicated secrets and could overwrite user changes made
   after the snapshot;
2. aggregate profile activation could leave LLM, Embedding, and OCR selections on
   mixed generations after a crash or failed compensation.

The correction is not a more elaborate rollback journal. It is to remove the
cross-domain atomicity claim.

The second review then found two additional P0-level correctness questions in
removal: racing new-operation admission and persisted LLM model references. They
are not remnants of rollback; they are authority/linearization issues that become
visible once rollback machinery is removed. The table below distinguishes the two
original rollback-derived P0s from these newly surfaced removal P0s.

The third review found two more architectural defects:

1. the current development machine's lack of AMD hardware had incorrectly turned
   private SSH into the only product placement, excluding a user with a compatible
   local Radeon from one-click deployment;
2. the settings design had treated serialized writes as sufficient even though UI
   and deployment could still submit stale whole-document snapshots. One
   application-scoped persistence writer plus domain mutation commands and
   revisions is required.

The fourth review audited complexity isolation, extension axes, boundaries, and
ownership. It found that the direction was sound but several statements would
still create coupled or duplicate authorities if implemented literally:

1. desktop installation state and the target were both said to own component
   generations;
2. managed provider identity did not guarantee that G1 and G2 were different
   selectable instances;
3. the removal preflight still relied on a cross-domain point-in-time truth;
4. placement identity could appear to change within one installation;
5. `READY`, settings notification, provider factories, and the public facade still
   crossed their intended boundaries.

The accepted corrections are detailed in
[architecture boundary review](evidence/architecture-boundary-review.md).

## Adopted No-Rollback Model

### Authority

| Fact | Sole authority | Other representations |
| --- | --- | --- |
| Installation lifecycle, immutable placement, component generation identity, desired presence | Desktop AMD installation record through its coordinator | Target realization and status projections |
| Component artifact/runtime/model/protocol/self-test descriptor | Versioned component manifest | Generation pins its digest; settings store normalized metadata only |
| Settings document revision and durable mutation order | One app-lifetime `SettingsStore`, per document | Domain settings services submit validated commands |
| Provider catalog and active/default selections | Each capability's settings owner | AMD-managed entries are tagged projections |
| Conversation-pinned LLM model reference | Conversation/LLM domain | Retirement blocker/status input, never deployment-owned |
| Local or SSH realization/process/connection/forward/health/live binding | Placement-specific `AmdExecutionSession` | Memory-only HTTP binding snapshots |
| Admission and scoped use of one AMD generation | Private per-generation AMD runtime gate | Capability adapter holds the permit for its semantic operation |
| Inference meaning, retry, stream, batching, OCR import result | Chat, Embedding, or OCR capability owner | AMD adapter maps its permit to that operation boundary |
| Knowledge, index, conversation, Dataset, Artifact | Existing desktop owner | Execution target has no canonical copy |

`AmdDeploymentIntent` is command input; immutable `InstallationSpec` fixes one
placement and resolved profile; the component manifest owns exact technical
requirements; the generation record pins that manifest and owns lifecycle. If
`AmdExecutionProfile` remains as a name, it is an immutable value inside the
installation spec, not a service or live status.

`AmdAiDeploymentService` remains the placement-neutral public control-plane facade,
but an internal coordinator/repository, compatibility planner, driver registry,
managed-component participants, and status projector isolate its responsibilities.
AMD capability adapters are sibling composition components and never route through
the facade. A private `AmdExecutionSession` implementation owns one Local Radeon or
Private SSH realization; Local and SSH retain different process, trust, transport,
cleanup, and diagnostic state. A custom transport gateway is not part of the
baseline topology.

### Installation and registration

Each component deployment creates an immutable generation. After artifact
verification, target/process identity verification, protocol self-test, and ROCm
workload evidence, the deployment reconciler submits a managed-provider command to
the matching `LLMSettingsService`, `EmbeddingSettingsService`, or
`OcrSettingsService`. That domain owner alone resolves current state and commits the
AMD-owned projection through the physical `SettingsStore`.

The provider-instance identity is immutable and generation-specific. An ensure for
G2 creates a second entry and cannot redirect a selected G1 entry behind an
unchanged key. The command carries capability-normalized immutable metadata and the
component-manifest digest as a projection, never live endpoint or health data.

The reconciler:

- stores no previous or desired whole-settings snapshot;
- copies no provider secret;
- never restores an old settings file;
- never mutates a capability's active/default selection;
- submits an owner-scoped domain command rather than reading or saving a complete
  settings document;
- relies on the domain service to use the single `SettingsStore`
  revision/serialization boundary so a stale UI edit and background reconcile
  cannot silently overwrite one another;
- resumes missing upserts after restart and leaves unrelated provider entries
  untouched.

Registration presence, component verification, transport reachability, user
selection, and derived product status are separate facts. A deployment can be fully
registered without being selected. `Installed` may mean all required generations
are verified and their exact managed projections exist; `Operational` additionally
depends on current runtime observations. Neither status asserts that capability
settings currently select AMD, and neither is persisted as a second `READY` truth.

Partial registration is safe because a managed reference is materializable only
when its exact component generation is verified and not retiring. Whether a verified
single component may be selected before the complete profile is installed or
operational is a capability/product policy that must be decided explicitly; it is
not inferred from registration.

### Upgrade and recovery

Upgrade prepares a new immutable generation while the selected old generation
remains undisturbed. If the target cannot host or self-test old and new generations
within its resource limits, upgrade remains `BLOCKED` or `NOT_READY`; it must not
stop the selected old generation to manufacture progress.

A failed new generation becomes `FAILED` or `REPAIR_REQUIRED`. Recovery is a new,
explicit forward command against authoritative current state. Retaining an older
generation as a recovery candidate does not make it a rollback target, and no
journal replay restores settings snapshots.

### Dynamic endpoint

Each capability owns its provider factory port. Its AMD implementation uses an
AMD-private installation runtime directory to locate the exact placement-specific
`AmdExecutionSession`; it never calls the deployment facade or closes over one
global session. Before materializing a memory-only HTTP binding, the adapter obtains
a private per-generation admission permit at the capability's natural operation
boundary:

- Chat: one complete request or stream, including its internal retries;
- Embedding: one `embed_texts` operation, including all batches;
- OCR: one parent import attempt from spawn preparation through child exit.

The operation pins `(installation_id, component_generation_id,
runtime_incarnation)` for its entire lifetime. An SSH disconnect fails the current
operation honestly; a local process/device failure has the same current-operation
semantics. The next operation may obtain a new local port or runtime incarnation.
No operation silently changes generation or replays a partially sent request.
Every binding publication verifies the target process identity, so port reuse
cannot connect an old reference to a new generation. No URL, port, token, health
fact, or connection handle is persisted.

Chat releases the hidden permit in `finally` across retries/full streaming,
Embedding keeps `freeze()` resource-free and holds one permit per `embed_texts`,
and the OCR parent holds one through child exit. The private binding is named
`LoopbackHttpBinding`; generalizing it to arbitrary transports before a real need
would obscure the current HTTP contract.

Each capability owns a small domain-specific managed provider reference with
`installation_id` and `component_generation_id`; the component is implicit in that
domain. The serialized fields may be parallel, but there is no shared public
`ManagedEndpointRef` type or global provider registry.

### Removal

Removal is a monotonic desired-absence transition:

1. the explicit user request commits desired absence and `RETIRING` in the
   installation authority;
2. the same installation-runtime command closes new admission for the exact
   generation, while already-issued scoped permits remain counted;
3. forward reconcile asks each settings owner to mark its exact managed projection
   retiring and unavailable for new selection without changing existing selection;
4. existing operations finish or fail under their own contracts; zero HTTP
   connections is not proof of scoped quiescence;
5. active/default selection or an LLM-owned durable-reference rule produces a
   visible `REMOVAL_BLOCKED` status until the user/domain resolves it;
6. each settings owner atomically removes its exact entry after its own blockers
   clear; only after all projections are absent and scoped use is zero does the
   runtime remove target realizations and reach `REMOVED`;
7. crash recovery only continues toward absence; normal registration reconcile
   cannot resurrect a retiring generation.

The previous all-domain preflight/zero-mutation promise is rejected. It can race
with a new selection, while reserving three domains atomically would recreate a
two-phase cross-domain transaction. A racing selection either commits before the
domain retirement command and becomes a blocker, or is rejected by the now
retiring/absent catalog entry. The AMD gate is already closed, so it cannot start a
new generation operation. Normal live retirement drains issued permits rather than
canceling Chat, Embedding, or OCR operations; crash-orphan cleanup follows its
separate bounded policy. Deployment does not select a fallback provider.

The LLM domain must separately classify durable references such as conversation
`selected_fq_model_key`, default, guard, and title model selections. References
declared blocking prevent removal; non-blocking stale references must later fail or
migrate according to an LLM-owned rule. Deployment must never rewrite conversations.

## Issue Dispositions

| ID | Review issue | Disposition | State |
| --- | --- | --- | --- |
| P0-1 | Rollback snapshots duplicate secrets and can restore stale user settings | Delete snapshots, compensation, and settings restoration. Deployment submits only an owner-scoped managed-provider command; the domain owner commits it through the versioned settings store. | Design corrected |
| P0-2 | Aggregate activation can leave mixed old/new selections | Deployment never changes active/default selections. Three selections remain independent capability facts; product status is only a derived projection. | Closed by boundary change |
| P0-3 | Removal idle check races with a new operation | Commit `RETIRING` and close the private per-generation gate in the same installation-runtime command; hidden adapter permits span the complete capability operation. | Authority corrected; proof mechanism open |
| P0-4 | Removal can delete a provider still referenced by a persisted LLM thread | LLM owner classifies durable references as blocking or deterministically stale; deployment only consumes that decision and never migrates conversations. | Product/LLM policy open |
| P0-5 | SSH-only topology excludes one-click deployment for a compatible local Radeon | Make deployment/component lifecycle placement-neutral; use distinct Local and Private SSH target sessions behind one facade. Local is a required product placement, while exact native/WSL/Linux cells remain evidence-gated. | Topology corrected; local acceptance open |
| P0-6 | A singleton object can still serialize stale whole-settings overwrites | Make one app-lifetime `SettingsStore` the only physical writer; UI and AMD call the relevant domain settings service with revisioned typed commands, and only that service accesses the store. | Authority corrected; persistence mechanism open |
| P0-7 | Desktop installation and execution target both appear to own component generations | Desktop `ComponentGenerationRecord` owns normative ID/manifest/lifecycle; placement driver owns only the target `GenerationRealization` and returns evidence. | Ownership corrected |
| P0-8 | G2 may replace G1 behind the same provider-instance key and silently move an existing selection | Managed provider identity is immutable and generation-specific. G2 creates a new entry; same ID plus different exact ref is an owner conflict. | Required identity invariant |
| P0-9 | All-domain removal preflight can become stale before `RETIRING` | Remove the zero-mutation preflight promise. Record monotonic retirement first, close the AMD gate, then forward-mark/remove each domain projection; blockers produce `REMOVAL_BLOCKED`, never rollback. | Protocol corrected; LLM reference policy open |
| P0-10 | Placement can appear selected at composition or changed by creating only a generation | Composition registers drivers; immutable `InstallationSpec` selects one tagged target. Changing Local/SSH creates a new installation. | Ownership corrected |
| P1-1 | Gateway connection drain is not semantic operation drain | Remove the gateway from the baseline and define Chat/Embedding/OCR operation scopes. Connection count is not a correctness signal. | Closed at topology level |
| P1-2 | A reconnect/restart or reused port can route an operation to the wrong generation | Pin exact component generation and memory-only runtime incarnation for the whole operation; verify target process identity before publishing a binding. | Required admission invariant |
| P1-3 | Forward-only upsert can still lose concurrent UI edits | Promoted and consolidated into P0-6 after confirming that singleton identity cannot prevent a stale whole-document save. | Superseded by authority correction |
| P1-4 | Partial registration conflates verified, registered, reachable, selected, and ready | Model them separately; never equate automatic registration with selection or aggregate activation. | Closed conceptually; selection policy open |
| P1-5 | No-rollback upgrade assumes old/new generations fit simultaneously | Keep the selected old generation untouched; if the new generation cannot coexist for self-test, report upgrade blocked/not-ready. | Closed by fail-safe policy |
| P1-6 | Accepted removal can be reversed by normal reconcile | `RETIRING` closes admission and establishes desired absence; restart can only continue retirement/removal, including a visible blocked state. | Required state-machine invariant |
| P1-7 | Two clients may manage the same installation | Require placement-appropriate owner/incarnation fencing before either local or remote controller may publish or remove a generation. | Required target admission evidence |
| P1-8 | Shared `ManagedEndpointRef(component=...)` creates a cross-domain abstraction | Let each capability own its two-field managed reference; component identity is implicit in the domain. | Closed by data-shape change |
| P1-9 | Runtime session and custom gateway both claim live binding authority | Keep the placement-specific `AmdExecutionSession` as sole live authority. A gateway may be reconsidered only for a measured continuity SLO, never for correctness. | Closed at topology level |
| P1-10 | “UI or Agent cannot select AMD placement” also rejects legitimate provider selection | Reject only Agent/per-request placement selection. Settings UI may deploy AMD and independently select a capability provider. | Wording corrected |
| P1-11 | OCR transport failures can look like “no text” or silently publish a partial result | Return a typed provider/transport failure. The Knowledge import owner explicitly decides page-level partial assembly versus whole-import failure; canonical generation publication remains atomic. | Product failure policy open |
| P1-12 | KServe V2 has no standard server-side cancellation | Promise only local attempt cancellation/stop-waiting; remote compute may continue until a bounded server deadline. Hard remote cancellation requires an admitted extension. | Corrected; runtime bounds need proof |
| P1-13 | The OCR request/document/page boundary is ambiguous | One request contains exactly one decoded logical image and returns exactly one PAGE `PcGts/Page`; Xenix owns PDF/TIFF splitting, page identity, order, and document assembly. | Closed conceptually |
| P1-14 | PAGE and ALTO fixture equality was overstated | PAGE-only is the leading product profile. ALTO remains comparison/compatibility evidence and needs separate admission if enabled. | Closed |
| P1-15 | PAGE line hierarchy, reading order, and coordinate mapping are underspecified | Define detected text line as the normalized unit, place `TextLine/TextEquiv index=1` under `TextRegion`, define region reading order, and inverse-map all server transforms to exact request-image pixels. | OCR profile blocker |
| P1-16 | PAGE integer coordinates conflict with Xenix float polygons | Admit any finite polygon with at least three points in Xenix; define bounded nearest-pixel PAGE quantization plus error, bounds, self-intersection, and containment checks. | OCR profile blocker |
| P1-17 | Custom KServe metadata tokens were treated as standard negotiation | Pin OCR profile/schema/model generation in the immutable deployment manifest and self-test; validate standard tensor metadata without claiming a standardized extension token. | Closed conceptually |
| P1-18 | OCR resource limits cover compressed bytes but not parser/decode amplification | Quantify compressed input, decoded pixels/bytes, dimensions/channels/frames, response/tensor/XML bytes, XML structure, region/point/reference counts, deadlines, concurrency, and in-flight memory; fail closed. | OCR profile blocker |
| P1-19 | The spike is self-client/self-server evidence only | Keep it as wire/schema evidence. Product admission still requires a real ROCm OCR runtime and preferably a second compatible client/server implementation. | Evidence open |
| P1-20 | `READY` mixes durable generation lifecycle, live health, registration, selection, and UI rollup | Remove persisted generation `READY`; derive `Installed/Operational/Blocked/Degraded` from independently owned facts with reasons and observation time. | State model corrected |
| P1-21 | Public deployment facade is described as owner of state, compatibility, Local/SSH I/O, status, and request adapters | Keep one deep facade, but isolate an internal coordinator/repository, compatibility planner, driver registry, managed participants, and status projector. Capability adapters are siblings. | Boundary corrected |
| P1-22 | Settings service, store, UI events, and inference use one broad path | Same domain service implements narrow snapshot, user-command/event, and AMD managed-projection ports. Store emits only opaque per-document revision notification; domain owner emits typed/redacted events. | Boundary corrected |
| P1-23 | Durable provider catalog and process-local provider factory are conflated | Capability owns both as separate concepts: catalog owns instances/selections; factory registry owns only composition. AMD implements a capability-owned factory port. | Boundary corrected |
| P1-24 | An AMD adapter that closes over one session cannot support multiple installations | Use an AMD-private exact-reference runtime directory; it is not persisted, public, or capability-visible and does not call the deployment facade. | Topology corrected |
| P1-25 | Generic `OperationBinding` actually promises HTTP URL/token | Name the baseline `LoopbackHttpBinding`; introduce a private tagged transport only if a non-HTTP protocol is admitted. | Naming/boundary corrected |
| P1-26 | Profile, manifest, generation, observation, attestation, and provenance duplicate technical fields | Adopt the one-way data chain from intent to installation spec, manifest digest, generation, realization, attestation, and capability projection. | Ownership corrected |
| P1-27 | Three concrete settings services/adapters are hard-coded into deployment lifecycle | Compose a private managed-component participant collection containing projection/status ports only; current required members remain explicitly LLM, Embedding, and OCR. | Extension seam corrected |
| P1-28 | Two-field managed ref alone cannot render model/profile compatibility metadata | Capability settings store a normalized immutable projection plus manifest digest; manifest remains technical authority and live binding data remains excluded. | Projection contract corrected |
| P1-29 | Controller crash loses in-process permits while remote inference may continue | Rebuild the gate closed from durable `RETIRING`, fence the old runtime incarnation, and require bounded request deadlines plus placement-specific orphan drain/owned-process termination before physical removal. | Recovery invariant open |

## OCR Profile Consequences

KServe V2 remains the preferred transport candidate because it standardizes health,
metadata, typed inference, and binary tensors; it is not an OCR semantic standard
and supplies no standard cancellation endpoint. The leading product output is one
version-pinned PAGE document per input image. ALTO is not a required parallel output.

The current local spike remains valid evidence for binary framing and official-XSD
validation of its fixtures. It does not prove OCR-D conformance: its PAGE
`TextEquiv/@index=0` is XSD-valid but the proposed OCR-D-aligned product profile
uses preferred `index=1`. It also does not prove general PAGE/ALTO equivalence,
hostile-XML safety, real inference, ROCm execution, or hard cancellation.

## Review Gate

The architecture may advance to a concrete implementation Impact Handshake only
after the still-open items above have an owner and an executable proof shape:

- the single settings writer, domain command/revision semantics, notification, and
  supported-OS process fencing described in
  [settings authority](evidence/settings-authority.md);
- the generation-specific provider identity, private admission-gate proof,
  monotonic blocked-retirement sequence, controller-crash orphan-drain policy, and
  LLM durable-reference policy;
- placement-appropriate deployment owner/incarnation fencing;
- the installation repository, immutable placement rule, manifest/realization
  ownership split, and exact status derivation;
- OCR PAGE hierarchy/coordinate/resource/failure profile;
- a real Radeon/ROCm OCR, LLM, and Embedding runtime cell;
- Local Radeon and Private SSH placement-specific acceptance described in
  [execution placement options](evidence/execution-placement-options.md).

No rollback, compensation journal, aggregate selection transaction, cross-domain
removal reservation, custom gateway, or cross-domain cancellation mechanism should
be reintroduced merely to close these items.

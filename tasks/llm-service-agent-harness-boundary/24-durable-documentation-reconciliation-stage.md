# Durable Documentation Reconciliation Stage

## Status and Authority

Sir opened and authorized this documentation-only Execute stage on 2026-07-15.
It promotes already accepted, implemented LLM Conversation / Agent Harness
boundary facts into their durable owners. It does not authorize source, schema,
runtime, or product-behavior changes.

Implementation is complete and awaits Sir's review. No commit is authorized by
this stage itself.

## Objective

Give maintainers one concise, durable answer to two different questions:

1. **What is the cross-unit authority and dependency topology?**
2. **What is the required UI -> Harness -> LLMConversationService sequence for
   submission, sampling, finalization, reopening, and Chatbot projection?**

The documentation must make an invalid reverse dependency or a recreated
Turn/Run/ConversationStore visibly wrong before a reader reaches source.

## Guardrails

- Keep one canonical statement per durable claim: topology and cross-unit
  sequences belong to Product TDD; local implementation seams belong to Unit
  TDD; decision rationale belongs to the ADR; PRD remains product-level.
- Describe only accepted, implemented behavior. Do not promote an unresolved
  discrepancy into a new product promise by changing prose alone.
- Preserve the existing source/test authority for mechanical fields, exact
  algorithms, limits, and payload shapes.
- This is documentation-only work. Do not change source, schema, runtime
  behavior, or release configuration.

## Current Truth

The completed refactor made `LLMConversationService` the sole canonical
Thread/Message writer and moved provider/tool protocol, registry, validation,
and invocation to the LLM boundary. Harness now owns only live coordination,
source import, sampling/cancellation policy, and snapshot-to-Chatbot-event
projection.

However, `docs/20-product-tdd/README.md` still assigned conversation and
provider/tool orchestration to Harness, while `docs/30-unit-tdd/README.md`
still described persisted Run/Turn convergence, connected completion-guard and
step-budget behavior, and a pre-cutover verification route. The current task
packet held the accurate architecture but is not a durable owner.

This stage has now added the Product TDD boundary contract and ADR, reconciled
the Product TDD/Unit TDD/top-level owner routes and Agent-local guidance, and
made narrow PRD/observability wording corrections. The Product TDD contract is
the only owner of the new dependency topology and cross-unit sequences; Unit
TDD records local seams rather than restating that authority.

## Settled Documentation Topology

```text
Chatbot UI -> Agent Harness -> LLMConversationService -> provider adapter -> LLM
                    |                    |
                    v                    v
              DatasetService       canonical SQLite + LLM-owned Tool protocol
```

- Chatbot UI submits intent and renders Chatbot Events; it has no canonical
  writer or storage authority.
- Harness coordinates transient application work: source import, choosing when
  to sample/cancel, and projecting canonical snapshots. It neither writes
  canonical conversation state nor dispatches a Tool.
- `LLMConversationService` owns Thread/Message state, pending/final message
  lifecycle, provider history serialization, and the `AgentTool` protocol,
  registry, scope validation, and invocation.
- Concrete Tool implementations depend on the LLM-owned Tool interface and
  are registered by composition; the LLM boundary does not import Harness or
  domain/concrete Tool modules.
- DatasetService owns materialization and original-source provenance. Harness
  may ask it for a read-only source presentation only after loading a canonical
  snapshot; that presentation is not LLM conversation state.
- Thinking, activity, connection, and usage presentation are Chatbot Events.
  Observability remains non-authoritative and cannot restore/replay state.

## Planned Durable Owners

| Owner | Change |
| --- | --- |
| `docs/20-product-tdd/llm-conversation-boundary.md` | New canonical cross-unit topology, two sequence diagrams, authority rules, and source/test routes. |
| `docs/20-product-tdd/adr/0008-canonical-llm-conversation-boundary.md` | Concise decision rationale and rejected persistent Turn/Run/ledger alternatives; links to the contract instead of duplicating it. |
| `docs/20-product-tdd/README.md` | Correct topology summary and route to the new contract. |
| `docs/30-unit-tdd/README.md` | Replace stale Harness-only Run/Turn model with the local lifecycle and projection invariants; link back to Product TDD. |
| `src/xenix/services/agent/AGENTS.md` | Synchronize active maintainer tripwires and verification route with the durable contract. |
| `docs/10-prd/README.md` | Remove accidental technical implication that a persisted Turn exists, without adding architecture detail. |
| `docs/40-deployment/observability.md` | State the already-implemented token-usage metric export boundary. |
| `docs/README.md` | Keep the top-level owner route aligned with the renamed Unit TDD. |

## Explicitly Excluded Decision Gates

This stage must not hide unresolved implementation/product questions by
rewriting a contract around them:

1. Whether a final Message's DatasetBlock reference must prevent Dataset
   disposal is unresolved. The current storage contract is stronger than the
   current disposal lookup; retain the mismatch as a follow-up decision.
2. Completion guard and step-budget pause/resume are not active current
   lifecycle behavior. Remove stale durable claims, but do not restore or
   formally retire the product features in this documentation slice.
3. The Artifact-link rule about prebuilt `artifact://` values conflicts with an
   existing tool result path. It requires a separately scoped contract/code
   decision; this stage does not silently choose one.
4. External OSS bucket-policy assertions are deployment acceptance work, not a
   consequence of this conversation-boundary change.
5. `model.task.query` currently exposes Artifact absolute paths and optional
   logs in a ToolResult despite the existing Agent-local no-raw-path guidance.
   This is an existing payload-contract debt; do not weaken the guide or alter
   Tool code in this documentation-only stage.

## Verification

- The new Product TDD contract contains one dependency diagram and two
  complementary sequence diagrams: live submission/sampling and history
  reopening/source enrichment.
- Product TDD, Unit TDD, and the Agent-local guide agree that only
  `LLMConversationService` writes canonical conversation state and invokes
  registered Tools.
- No durable claim says persisted Turn/Run/ConversationStore, connected
  completion guard, or connected step-budget pause/resume is current behavior.
- PRD remains product-level; it does not duplicate implementation topology.
- Deployment documentation preserves the observability firewall and states any
  token-count export boundary.

## Verification Record

- Two independent read-only reviews checked topology/lifecycle accuracy and
  durable-owner placement. Their tool-only-response, source-presentation,
  deletion-scope, Unit-TDD duplication, owner-index, verification-route, and
  control-surface findings were incorporated.
- All changed Markdown relative links resolve. A dedicated trailing-whitespace
  scan, including new untracked files, and `git diff --check` pass.
- The review verified the diagrammed authority and sequences against the LLM
  conversation, Harness, DatasetService, Chatbot projection, repository, and
  focused test sources. No product/runtime code was changed.
- Markdown links resolve, `git diff --check` passes, and a read-only topology
  review finds no reverse dependency or duplicated authority claim.

## Next Step

Sir reviews the durable documentation update. The unresolved decision gates and
the recorded ToolResult local-path debt remain follow-up work; no commit is
authorized by this stage itself.

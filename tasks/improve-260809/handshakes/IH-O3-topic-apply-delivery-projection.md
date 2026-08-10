# Impact Handshake O3 — Topic Apply Delivery Projection

**Status:** Consumed for an evidence-triggered experiment on 2026-08-10; the experiment was implemented and offline-verified, then rejected and rolled back after bounded paid evidence. No O3 product code remains, and the paid topic outcome is not closed.

## Evidence Trigger

Bounded paid summaries show that run `1143200b493149cf8c3aff77f52963a7` failed only `group_template_isolation`, while run `8ada4c4dd50349f0aeccdbdef9e06484` failed `group_template_isolation` and `exploratory_offline_boundary`. Both summaries report all three pre-final grounding families available, and `model.apply` was the last successful Tool. O2 Skill guidance alone therefore did not reliably carry already-authoritative evaluation evidence across the final Apply-to-answer boundary.

## Paid Decision and Current State

The valid O3 run `25d00f7f27d649eaa8407e7828ec9de2` again omitted `quality_metrics`, `group_template_isolation`, and `exploratory_offline_boundary` even though all three families were available before finalization. A second attempt ended in `runtime_error` and supplied no semantic evidence. The adjacent Apply projection therefore did not ensure final Provider synthesis and showed no bounded improvement. The experimental source and test changes were rolled back; this handshake remains only as a record of the rejected hypothesis.

## Address and Object

- `src/xenix/services/agent/tools.py`: completed topic `model.apply` provider projection, both direct completion and later `model.task.query` convergence;
- `tests/test_agent_ml_text_discovery_projection.py`: ordinary Agent-boundary projection assertions;
- O3 handshake, implementation, execution, and index records in this task packet.

No benchmark case, Skill, ML service/domain DTO, storage schema, finalizer, completion guard, sanitizer, provider, or other model-family result is in scope.

## State Diff

- **Experimental From:** completed topic Apply returned assignment facts and its own public output, while the final Provider recovered quality, stability, connected/template isolation, limitations, and the evaluation Artifact from an earlier Tool result.
- **Experimental To:** completed topic Apply additionally projected a bounded `text_topic_delivery` view containing the authoritative evaluation values, aggregate isolation facts, limitations, public evaluation Artifact URI, and a concise conditional delivery checklist.
- **Authority gate tested:** resolution used only `trained_model.metadata.evaluation_ml_task_id` with `evaluation_facts_authority=ml_task_result` and required a succeeded, identity-consistent typed Evaluate result plus its public report.
- **Final state:** `To -> From`; no `text_topic_delivery` projection remains because the paid result did not improve final synthesis.

## Blast Radius

During the experiment, only completed multilingual topic Apply payloads gained `text_topic_delivery` in direct and task-query projections. After rollback, all product and test surfaces retain their pre-O3 shapes.

## Invariants

- `EvaluateTaskResult` remains the only evaluation-fact authority; metadata remains a reference, not a copy.
- Apply facts cannot certify quality or isolation and are never used as a fallback.
- The projection includes no raw row, document/group value, vocabulary/profile, private identifier, digest, or local path.
- The sole identifier-like value added is the required public `artifact://` evaluation reference.
- Missing, stale, invalid, cross-model, or label-inconsistent evidence fails closed as unavailable without failing an otherwise successful Apply.
- No Tool ordering, final-answer rewriting, transcript inspection, extra Provider call, or case-specific branch is introduced.

## Verification

1. The experimental focused test covered authority, identity, Artifact linkage, bounds/privacy, negative references, and non-topic isolation before the paid run.
2. Bounded paid evidence tested the hypothesis without retaining raw content.
3. Rollback proof requires both source/test files to match `HEAD`, the original focused projection test, `pdm run check`, task-link validation, and `git diff --check`.

## Return to Discussion

Return before changing domain contracts or persisted metadata, weakening identity/privacy gates, adding a finalizer/sanitizer, or modifying benchmark semantics.

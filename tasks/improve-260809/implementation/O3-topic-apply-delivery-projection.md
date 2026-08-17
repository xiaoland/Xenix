# O3 Implementation Plan — Topic Apply Delivery Projection

**Status:** Experiment implemented and offline-verified on 2026-08-10, then rejected and rolled back after paid evidence showed no improvement. No O3 product/test diff remains; paid topic closure is still open.

## Outcome

Test whether re-surfacing exact authoritative topic facts beside completed Apply reliably closes the final-delivery gap without copying evaluation authority or exposing private content.

## Working Set

- [IH-O3](../handshakes/IH-O3-topic-apply-delivery-projection.md);
- `src/xenix/services/agent/tools.py`;
- `tests/test_agent_ml_text_discovery_projection.py`;
- O1/O2 bounded task records and the two bounded paid summaries named by IH-O3.

Benchmark cases, Skills, ML service/domain DTOs, storage, finalization, completion guards, sanitizers, Providers, and unrelated result projections are excluded.

## Coherent Passes

1. Detect a typed topic Apply result on direct completion and task-query convergence without changing other Apply payloads.
2. Resolve the trained model's sole evaluation-task reference and validate authority, task status/type, typed result identity, topic-label identity, and the linked public evaluation report.
3. Project only exact quality/stability values, aggregate connected/template isolation, bounded limitations, the evaluation Artifact URI, and a conditional delivery checklist; otherwise return one bounded unavailable shape.
4. Protect the boundary with ordinary black-box assertions, then run focused projection regression, repository checks, and diff validation.
5. If bounded paid evidence shows no improvement, reject the hypothesis and restore the pre-O3 product/test state while retaining this decision record.

## Verification

- The experimental focused topic projection passed before paid execution, including missing and tampered evaluation references.
- One valid paid run showed no improvement; one retry was a runtime error with no semantic evidence.
- Post-rollback source/test identity, the original focused test, repository checks, and final diff/link checks are recorded in the [O3 execution record](../execution/O3-topic-apply-delivery-projection-2026-08-10.md).

## Current Truth

- The adjacent projection was technically bounded and authority-correct but did not ensure final Provider synthesis.
- The sole valid paid O3 run reproduced all three final-grounding gaps with all three pre-final evidence families available.
- O3 is a rejected hypothesis, not retained product behavior; `tools.py` and its ordinary discovery projection test match their pre-O3 `HEAD` state.
- The paid topic outcome remains open.

## Next Step

Return to diagnosis before another product mutation. Any different final-synthesis owner or broader control surface requires a new exact handshake; do not reinstate the adjacent projection without new evidence.

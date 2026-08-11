# O4 Implementation Plan — Cleaning Causal Diagnosis

**Status:** Completed on 2026-08-11. Diagnosis and the next ablation matrix are ready; no product mutation was made.

The A1 oracle was subsequently audited, corrected, implemented, and verified in [O4-A1 cleaning service correctness](O4-A1-cleaning-service-correctness.md).

## Outcome

Explain why the cleaning Agent used multiple queries/transforms and derived Datasets by joining real Provider turns with SQLite messages, Tool results, service behavior, Dataset lineage, and token timing. Preserve uncertainty about the deleted historical runtime.

## Working Set

- [IH-O4](../handshakes/IH-O4-cleaning-causal-diagnosis.md);
- historical report `d4fc5a8482a94c81a1909b1760345b24`;
- ignored `execution/raw/o4-cleaning-causal-diagnosis/` retained runtimes;
- cleaning case, preprocessing Skill, Tool input/projection, cleaning/transform service, and existing Foundation service test;
- [O4 execution record](../execution/O4-cleaning-causal-diagnosis-2026-08-11.md).

## Coherent Passes

1. Recover every fact the historical bounded report can prove and list what normal TemporaryDirectory cleanup deleted.
2. Run one same-case/same-model retained diagnostic and inspect the raw runtime rather than relying on report counts.
3. Remove the diagnostic's cross-drive TEMP confounder and run a second retained diagnostic to completion.
4. Recompute each suspected service failure from canonical registered data and source control.
5. Classify causes by service, Tool schema/projection, Skill routing, Agent reasoning, and observability.
6. Define sequential ablations that change one owner at a time and retain outcome correctness as the first gate.

## Stop Conditions

Stop before source/test mutation, before weakening the case oracle, and whenever a conclusion would require inventing the original deleted Tool order. Provider retries or unrelated model comparisons are out of scope.

## Acceptance

The diagnosis is complete when it contains:

- one exact successful retained sequence and one exact failure sequence;
- the first divergence and raw evidence for each;
- deterministic reproduction of any service defect;
- historical fact versus cross-run inference labels;
- per-round cost accumulation;
- a service-first ablation matrix with objective pass/fail criteria.

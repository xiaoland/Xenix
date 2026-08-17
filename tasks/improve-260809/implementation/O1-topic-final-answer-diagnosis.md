# O1 Implementation Plan — Topic Final-Answer Diagnosis

**Status:** Completed on 2026-08-10: evaluator defect fixed and the final-synthesis divergence classified with paid exact-selector evidence.

## Outcome

Locate the first divergence behind the completed topic run's Windows-path disclosure and missing grounding without guessing that the owner is the prompt, Skill, Tool projection, attachment context, finalizer, or evaluator.

## Working Set

- [IH-O1](../handshakes/IH-O1-topic-final-answer-diagnosis.md);
- the bounded RT-T2 run summary and one ignored live runtime/report;
- topic benchmark evaluator and its nearest local instructions;
- attachment/public Artifact-link projection code only for read-only source tracing.

Do not load the supplied corpus, unrelated benchmark cases, broad logs, or product implementation files until a bounded provenance category names them.

## Coherent Passes

1. Trace all legitimate path-bearing inputs statically: source attachment identity, app-owned Dataset path, public `artifact://` URI, artifact renderer, and final answer text.
2. Add only the evaluator-side bounded classification approved by `IH-O1`; never serialize the matched value.
3. Re-run offline Harness checks and exact collection.
4. Run one paid exact-selector diagnostic and classify the first divergence.
5. Return to design with one proposed `IH-O2` for the exact owner, or close O1 as evaluator-only if no product defect exists.

## Stop Conditions

Stop if diagnosis requires retaining a transcript/path, changing the topic prompt or oracle, adding a generic response sanitizer, prescribing Tool order, or touching product behavior. Those are product/evaluator decisions, not diagnostic implementation details.

## Acceptance

O1 is complete when a privacy-safe category distinguishes the origin of the path and confirms whether the missing grounding facts were available to the Agent before finalization. A semantically passing Agent run is not an O1 acceptance requirement; that belongs to the later exact optimization.

## Current Truth — 2026-08-10

- The old `windows_path` category was produced at least by a public `artifact://` URI because the detector accepted the URI's scheme suffix as a drive prefix. The bounded report cannot establish whether another real Windows path coexisted. The evaluator now distinguishes real path syntax and classifies only bounded provenance.
- All three omitted grounding families were available before finalization through the authoritative Evaluate Tool result plus the user request. Their first divergence is final Provider synthesis, not missing public evidence.
- Offline Harness checks pass and the exact case collects once in both modes. Paid run `81f8c49b3f1d4cbb882bcac7115f2a89` passed privacy after the detector fix and confirmed that the remaining missing facts diverged only during final Provider synthesis.
- [Execution record](../execution/O1-topic-final-answer-diagnosis-2026-08-10.md) owns the bounded evidence and proposed O2 state diff.

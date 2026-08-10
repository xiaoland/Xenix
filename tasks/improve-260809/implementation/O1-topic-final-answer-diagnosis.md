# O1 Implementation Plan — Topic Final-Answer Diagnosis

**Status:** Proposed; requires approval of `IH-O1`.

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

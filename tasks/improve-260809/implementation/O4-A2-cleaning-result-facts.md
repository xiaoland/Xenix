# O4-A2 Implementation Plan — Bounded Cleaning Result Facts

**Status:** Completed and objectively verified on 2026-08-11.

**Execution:** [O4-A2 bounded cleaning result facts](../execution/O4-A2-cleaning-result-facts-2026-08-11.md).

**Handshake:** [IH-O4-A2](../handshakes/IH-O4-A2-cleaning-result-facts.md).

## Outcome

Give the Agent enough authoritative feedback to understand what one atomic cleaning call actually did without putting the cleaned Dataset into its context window.

## Contract

The complete result stays behind the public Dataset and Artifact IDs. The Provider projection contains only:

- whole-Dataset scope and holdout-safety warning;
- source/result Dataset and Artifact identities;
- row counts and aggregate removal count;
- bounded, ordered operation effects, including one bounded resolved fill scalar when applicable;
- bounded validation effects and bounded warnings;
- an explicit note that preview rows are omitted and `dataset_id` is the follow-up authority.

## Coherent Passes

1. Add a JSON-safe resolved-fill scalar to the service report and lock it with order-sensitive service tests.
2. Carry the scalar through the existing compact-report bounds.
3. Replace `data.clean` XTT preview rendering with a compact metadata-only rendering.
4. Extend the public Tool integration test to prove positive facts and negative row/path/schema disclosure.
5. Run focused and full verification, then record exact evidence and remaining O4-A3 work.

## Stop Conditions

Stop if the implementation needs raw rows, arbitrary value lists, a second result authority, a change to cleaning semantics, or a case-specific Agent prompt. Broader textbook ch07 operations and Tool/Skill authority changes remain separate slices.

## Acceptance

O4-A2 is complete only when the full cleaned data is reachable through the public Dataset/Artifact but absent from the Provider Tool result, while the bounded result is sufficient to explain operation order, validation effects, and learned fill values.

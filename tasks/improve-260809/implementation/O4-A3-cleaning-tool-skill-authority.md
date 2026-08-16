# O4-A3 Implementation Plan — Cleaning Tool and Skill Authority

**Status:** Completed and paid-characterized on 2026-08-11; implementation gates passed, while the no-broad-query target missed.

**Handshake:** [IH-O4-A3](../handshakes/IH-O4-A3-cleaning-tool-skill-authority.md).

## Outcome

Make the shortest correct cleaning route obvious to the Agent without hiding Tool capability or prescribing a benchmark-specific trace.

## Coherent Passes

1. Project strict left-to-right/current-frame semantics through the typed Provider schema.
2. Align `data.clean` and `data.transform` descriptions around atomic-operation ownership versus unsupported SQL predicates.
3. Update the canonical preprocessing Skill and its optional Tool reference; add lowercase and non-negative direct recipes.
4. Generate the Skill catalog and add provider-free contract tests that read the real schema/catalog.
5. Run focused, full, check, and smoke verification.
6. Reuse a task-local retained-runtime runner for three exact paid cells; query SQLite, usage journals, and Dataset lineage before summarizing the outcome.

## Stop Conditions

Stop if implementation requires changing cleaning execution, hiding `data.transform`, modifying the benchmark prompt/oracle, adding case-specific language, or accepting a wrong Dataset for fewer calls. Stop paid repetitions on an infrastructure/integrity failure until its cause is classified.

## Acceptance

The implementation portion is complete when the schema/Skill authority is mechanically verified. The O4-A3 outcome claim is complete only after three valid paid cells are causally inspected; efficiency is never promoted without semantic and integrity correctness.

## Execution

See [O4-A3 implementation and paid characterization](../execution/O4-A3-cleaning-tool-skill-authority-2026-08-11.md). Three valid cells were inspected through SQLite, usage journals, Dataset lineage, and exact result files; two network failures were excluded from Agent evidence.

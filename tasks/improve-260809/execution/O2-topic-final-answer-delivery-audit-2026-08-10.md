# O2 Topic Final-Answer Delivery Audit — 2026-08-10

**Status:** Post-change characterization complete; final-grounding outcome not reliably closed.

## Authority and Trigger

Sir's blanket execution authorization consumed [IH-O2](../handshakes/IH-O2-topic-final-answer-delivery-audit.md). Paid O1 run `81f8c49b3f1d4cbb882bcac7115f2a89` passed privacy and showed all diagnosed grounding facts available before finalization, but its final answer omitted topic delivery, isolation, permutation, and exploratory/offline limits.

## Implemented Diff

- Modeling Skill version is `0.10.0`.
- Its final-answer standard now owns one multilingual topic pre-finalization audit.
- The audit reconciles the user request against authoritative Evaluate and completed FIT/APPLY results before answering.
- It requires the realized topic count, permutation boundary, reported quality/stability values, connected/template zero overlap, requested public Dataset/Artifact references, exploratory/offline decision limits, and an external validation step.
- It permits only public Dataset IDs and `artifact://` Artifact links, excludes local paths and raw/private content, and says unavailable when public evidence is absent.

No Tool schema/result, ML service, orchestration, completion guard, sanitizer, fixture, semantic oracle, rubric, or report policy changed. The generated catalog remains a derived ignored surface.

## First Paid Post-change Attempt

Run `75ad6132b189420bb0175bea0f6dc00e` ended as `measurement_error`, not as Agent evidence or acceptance. The seven-round run stayed within its 102,539-token reported budget, but assessment construction raised `ValueError`: the 581-character business prompt exceeded `JudgeInput.task_intent`'s 512-character contract. Reaching JudgeInput construction implies the deterministic checks passed, but semantic assessment was not evaluated and the judge remained blocked, so the measurement remains invalid.

## Benchmark Contract Repair

- Compressed the business prompt from 581 to 505 characters while retaining every semantic/oracle requirement.
- Added an import-time fail-closed assertion against the 512-character `JudgeInput.task_intent` maximum and directly validated construction of `JudgeInput` with the prompt.
- Kept the fixture, Tool trajectory, expected counts, privacy constraints, semantic oracle, and rubric unchanged.

## Subsequent Paid Results

- Run `1143200b493149cf8c3aff77f52963a7` completed with integrity true and budget within limits in 10 rounds, reporting 147,405 subject tokens over 279.494 seconds. All deterministic checks other than `group_template_isolation` passed, and every pre-final grounding family was available. The sole semantic failure was `group_template_isolation`, so this is valid post-change evidence but not acceptance.
- The sole v3 report, run `036ad42d99144b84948dba4b61088c08`, ended as `runtime_error` on its first round with usage unreported. Semantic assessment was not evaluated; it contributes no Agent evidence.
- Run `8ada4c4dd50349f0aeccdbdef9e06484` completed with integrity true and budget within limits in 6 rounds, reporting 84,050 subject tokens over 124.590 seconds. Every deterministic check except final grounding passed, all pre-final grounding families were available, and the only semantic gaps were `group_template_isolation` and `exploratory_offline_boundary`. This is valid post-change evidence but not acceptance.

## Offline Verification

| Gate | Result |
| --- | --- |
| Skill catalog generate/check | passed; three Skills |
| Focused Skill scope | 3 passed |
| `pdm run check` | passed |
| Direct `JudgeInput` boundary validation | passed; 505 characters, 7 characters headroom |
| Agent Harness offline | 33 passed |
| Exact topic headless collect-only | one item |
| Exact topic headed collect-only | one item |
| `git diff --check` | passed |

## Outcome

The two valid completed post-change runs retained one or two final-grounding failures despite all corresponding pre-final evidence being available. O2 is retained because it provides a coherent general delivery audit and improved some samples, but it is not formal acceptance. The subsequent O3 experiment tested and rejected an adjacent Apply projection, then restored the pre-O3 product state.

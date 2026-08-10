# O3 Topic Apply Delivery Projection — 2026-08-10

**Status:** Experiment implemented and offline-verified, then rejected and rolled back. One valid paid run showed no improvement; one retry was a runtime error. Paid topic closure remains open and no O3 product/test code is retained.

## Trigger

Bounded post-O2 runs `1143200b493149cf8c3aff77f52963a7` and `8ada4c4dd50349f0aeccdbdef9e06484` retained final-delivery failures despite all pre-final grounding families being available. In both, `model.apply` was the last successful Tool, making its topic-only provider projection the smallest evidenced boundary.

## Experimental Diff — Rolled Back

- Completed topic Apply now includes the same `text_topic_delivery` view in direct completion and later `model.task.query` convergence.
- Its available form contains exact topic count, perplexity, coherence, diversity, permutation-matched stability values, connected/template aggregate counts and zero-overlap counts, authoritative limitations, and the public evaluation Artifact URI.
- A conditional checklist asks for those exact values, isolation evidence, exploratory/offline/non-causal/no-automatic-decision limits, and requested public references.
- Evidence resolution follows only the trained model metadata's evaluation-task reference and accepts only a succeeded, typed, identity-consistent `EvaluateTaskResult` with its valid public evaluation report.
- Missing or tampered evidence returns the same bounded unavailable form and does not fail completed Apply.

No benchmark, Skill, ML service/domain DTO, persistence, finalizer, completion guard, sanitizer, or non-topic Apply shape changed.

## Bounded Paid Results

- Run `25d00f7f27d649eaa8407e7828ec9de2` completed with integrity true and budget within limits in 8 rounds, reporting 107,678 subject tokens over 209.093 seconds. All three pre-final grounding families were available, but the final answer still failed `quality_metrics`, `group_template_isolation`, and `exploratory_offline_boundary`. This valid run showed no improvement: placing the evidence beside Apply did not ensure final synthesis.
- Run `de3e87d473d14e33ac227bfdc7418bfd`, the sole v2 report, ended as `runtime_error` (`llm_provider_network_error`) in round 2 after 77.892 seconds. Subject usage was unreported; the invocation recorded 3,090 tokens. Semantic assessment was not evaluated, so the run contributes no Agent evidence.

## Decision and Rollback

The valid paid result rejects the O3 optimization hypothesis. The provider already had all required evidence, and another adjacent bounded projection did not cause it to synthesize that evidence into the final answer. Only the O3 changes in `src/xenix/services/agent/tools.py` and `tests/test_agent_ml_text_discovery_projection.py` were manually reversed. O1/O2/A2/M1 work and the O2 v4 bounded evidence remain intact.

## Offline Verification

| Gate | Result |
| --- | --- |
| Experimental focused projection | passed before paid execution; hypothesis was technically viable but behaviorally ineffective |
| Paid semantic result | failed with all three grounding gaps despite all three pre-final families being available |
| Rollback identity | passed; both O3 source/test targets have no diff against `HEAD` |
| Original focused projection test | passed; 1 test, 22 existing Joblib/NumPy warnings |
| `pdm run check` | passed; lint, typecheck, Skill generation/check, lock validation, and compilation succeeded |
| Task links and `git diff --check` | passed |

The pre-paid focused run emitted only existing Joblib/NumPy deprecation warnings. Raw Provider content is not retained here.

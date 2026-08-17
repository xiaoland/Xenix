# Foundation 1 Implementation Plan — Dataset Profile and Cleaning Evidence

**Status:** Implemented and objectively verified on 2026-08-09.
**Authorization owner:** [Impact Handshake F1 — Dataset profile and cleaning evidence](../handshakes/IH-F1.md).
**Execution record:** [Foundation execution — 2026-08-09](../execution/foundations-2026-08-09.md).

## Outcome

A registered Dataset can be profiled through one bounded, typed, read-only Tool call. The default provider-visible result contains structural and quality facts but no sample rows, category/group values, or identifier values. When business semantics remain materially ambiguous, the Agent may make one focused, bounded `data.query` call for the exact values needed to decide.

Business cleaning remains a whole-Dataset derivation workflow. It is clearly distinguished from learned preprocessing fitted inside a model split.

## Working Set

Load only:

- `src/xenix/services/analysis_profile.py`
- `src/xenix/services/dataset_service.py` and direct inspection/tabular helpers used by the profile boundary
- `src/xenix/services/agent/tool_inputs.py`
- `src/xenix/services/agent/tools.py`
- `src/xenix/services/agent/composition.py`
- `src/xenix/services/agent/tool_presentations.py`
- `src/xenix/services/agent/skills/xenix-data-analysis/SKILL.md`
- `src/xenix/services/agent/skills/xenix-data-preprocessing/SKILL.md`
- their generated Skill projection only if the repository check requires regeneration
- `tests/test_analysis_profile.py`
- `tests/test_ml_foundation_profile_cleaning.py`
- `tests/fixtures/ml_foundation/profile_cleaning_v1.csv`

Do not load or change ML split/evaluation code in this plan.

## Pass 1 — Freeze the Clean-Room Case

Create an independently designed, small service-ticket quality case with:

- an exact duplicate and a business-key duplicate;
- missing numeric and categorical values;
- one invalid range and one defensible outlier;
- a date field, low-cardinality category, identifier-like field, and binary outcome;
- a committed SHA-256 asserted by the test.

The expected facts and cleaning membership live only in the ordinary service test. No textbook row, field combination, sample output, or reference code is copied. The test first proves source bytes are unchanged.

## Pass 2 — Make Profile Facts Typed and Dataset-ID Driven

Refactor `ProfileDatasetInput`, `ProfileDatasetResult`, and `AnalysisProfileService.profile_dataset` so the public boundary resolves a registered `dataset_id` and returns typed, bounded facts. The contract includes:

- Dataset ID and `scope="whole_dataset"`;
- row/column counts and exact duplicate count;
- ordered field facts: index, name, logical type, missing count/rate, and cardinality;
- bounded numeric summaries and datetime ranges;
- a bounded correlation projection and explicit truncation metadata;
- no preview/sample rows and no category/group/identifier values.

This is not a new persistent Profile entity. It does not create a Dataset or Artifact by default. Any local Markdown is rendered from the typed facts and is not a second source of truth.

## Pass 3 — Restore the Atomic Agent Tool

Register the existing orphaned `analysis.profile` presentation as a concrete read-only Tool:

- input: registered `dataset_id` plus bounded numeric limits only;
- result: the typed safe projection above;
- no source path, raw row, or unbounded local metadata;
- no implicit `data.query` call and no derived output.

Update the data-analysis and preprocessing Skills to use this sequence:

1. call `analysis.profile` for low-sensitivity structural facts;
2. bind unambiguous structural roles without asking;
3. if business classification remains materially ambiguous, call one purpose-specific bounded `data.query` for only the relevant columns/values;
4. ask Sir only when multiple plausible interpretations would change leakage or evaluation meaning;
5. call explicit atomic `data.clean` operations and validate the derived Dataset.

The `data.clean` Tool description/result guidance labels its stateful imputing, encoding, and scaling operations as whole-Dataset business transformation, not holdout-safe model preparation.

## Pass 4 — Public-Boundary Qualification

`tests/test_analysis_profile.py` owns the typed profile contract, bounds, error handling, and default value non-disclosure.

`tests/test_ml_foundation_profile_cleaning.py` owns the service workflow:

```text
fixture hash
-> register source Dataset
-> profile
-> explicit clean
-> register derived Dataset/Artifact
-> profile derived Dataset
-> compare private expected facts
```

It asserts source SHA immutability, exact bounded facts, cleaning result membership/schema, derived lineage, and user-openable output identity. It never calls an Agent benchmark.

## Verification Order

1. `pdm run pytest --direct tests/test_analysis_profile.py tests/test_ml_foundation_profile_cleaning.py -q`
2. `pdm run test -q`
3. `pdm run check`
4. `pdm run smoke`
5. Only after steps 1–4 are green, independently run one bounded paid headless characterization of `benchmarks/agent_harness/test_ml_cleaning.py::test_ml_cleaning`.
6. Record the paid run in `execution/`; diagnose before changing a Skill, Tool, or orchestration seam beyond this approved state diff.

The paid run consumes no service fixture or report. Its ordering is development control only.

## Stop and Return to Design

Stop before source mutation or during execution if:

- a useful profile requires provider-visible sample/category/identifier values by default;
- the profile needs to become persistent or user-openable by default;
- cleaning correctness requires changing operation semantics rather than projection/guidance;
- the clean-room case cannot be made materially independent of the supplied corpus;
- a change outside the Impact Handshake is needed to pass acceptance.

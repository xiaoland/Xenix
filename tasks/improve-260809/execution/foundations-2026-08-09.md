# Foundation Execution — 2026-08-09

## Scope

This record closes the objective implementation/verification pass for:

- `IH-F1`: Dataset profile and cleaning evidence;
- `IH-F2`: group-safe preparation, evaluation, lifecycle facts, and bounded Agent projection.

The supplied textbook code/data remain ignored and private. Their exact ch06/ch07/ch09/ch10/ch11 adoption map, hash/license gate, isolated reference-run contract, and clean-room correspondence are recorded in the [on-demand material-adoption plan](../materials/on-demand-adoption.md); no supplied Joblib/Pickle was loaded.

## Implemented Contract

Foundation 1:

- Dataset-ID, typed, bounded, whole-Dataset `analysis.profile` Tool;
- default non-disclosure of sample/category/group/identifier values and local paths;
- profile-first progressive disclosure with a purpose-limited `data.query` only for material semantic ambiguity;
- explicit distinction between whole-Dataset `data.clean` and split-fitted model preparation;
- independent clean-room profile/cleaning fixture and black-box workflow.

Foundation 2:

- schema-v2 column bindings with immutable Dataset content/schema snapshot and explicit legacy rebind;
- optional supervised `group` role, deterministic `group_hash_holdout.v1`, zero-overlap facts, and group-aware tuning folds;
- train-only sklearn Pipeline preparation facts, same-holdout Dummy baseline, candidate/baseline prediction digests, and typed comparison;
- authoritative Evaluate-task result/report plus direct trained-model reference;
- evaluation-model train-split scope versus apply-model all-eligible-row scope;
- Dataset/Artifact apply-source identity and true derived Dataset lineage;
- bounded Agent task/model projection without paths, previews, raw worker payloads, or full metadata.

## Ordinary Verification

| Command / selector | Result |
| --- | --- |
| F1 focused profile/cleaning | 5 passed |
| F2 registry + lifecycle during core integration | 10 passed |
| Combined F2 registry/execution/Agent projection/migration/storage selector | 19 passed; only Joblib/NumPy deprecation warnings |
| `pdm run test -q` | 60 passed; 48 existing Joblib/NumPy deprecation warnings |
| `pdm run check` | passed, including Skill catalog, lint, typecheck, OCR lock, and compile checks |
| isolated `pdm run smoke` | exit 0; about 82 seconds |
| `pdm run package` | exit 0; about 813 seconds |

No ordinary test imports, invokes, or reads Agent benchmark code/results.

## Proof-Portfolio Architecture Review

The suite crossed the existing 50-case review trigger from the 45-test baseline and now collects 60 ordinary cases. The expansion is accepted for this slice because:

- profile contract tests, clean-room cleaning workflow, ML registry contract, full lifecycle execution, bounded Agent Tool projection, and storage migration each own a distinct public boundary or durable invariant;
- the service/Tool cases do not import benchmark fixtures, runners, evaluators, or reports;
- the grouped lifecycle and Agent Tool projection deliberately reuse the same logical business risk through independently constructed test flows because they prove different authorities;
- no cases were merged or hidden behind parameterization to game the threshold;
- the complete suite remains about 19 seconds on this workstation, so the added proof has not created a material default-CI runtime problem.

The main maintenance cost is repeated local logistic-regression fit/evaluate/apply execution and its Joblib/NumPy deprecation warnings. That warning is tracked as dependency noise, not a reason to weaken lifecycle coverage.

## Packaged-Smoke Exception

Official `pdm run smoke-package` failed before launching the packaged app because `dist/knowledge-ocr/runtime_catalog.json` selected the locked native OCR bundle while `build/knowledge-ocr/downloads/golden_image.png` was absent. The stable failure was `Native OCR packaged smoke requires the locked golden image.`

A direct packaged `xenix.exe --smoke-test` diagnostic, without pretending to activate missing OCR material, wrote a complete marker for Docling IR, PDFium, pikepdf, Zstd, spawned DOCX/PPTX imports, document removal/re-import, and LanceDB. OCR activation/retrieval were false as expected. Its PyInstaller parent process remained alive after the child completed and was terminated. Therefore:

- package construction passed;
- non-OCR packaged behavior produced positive diagnostic evidence;
- the official packaged-smoke gate did **not** pass and is not waived or replaced.

## Paid Cleaning Characterization

The first attempt selected exactly one case but stopped at round 0 with `missing_llm_settings`; no provider attempt or token usage occurred. The persisted invalid-setup run id was `f3803603993f4f868bf57d8653d3154e`.

The same exact selector was rerun with the ignored development LLM settings passed explicitly. Privacy-bounded report identity:

- case: `ml.cleaning_service_tickets`;
- run id: `d4fc5a8482a94c81a1909b1760345b24`;
- model: `kimi/kimi-k2.6`;
- mode/variant: headless / baseline;
- verdict: completed, semantic pass, integrity pass, budget within limits;
- 8 sampling rounds/provider attempts, 0 retries;
- 65,825 input, 4,038 output, 43,008 cached-input, 69,863 total reported tokens;
- 102.266 subject-turn seconds;
- exact cleaned Dataset, public Artifact link, grounded final answer, source immutability, and isolated state all passed.

Observed Tool counts were one Skill activation, one `analysis.profile`, two `data.query`, one `data.transform`, one `data.clean.metadata`, and one `data.clean`. The run produced two derived Datasets. This proves the workflow outcome for one paid sample, not formal multi-repetition acceptance.

## Diagnostic Consequence

The characterization is semantically successful but not yet orchestration-minimal. Two focused queries plus an extra transform consumed eight rounds and created a second derived Dataset. No transcript or unbounded trace is retained, so the exact cause is not established. A future `IH-O<n>` may investigate this with purpose-built bounded trace evidence; this observation alone does not authorize Tool-schema, Skill, or orchestration mutation.

# V2 Verification Plan

Status: **completed on 2026-07-20**.

## Offline Contract Proof

- Judge settings are required explicitly and never silently inherited from the
  subject configuration.
- A subject cell completes before judge dispatch; subject measurements do not
  include judge time, usage, or retries.
- Judge request has no Tools and uses only bounded case evidence.
- Strict JSON accepts only the versioned verdict, score, and reason-code shape;
  prose, missing fields, unknown enums, and oversized values are invalid
  responses.
- `pass`, `partial`, `fail`, `inconclusive`, missing terminal outcome,
  integrity breach, judge unavailable, provider failure, and invalid judge
  response stay distinguishable in serialized JSON.
- Reports contain no key, endpoint, path, Artifact/Dataset/Thread identity,
  raw source data, raw SVG, raw judge request/response, or exception text.

Recorded: focused benchmark suite passed **29** tests; the final full run passed
**383** core tests and **58** UI tests; `pdm run check` and `git diff --check`
passed. The full run emitted only existing sklearn convergence/deprecation
warnings.

## Calibration Proof

Use the four hand-labelled semantic-evidence fixtures in
[judge-contract.md](judge-contract.md). The deterministic suite proves their
safe construction and intended labels, not an LLM outcome. An explicit live
calibration records the configured judge's actual verdicts; disagreement is
evidence for rubric refinement, not a hidden test rewrite.

Recorded against Kimi K2.6 after the explicit verdict policy was added:

- `correct_comparison` → `pass`.
- `inverted_comparison` → `fail` on a clean retry; an earlier attempt returned
  `provider_error`, which remained isolated as judge state.
- `unrelated_visual` → `fail`.
- `insufficient_evidence` → `inconclusive`.

The transient provider error means these calibration results are acceptance
evidence, not a deterministic regression gate or a model leaderboard.

## Live Acceptance

1. Supply external subject and judge settings, with Kimi K2.6 selected
   explicitly for each role.
2. Run the regional-sales graph case through the normal benchmark CLI.
3. Confirm one report has: completed subject execution, valid integrity,
   separate judge status/verdict, subject metrics, judge metrics, and no raw
   evidence.
4. Intentionally provide unusable judge settings once; confirm the subject
   metrics still persist and the result records only a judge setup/error state.
5. Run `pdm run test` and `pdm run check` after source changes.

Recorded final Kimi K2.6 graph cell:

- Subject: `completed`, integrity valid, semantic `pass`; **16,682** subject
  tokens and **28.7 s** turn time.
- Judge: `completed`, `same_model`, all three scores `2`; **2,072** judge
  tokens and **36.7 s** elapsed time, recorded separately.
- The persisted bounded report passed a deny-list scan for raw SVG/Artifact
  URI/file URI/provider configuration fields.
- A second real cell with a missing judge settings path still completed the
  subject with **16,219** tokens; it recorded `judge=invalid_setup` and
  `semantic=not_evaluated`, with no judge token usage.

## Decision Gates

- If the judge disagrees with clear calibration cases, revise the rubric/evidence
  contract before adding score thresholds or new cases.
- If same-model judging materially distorts comparison, configure a fixed
  independent judge before reporting cross-model rankings.
- If semantic evidence cannot support a product category, decide whether to add
  a safe structured projection or defer that case; do not fall back to Tool
  trajectory assertions.

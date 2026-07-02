## Objective & Hypothesis

- Objective: improve word cloud generation reliability and visual defaults by tightening the `xenix-data-analysis` skill guidance and hardening `analysis.graph` tool schema, validation, error response, and tolerance behavior.
- Hypothesis: repeated failures and poor-looking word clouds come from an underspecified upstream contract, lax or unhelpful tool validation, and missing chart-type-specific defaults/fallbacks for Vega word cloud specs.

## Guardrails Touched

- `AGENTS.md` root operating model and impact handshake
- `docs/00-meta/mode-a-explore.md`
- `docs/00-meta/implementation-taste.md`
- `src/xenix/services/AGENTS.md`

## Verification

- Confirm current `analysis.graph` schema, runtime validation, and error surfaces for word clouds.
- Confirm current `xenix-data-analysis` skill instructions and references that shape chart requests.
- Bound blast radius before code changes.
- Baseline tests before implementation:
  - `pdm run pytest tests/test_analysis_graph.py -q` -> 13 passed
  - `pdm run pytest tests/test_agent_harness_first_slice.py -q -k "test_agent_harness_model_metadata_exposes_contract_without_train_enums"` -> 1 passed
  - `pdm run pytest tests/test_analysis_graph.py -q -k "tool_schema_is_dataset_scoped"` -> 1 passed

## Current Understanding

- The request spans both prompt/skill behavior and service/tool behavior.
- Desired word cloud constraints are already concrete enough to map into upstream guidance plus runtime defaults/validation.
- Current upstream guidance is too weak:
  - `xenix-data-analysis/SKILL.md` only says to use `analysis.graph` and read the Vega reference when needed.
  - `references/visualization-vega.md` still normalizes the dataset shape as `word` + `frequency`, allows 80-150 words, does not warn against Chinese `countpattern`, does not require tooltip, and only says to pair with Top-N bars when precise comparison matters.
  - `assets/vega/wordcloud.vg.json` currently colors by `word` domain, which produces per-word random-like coloring with weak semantics, and it has no tooltip channel.
- Current `analysis.graph` provider-facing schema is shallow:
  - it exposes only generic Vega fields and one sentence about word clouds;
  - it does not describe word-cloud-specific expectations such as preferred columns, bounded top-N, tooltip, or rotation constraints.
- Current `AnalysisGraphService` word-cloud validation is necessary but incomplete:
  - it checks text mark, grouped encode, `transform.text`, `transform.fontSize`, and bounded `fontSizeRange`;
  - it does not validate or normalize likely synonyms such as `count` vs `frequency`;
  - it does not enforce or repair visual defaults for rotation, tooltip, palette, or term-count bounds;
  - failures surface as plain string `ValidationError` messages with one long generic repair hint.
- Current failure response path is weak for iterative agent correction:
  - the harness converts exceptions into `payload.error = str(exc)` and `error_summary = str(exc)`;
  - there is no structured machine-readable repair guidance for the model.
- Compatibility pressure exists:
  - tests and `src/xenix/app.py` smoke coverage still use a `term/count/angle/weight` word-cloud shape;
  - a hard switch to only `word/count` or `word/frequency` would likely break existing smoke/tests unless compatibility or migration is added.
- Implemented shape:
  - skill/reference/template now steer the Agent to upstream `word` + `count`, Top 20-80, Chinese no-`countpattern`, tooltip, restrained color, mostly horizontal rotation, and paired Top 10 exact view when needed;
  - `analysis.graph` schema descriptions now surface the word-cloud contract directly to the provider;
  - `AnalysisGraphService` now normalizes word-cloud specs and data more aggressively: canonicalizes grouped encoding, applies bounded defaults, keeps legacy aliases (`term`, `frequency`) working, trims long clouds to Top 80, normalizes rotation to mostly horizontal placement, injects restrained rank-tier color defaults, and returns structured retry metadata on word-cloud failures;
  - Harness tool error payloads now forward structured retry metadata (`error_code`, `error_details`, `repair_hints`, `retryable`) when exceptions provide it;
  - app smoke coverage now exercises the canonical `word` + `count` path with leaner word-cloud input/spec.

## Next Step

- Commit only the relevant word-cloud hardening files and report verification.

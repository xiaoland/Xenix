# TP-24 — AMD Feature Hard Cut-off Proof

## Outcome

Mechanically prove that AMD one-click is a removable composition slice and that a
cutoff build remains a complete ordinary Xenix product.

## Owned Mutation

- add `scripts/verify_amd_cutoff.py`;
- add `tests/test_amd_cutoff.py` and cutoff fixtures;
- add the cutoff build/package switch at the single TP-19/21 composition and
  resource-collection anchors;
- update the AMD-owned decommission runbook.

No capability implementation, SettingsStore, Knowledge policy, provider schema,
or released migration is removed or made conditional.

## Proof Shape

- maintain the exact removable-file and allowed-anchor manifest from
  [the hard cut-off contract](../hard-cutoff.md);
- AST-scan every generic package for forbidden AMD imports, AMD types, import-time
  registration, or ambient entry-point discovery;
- construct a temporary cutoff tree/package without AMD service/resources/UI/tests
  and without the bounded app/spec anchors;
- run generic import, persistence, static provider, spawned Paddle OCR, startup,
  shutdown, diagnostics, and packaged-smoke probes;
- load an old-AMD database/settings fixture and observe typed unavailable managed
  refs with zero selection/fallback/revision mutation.

The verifier does not mutate the developer worktree and does not contact a Radeon
target.

## Acceptance

- no core-to-AMD import edge exists;
- `src/xenix/services/agent/composition.py` and generic smoke/diagnostics contain no
  AMD symbol or conditional import;
- the cutoff app starts with no AMD UI/action/runtime side effect;
- static OpenAI-compatible Chat/Embedding, Paddle OCR, Knowledge, Agent,
  SettingsStore, and SQLite bootstrap remain operational;
- old AMD tables remain inert and old managed refs remain readable/unavailable;
- base dependency installation and cutoff packaging do not resolve or collect
  ROCm/vLLM/RapidOCR target runtimes;
- simulated removal touches only the declared slice and bounded anchors.

## Verification

- `pdm run pytest --direct tests/test_amd_cutoff.py`;
- `pdm run check`;
- cutoff generic smoke/package/smoke-package manifest;
- diff/import/resource/secret scan.

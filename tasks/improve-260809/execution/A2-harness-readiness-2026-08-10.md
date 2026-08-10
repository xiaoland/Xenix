# A2 Formal Agent Harness Readiness — 2026-08-10

## Scope

Provider-free implementation under
[IH-A2](../handshakes/IH-A2-harness-readiness.md). No Subject, Judge, Embedding,
or other paid request ran. No Judge observation or formal Agent evidence was
created.

## Invocation Finding

The A1 shared-invocation blocker was disproved:

- `identity.invocation_id` must be non-empty in every schema-v5 report;
- formal cohort identity intentionally does not require those IDs to match;
- the existing formal-policy test built four unique IDs, one per report, and
  accepted the otherwise-qualified cohort;
- the three headless passes and one headed pass are four pytest invocations,
  each with its own `_InvocationBudgetState` and 4,000,000-token ceiling;
- each six-case pass has a nominal sum of six 500,000-token cell ceilings, below
  its invocation limit, while response-boundary overruns still invalidate and
  halt that invocation.

No `--invocation-id`, durable cross-process counter, or cohort controller was
added. A caller-authored shared ID would identify evidence without owning the
corresponding budget state and would weaken the existing authority model.

## Calibration Readiness

A2 added `ml_formal_judge_calibrations.json` with one suite for each exact
Judge-required A1 rubric:

1. clustering selection;
2. forecast validation;
3. recommendation ranking;
4. grouped text classification;
5. topic discovery.

Each suite resolves the live case's `JudgeRubric` object, uses a bounded
calibration-specific task intent and authoritative facts, and contains one
hand-labelled `pass`, `partial`, `fail`, and empty-evidence `inconclusive`
packet. The loader rejects oversized/malformed manifests, duplicate identities,
non-case symbol references, suite/rubric mismatch, invalid verdicts, and
unbounded packet text before settings or provider dispatch.

The CLI now accepts either its existing `module:symbol` positional source or:

```powershell
pdm run benchmark-agent-harness-calibrate-judge -- `
  --manifest benchmarks/agent_harness/fixtures/ml_formal_judge_calibrations.json `
  --manifest-suite <exact-rubric-id> `
  --judge-llm-settings <external-judge-settings.json> `
  --judge-model <independent-judge-provider/model> `
  --subject-model <pinned-subject-provider/model> `
  --output <bounded-calibration-report.json>
```

No calibration command was run because the required external Judge snapshot is
not available in the audited environment.

## Provider-Free Verification

| Command | Result |
| --- | --- |
| `pdm run benchmark-agent-harness-check -q` | 33 passed |
| manifest CLI source-resolution probe | stable path-free suite identity; 4 packets; no settings/provider load |
| `pdm run benchmark-agent-harness-calibrate-judge -- --help` | exit 0; both source modes exposed |
| exact six selectors, headless `--collect-only -q` | 6 collected |
| exact six selectors, headed `--collect-only -q` | 6 collected |
| `pdm run check` | exit 0 |
| `git diff --check` | exit 0 |

During integration, the concurrent topic prompt temporarily exceeded the
existing 512-character `JudgeInput.task_intent` bound; its owned import-time
guard correctly failed closed. The topic owner reduced the prompt to 505
characters without A2 editing that case, after which both six-case collections
and the full offline Harness check passed.

## Remaining Blockers

- External-only: no frozen independent Judge settings/model snapshot exists, so
  the five suites are runnable inputs but not passing calibration evidence.
- A1-wide: a fresh passing topic characterization, final clean immutable state,
  and full/package qualification remain outstanding.

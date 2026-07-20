# V2 Design

## Topology

```text
external subject settings ──┐
                           ▼
case × subject model → isolated AgentHarness cell → final public outcome
                           │                         │
                           │                         ├─ case evidence projection ─┐
                           │                         │                             ▼
                           └─ subject metrics         └─ external judge settings → LLMService.complete(tools=[])
                                                                              │
                                                                              ▼
                                                                       structured verdict

fixture/settings/isolation/privacy ───────────────────────────────→ integrity channel
```

The subject turn ends before the judge begins. The judge is not constructed by
the headless Agent composition, does not create a Thread or Message, and does
not write to usage observability intended for primary Agent requests.

## Ownership

| Owner | Responsibility | Must not do |
| --- | --- | --- |
| Runner | cell lifecycle, independent settings loading, generic judge dispatch, result persistence | inspect a case id or derive case truth |
| Case | submission, terminal output location, evidence projection, rubric/fact identity | call a provider or persist raw evidence |
| Judge service | request framing, delimiter neutralization, direct provider call, strict response parsing, judge metrics | inspect Harness transcript or alter product state |
| Result contract | separate state channels and privacy-safe serialization | retain raw prompt/response/error data |
| Tests | deterministic boundary/failure/privacy proof and explicit live acceptance | call a provider in the default suite |

## Result Channels

V2 retains `run_status` for subject execution and introduces distinct channels:

| Channel | Examples | Interpretation |
| --- | --- | --- |
| `run_status` | completed, invalid setup, runtime error | Was the subject cell executable? |
| `integrity` | valid, invalid fixture, escaped runtime, unsafe report | Can this measurement be trusted? |
| `semantic` | pass, partial, fail, inconclusive, not evaluated | What did the final outcome achieve? |
| `judge_status` | completed, not configured, blocked, provider error, invalid response | Can V2 attribute a judge verdict? |
| `subject_metrics` | turn seconds, Harness token usage, messages, Tool results | Cost/behavior of the subject only |
| `judge_metrics` | judge seconds, usage, retries | Cost/behavior of evaluation only |

`semantic=fail` is a scored subject outcome. `judge_status=provider_error` or
`semantic=inconclusive` is not a subject fail. A report consumer must not
collapse these channels into one boolean.

## Judge Configuration

The CLI/configuration contract is deliberately separate:

```text
--llm-settings / XENIX_AGENT_BENCHMARK_LLM_SETTINGS_PATH
    subject provider matrix

--judge-llm-settings / XENIX_AGENT_BENCHMARK_JUDGE_LLM_SETTINGS_PATH
    one judge provider settings snapshot

--judge-model
    optional fully qualified model key inside judge settings
```

The runner must never silently reuse the subject default model as judge. It may
accept the same settings file or same model when explicitly selected, then mark
the result `judge_independence=same_model`.

V2 initially uses `LLMService.complete()` with `tools=[]`, one judge request,
and judge settings whose retry/timeout policy is controlled outside subject
settings. Strict JSON and bounded response fields limit output shape; a hard
per-request output-token cap is not added until the core provider contract has
separate evidence and approval.

## Text-Only Evidence Boundary

The current provider abstraction carries text messages. A V2 graph judge sees
a bounded semantic projection of the final SVG—not the full DOM or a rendered
image. It can judge task relevance and factual grounding; it cannot credibly
grade palette, visual balance, or pixel readability. Vision input belongs to a
future capability-specific task, with its own artifact size/privacy contract.

## Failure Flow

```text
No terminal artifact        → semantic=fail, judge_status=blocked
Integrity breach            → integrity=invalid, semantic=not evaluated
Evidence cannot support rubric → semantic=inconclusive, judge_status=completed
Judge request/provider error → semantic=not evaluated, judge_status=provider error
Judge verdict fail          → integrity=valid, semantic=fail, judge_status=completed
```

This distinction preserves a usable benchmark report even where one system
component cannot complete its work.

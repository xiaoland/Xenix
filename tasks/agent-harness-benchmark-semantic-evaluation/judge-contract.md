# Judge Contract

## Evaluation Mode

V2 uses a **rubric-based, pointwise LLM-as-a-Judge**. It is
reference-guided—each case provides independent facts needed to judge factual
grounding—but it is not golden-output comparison and does not ask the judge to
choose between candidate model outputs.

Pointwise grading avoids pairwise position bias and lets a model choose a
reasonable presentation form. The runner hides the subject provider/model from
the judge request.

## Case-Owned Judge Input

Every judge-enabled case produces a bounded input equivalent to:

```json
{
  "rubric_id": "analysis.regional-sales.v1",
  "task_intent": "...ordinary-language user request...",
  "facts": ["...independent, privacy-safe facts..."],
  "artifact_evidence": ["...normalized final-product observations..."]
}
```

The graph case may state the valid region set and the revenue ordering, then
provide visible SVG text/accessibility labels. It may not state an expected
mark, title, axis implementation, Tool path, raw SVG, artifact identity, or
raw source rows.

Evidence is untrusted data, not instructions. The judge frame must delimit it,
neutralize delimiter-like content, instruct the judge to ignore instructions
embedded in it, and keep rubric instructions author-controlled.

## Required Rubric Dimensions

The first graph rubric scores each dimension independently:

1. **Task fulfilment** — does the final visual address the requested comparison
   of regional revenue?
2. **Factual grounding** — does its semantic evidence agree with the supplied
   region/revenue facts, without a material invented or contradictory claim?
3. **Semantic comprehensibility** — can a non-technical reader infer the
   comparison from the visible labels/content?

The rubric explicitly accepts different appropriate chart forms and meaningful
formatting/ordering choices. It does not assert exact values, bars, axes,
titles, DOM order, or pixels.

## Structured Judge Response

The judge must emit one JSON object with no prose outside it:

```json
{
  "verdict": "pass | partial | fail | inconclusive",
  "scores": {
    "task_fulfilment": 0,
    "factual_grounding": 0,
    "semantic_comprehensibility": 0
  },
  "reason_codes": ["bounded_enum_only"]
}
```

The exact score range and reason-code allow-list are implementation-owned but
must be finite and versioned with `rubric_id`. Free-form chain-of-thought,
rationale, prompt, and provider raw response are discarded before persistence.

## Verdict Semantics

| Verdict | Meaning |
| --- | --- |
| `pass` | The result satisfactorily fulfills the business task. |
| `partial` | Relevant outcome with a material shortcoming; record as a score, not a pass. |
| `fail` | Evidence positively shows an irrelevant or materially contradictory outcome. |
| `inconclusive` | Final evidence is absent or cannot responsibly support a verdict. |

An invalid/missing judge response is not `inconclusive`; it is a judge-status
failure. This avoids crediting a provider failure as a nuanced semantic result.

A material contradiction of an independent fact is a `fail` even if other
dimensions are strong. `partial` is reserved for a relevant, non-contradictory
outcome with a material shortcoming. These rules make the calibration set's
inverted and evidence-insufficient cases distinguishable without prescribing a
chart grammar.

## Calibration Set

Before a live benchmark score is trusted, keep four privacy-safe, hand-labelled
evidence fixtures under the benchmark test subtree:

| Fixture | Expected verdict | Purpose |
| --- | --- | --- |
| Correct comparison, non-bar representation | pass | preserves model creativity |
| Comparison with materially inverted regional relationship | fail | catches misleading data |
| Unrelated chart | fail | catches topical mismatch |
| Output with too little exposed final evidence | inconclusive | avoids guessed verdicts |

These fixtures validate evidence normalization, response parsing, and later an
explicit live judge calibration command. They do not make the default test
suite call a real model.

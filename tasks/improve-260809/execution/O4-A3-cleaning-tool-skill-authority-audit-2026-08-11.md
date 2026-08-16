# O4-A3 Cleaning Tool/Skill Authority Audit — 2026-08-11

## Verdict

The A3 state diff is warranted and can remain entirely at the Agent contract
boundary. The cleaning service already owns atomic validation and ordered
execution; O4-A1 repaired its nullable comparison semantics, and O4-A2 exposed
the bounded effects needed for final grounding. The remaining route divergence
comes from what the Provider is told:

- the baseline typed Provider schema does not state that `operations` execute
  left-to-right on the result of the preceding operation;
- `data.clean` and `data.transform` both appear to own row filtering;
- the preprocessing Skill's direct recipes omit `text.lowercase` and
  `validation.non_negative(action="drop_rows")`;
- the optional Tool reference historically encouraged a schema/sample query,
  even though `analysis.profile` already provides the source indexes needed by
  this case.

The reviewed working-tree candidate addresses those points without hiding SQL
capability or changing the outcome oracle. During this audit, three candidate
gaps were identified and relayed to the implementation owner: qualify the
`params` column-selector sentence so operations without selectors remain
valid, remove the reference's `SELECT *` index advice and generic
schema/sample-query start, and prove that preprocessing activation keeps both
`data.clean` and `data.transform` visible. The candidate subsequently adopted
all three corrections. Paid outcome evidence does not yet exist.

## Evidence Topology

```text
user's explicit ordered cleaning request
                  |
                  v
      activate xenix-data-preprocessing
                  |
                  v
 analysis.profile supplies indexes/quality facts
                  |
       +----------+-----------+
       |                      |
       v                      v
data.clean validation     data.transform filter
(atomic owner)            (overlapping old wording)
       |                      |
       +----------+-----------+
                  |
       extra query/metadata/Dataset variance
```

Skill activation is not the defect. In
`composition.py::_AGENT_SKILL_TOOL_NAMES`, preprocessing legitimately exposes
both Tools after activation; `data.query` is supplied by the common Tool set.
Before activation, only activation and Knowledge lookup are visible. The
contract fix must therefore disambiguate responsibility while retaining both
capabilities.

## Retained and Historical Facts

| Evidence | Exact retained fact | Relevance to A3 |
| --- | --- | --- |
| Historical run `d4fc5a8482a94c81a1909b1760345b24` | semantic/integrity pass; 8 rounds; 69,863 subject tokens; 102.266 s; activate/profile/query ×2/metadata/clean/transform; 2 derived Datasets | Aggregate reference only. Its runtime was deleted, so Tool order and first divergence are unknown. |
| Retained run `cd06c2749edc4333b8ef3aa98025c04d`, cell `cell-po99t6rj` | activate → profile → validation metadata → broad ordered source query → one five-operation clean; sequence 14 ordered dedupe → non-negative drop → trim → lowercase → median fill | The Agent explicitly questioned whether operations interact sequentially. This route was semantically broken by the now-fixed nullable service bug, then entered recovery. |
| Retained run `68cf62b1764b4750a3c1938ae9765c98`, cell `cell-hd4xdph7` | activate → profile → broad `SELECT *` → text metadata → clean → transform → clean → final; pass in 8 rounds, 62,502 tokens, 101.532 s; 3 derived Datasets | Sequence 7 is the first efficiency divergence: the Agent says conditional row removal belongs to transform. Sequence 10 reads text metadata because lowercase is absent from direct recipes. |

The retained SQLite databases are:

- `execution/raw/o4-cleaning-causal-diagnosis/retained-runtime/cell-po99t6rj/runtime/state/xenix.db`;
- `execution/raw/o4-cleaning-causal-diagnosis/retained-runtime/cell-hd4xdph7/runtime/state/xenix.db`.

The historical report is the ignored
`build/agent-harness-benchmarks/ml.cleaning_service_tickets-kimi-kimi-k2.6-d4fc5a8482a94c81a1909b1760345b24.json`.
The full cross-run qualification and limitations remain in the
[O4 causal diagnosis](O4-cleaning-causal-diagnosis-2026-08-11.md).

### Fact, inference, and unknown

- **Fact:** the exact benchmark prompt already authorizes the order dedupe →
  reject negative `parcel_count` → trim/lowercase `state` → fill the remaining
  missing `parcel_count` with the retained-record median.
- **Fact:** `ServiceTicketCleaningCase._resolve_outcome` accepts any exact
  run-descendant Dataset. `_matches_expected` requires the exact five-row,
  four-column result, and the final-answer check requires row count 5 and median
  21. The benchmark intentionally does not prescribe a Tool trace.
- **Fact:** the two retained runs reached different, locally plausible Tool
  routes with the same case/model/settings identities.
- **Inference:** declaring one atomic-filter owner and the ordered execution
  semantics removes the observed reasons for metadata, broad-query, and
  transform branches. This is strong causal guidance, not proof that a
  stochastic model will follow the shortest route.
- **Unknown:** the historical run's exact order, whether its transform was
  planned or recovery, and which query grounded its final median.
- **Unknown:** post-A3 route stability, tokens, and elapsed time until the paid
  three-run series is retained and inspected.

## Minimal State Diff and Exact Owners

| Exact symbol/paragraph | From | To |
| --- | --- | --- |
| `tool_inputs.py::CleaningOperationInput.operation` | opaque operation string | provider description says the atomic operation executes at this list position on the current intermediate Dataset |
| `tool_inputs.py::CleaningOperationInput.params` | arbitrary object with no semantic description | parameters resolve against the current intermediate Dataset; when columns are selected, one name or index form is used without implying that every operation has a selector |
| `tool_inputs.py::DataCleanInput.operations` | generic list | explicit strict left-to-right list and filter-before-imputation consequence |
| `tools.py::AgentToolRegistry._build_data_clean_tool` | atomic cleaning without filter priority or order | supported validation owns row checks/rejection; transform is only the unsupported-predicate fallback |
| `tools.py::AgentToolRegistry._build_data_transform_tool` | generic DuckDB derived Dataset | retains SQL power but yields supported cleaning predicates to atomic validation |
| `xenix-data-preprocessing/SKILL.md::Efficient Cleaning Path` | generic clean next; transform owns filters | one ordered clean list; profile-first evidence; atomic validation before transform fallback |
| `SKILL.md::Direct Routine Recipes` | no lowercase/non-negative recipe | direct `text.lowercase` and authorized `validation.non_negative(..., action="drop_rows")`; metadata is unnecessary for them |
| `SKILL.md::Cleaning Column References` | column-set boundaries only | general current-frame ordering plus the dedupe → validate → text → impute example |
| `references/preprocessing-tools.md::data.clean`, `data.transform`, and `Planning Pattern` | query-first and overlapping filter ownership | profile-first; no broad query for source indexes; ordered atomic-clean authority; unsupported SQL fallback |
| generated `skills/catalog.json` | old embedded Skill/reference | regenerated from the canonical Skill sources; never hand-edited |
| provider-free contracts | no A3 proof | real registry schema, generated Skill catalog, and activated preprocessing Tool scope assertions |

No change belongs in `DataCleaningService`, `DataQueryTransformService`,
`agent_skill_tool_scope_names`, Tool execution orchestration, the cleaning
benchmark prompt/evaluator, Provider settings, budgets, or model selection.
Hard-coding the complete cleaning-operation catalog as a nested Provider enum
would also be the wrong diff: it would duplicate the service catalog, enlarge
every request, and defeat progressive metadata disclosure.

## Responsibility Rule

`data.clean` is the unique owner when all of the following are true:

1. the task is an authorized cleaning operation on one Dataset;
2. the Dataset's schema/grain remains the same apart from that atomic clean;
3. an advertised validation operation expresses the predicate, including
   non-negative, min/max, not-null, allowed-values, or regex checks;
4. the requested action is `report_only` or an already-authorized `drop_rows`.

Within one clean call, operations execute left-to-right against the current
intermediate Dataset. Missing values are not numeric comparison violations;
`validation.not_null` owns explicit missing rejection. Therefore validation
must precede median imputation when the requested median is fitted only on
retained valid records.

`data.transform` remains the owner for cross-column or compound predicates not
represented by an atomic operation, projections/renames, derived fields,
joins, aggregates, reshaping, windows/subqueries, and grain changes. If such a
transform is genuinely needed, it materializes a new Dataset and any later
clean operates on the returned Dataset and its current schema. It must not be
used merely to duplicate an advertised atomic validation.

`data.query` is evidence, not execution-order documentation or manual service
arithmetic. Use it only when an exact value/membership question absent from
the bounded profile or clean result changes a decision. `data.clean.metadata`
is reserved for an unfamiliar operation or parameter not covered by direct
recipes.

## Provider-Free Black-Box and Contract Matrix

| Case | Boundary exercised | Required assertion | Negative assertion |
| --- | --- | --- | --- |
| Real registry Provider schema | instantiate `AgentToolRegistry` and inspect `list_specs()` | `data.clean.operations` and nested operation/params descriptions carry current-frame ordering; clean/transform descriptions agree on ownership | no service call, no full operation catalog enum, no benchmark-specific field/value |
| Generated Skill activation | `AgentSkillCatalog.from_default_catalog().activate(...)` | versioned body contains left-to-right semantics, lowercase/non-negative recipes, and transform fallback | metadata is not required for those recipes; no broad sample instruction |
| Optional reference read | read the real embedded `preprocessing-tools.md` after activation | profile supplies source indexes; planning and Tool responsibility sections repeat the same ownership | no `start with ... schema/sample query` and no source `SELECT *` recommendation for cleaning indexes |
| Progressive Tool scope | activate preprocessing through the real scope projection | `analysis.profile`, common `data.query`, `data.clean`, metadata, and `data.transform` remain visible | inactive scope exposes neither clean nor transform; modeling activation does not gain clean |
| Existing A1 service black box | registered canonical staged Dataset and independent expected table | one ordered clean preserves nullable rows through comparison, removes only duplicate/negative, fills 21, and yields exact 5 × 4 output | reverse-order control differs; report-only does not remove rows; missing is not a comparison violation |
| Existing A2 Tool projection | real `data.clean` Tool result | bounded validation effect and resolved median 21 reach Provider context with public IDs | no cleaned preview, raw value lists, local paths, or raw-payload fallback |
| Benchmark offline contract | collect exact case and run input/hash validation without Provider | one exact route-agnostic case remains collectible; fixture/oracle are unchanged | no Tool-count or route assertion is added to the evaluator |

Text contract tests should assert a small set of durable semantic anchors via
the public registry/catalog, not snapshot entire prose or read implementation
files directly. Service outcome proof stays in its independent black-box test;
A3 must not mirror the cleaning algorithm in a new test.

The focused provider-free audit selector passed before packet closeout:

```text
pdm run pytest --direct \
  tests/test_agent_data_cleaning_guidance.py::test_cleaning_provider_contract_declares_order_and_filter_authority \
  tests/test_agent_skill_tool_scope.py -q
4 passed
```

After the generated catalog is refreshed, the implementation gate should also
run the full new guidance module, the existing A1/A2 service/Tool selectors,
`pdm run benchmark-agent-harness-check -q`, the exact case with
`--collect-only`, then the ordinary suite, `pdm run check`, and `pdm run smoke`.

## Paid Three-Run Ablation Protocol

Do not run this audit as a paid action. After provider-free gates and an
immutable implementation identity are recorded, execute this exact selector
three times as three independent invocations:

```powershell
pdm run benchmark-agent-harness -- `
  benchmarks/agent_harness/test_ml_cleaning.py::test_ml_cleaning `
  --model kimi/kimi-k2.6 `
  --llm-settings <external-untracked-subject-settings.json> `
  --harness-variant o4-a3-cleaning-tool-skill-authority `
  --output-dir tasks/improve-260809/execution/raw/o4-a3-cleaning-tool-skill-authority/reports `
  -q
```

Use a task-local retained-runtime adapter equivalent to the existing ignored
`execution/raw/o4-cleaning-causal-diagnosis/run_retained_cleaning.py`; the
normal runner's temporary cell directory is deleted and cannot prove ordered
Tool calls. Retain each cell under:

```text
execution/raw/o4-a3-cleaning-tool-skill-authority/
  reports/<privacy-bounded-report>.json
  retained-runtime/cell-<id>/runtime/state/xenix.db
  retained-runtime/cell-<id>/runtime/logs/llm-usage.jsonl
  diagnostic-manifest-<run-id>.json
```

The tracked execution summary records only run/invocation IDs, revision and
case/fixture/settings/effective hashes, semantic/integrity verdicts, ordered
Tool-name/count summary, public Dataset/Artifact IDs, lineage shape, rounds,
tokens, elapsed time, retries/failures, and the evidence limitation. Raw
messages, arguments, rows, Provider payloads, settings, and paths stay ignored.

### Acceptance metrics

Hard outcome and route targets:

- 3/3 semantic and integrity pass; exact 5 × 4 Dataset, median fill 21, and
  ready public Artifact link;
- exactly one source descendant created by exactly one `data.clean` call;
- clean result reports one duplicate removal, one non-negative validation
  violation/removal, two total removed rows, and one median-filled cell with
  resolved value 21;
- zero `data.transform`, zero `data.clean.metadata`, zero broad/raw-row
  `data.query`, zero failed Tool results, and zero retries;
- source profile once; an optional post-clean profile is acceptable, but no
  query is needed merely to explain the resolved median or operation effects;
- median sampling rounds no greater than 5, with the 12-round, 900-second,
  500k-cell-token, and 4m-invocation-token safety limits unchanged.

Characterization metrics, not standalone correctness gates:

- report all three token/elapsed values and their median;
- compare token median with retained staged reference 62,502 and historical
  reference 69,863, but do not claim causal savings from non-contemporaneous
  runs;
- elapsed time is Provider/network sensitive and is reported rather than used
  to weaken an otherwise correct result.

On any miss, inspect the SQLite sequence and the immediately preceding Agent
reasoning. Classify the first divergence as schema, Tool description, Skill,
reference, Tool result, orchestration, model synthesis, or service/Provider
failure. A miss is evidence; it does not authorize benchmark-route assertions,
a looser oracle, or another product change in A3.

## Audit Conclusion

The reviewed A3 boundary is minimal and falsifiable. It closes the exact
authority and observability gaps reproduced in O4 while preserving the
service-owned execution semantics, progressive Skill scope, SQL escape hatch,
and route-independent benchmark. Offline contracts can prove that the intended
state reaches Provider context; only the retained paid three-run series can
prove that the model consistently consumes it.

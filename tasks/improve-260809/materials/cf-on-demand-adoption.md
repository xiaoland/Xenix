# CF On-Demand Material Adoption

**Status:** Active guardrail for the approved `IH-CF`; implementation start does not authorize a new private-material run.

This file narrows the general [on-demand material-adoption contract](on-demand-adoption.md) to clustering and forecasting. Original bytes, every derivative, answers, future windows, and reference outputs remain ignored/evaluator-private; no serialized artifact is loaded.

## Selected Clustering Material

| Risk | Reference code | Data | Intended private evidence |
| --- | --- | --- | --- |
| candidate quality/selection | `ch12/code/clustering_evaluation/clustering_evaluation_selection.py` | `ch12/code/clustering_evaluation/customer_clustering_evaluation.csv` | silhouette/Calinski-Harabasz/Davies-Bouldin behavior, candidate ranking, runtime |
| original-scale profiles | `ch12/code/segment_profiles/customer_segment_profiles.py` | `ch12/code/segment_profiles/digital_content_customer_profiles.csv` | bounded cluster size and business-profile aggregates |
| noise semantics | `ch12/code/other_clustering/shopping_district_dbscan_case.py` | `ch12/code/other_clustering/shopping_district_dbscan.csv` | noise rate, unavailable metrics, non-reusable apply semantics |

Hidden memberships, if derived for oracle qualification, are never placed in subject inputs. Reference labels are compared permutation-invariantly and never define product label numbers.

## Selected Forecast Material

| Risk | Reference code | Data | Intended private evidence |
| --- | --- | --- | --- |
| rolling evaluation/uncertainty | `ch15/code/forecast_evaluation/forecast_validation_uncertainty.py` | `ch15/code/forecast_evaluation/regional_home_ecommerce_daily_orders.csv` | temporal folds, future isolation, metrics, interval behavior |
| SARIMA selection/convergence | `ch15/code/arima/arima_seasonal_models.py` | `ch15/code/arima/outdoor_direct_store_sales.csv` | bounded order policy, convergence, grouped runtime, candidate value |
| seasonal-naive/Holt-Winters comparison | `ch15/code/smoothing/moving_average_exponential_smoothing.py` | `ch15/code/smoothing/urban_instant_retail_flower_orders.csv` | cadence/season admission, baseline/candidate error and cost |

The first safe aggregate comparison is recorded as [`E-017`](../evidence/forecast-o004-spike.md). `D-014` includes all three methods; private material qualifies safeguards and realistic behavior, not scope authority.

## Admission and Output

Before a selected run:

1. recompute source/code SHA-256 and record runtime/dependency identity;
2. inspect license/provenance status; unresolved remains `internal_only`;
3. mount only selected inputs/reference code into the private runner and keep subject/evaluator roots disjoint;
4. block network, GUI, bytecode, archive extraction, subprocess escape, and Joblib/Pickle loading;
5. hide memberships/future windows/reference outputs from the subject projection;
6. fail closed on a missing adapter, mismatched hash/schema, overlap, unsafe import, or unqualified oracle.

Tracked output may contain logical IDs, hashes, shapes, algorithm/policy versions, aggregate metrics, convergence counts, timing/memory, limitations, and verdict. It may not contain original rows, exact private future values, memberships, answer text, credentials, local subject-visible paths, raw traces, or model artifacts.

## Clean-Room Correspondence

- `tests/fixtures/ml_cf_service/segment_quality_v1.csv` independently represents quality/stability/noise/profile risks; it never copies ch12 bytes or memberships.
- `tests/fixtures/ml_cf_service/weekly_demand_validation_v1.csv` independently represents cadence/rolling/SARIMA/interval risks; it never copies ch15 bytes or future values.
- Benchmark fixtures are separately designed again and share only planning risk IDs.
- Private-material verdicts never replace clean-room CI or Agent verdicts.

## Triggers

Run the selected private profile only for one explicit real-scale, convergence, format, performance, ablation, diagnosis, or final manual-acceptance question. Default CI, service implementation, and initial paid Agent characterization do not search for or silently skip these files.

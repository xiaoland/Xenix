# Open Questions

## Resolved B0 Review

Sir approved the B0 design on 2026-08-09 with the D-008 through D-010 corrections. These entries remain only as decision history; none is open.

| ID | Resolution | Consequence |
| --- | --- | --- |
| O-001 | Approved `P-005` | Clean-room committed fixtures and ignored private material remain separate; service and Agent assets also remain in separate executable trees |
| O-002 | Approved `P-006` | The service proof portfolio may grow beyond 50 after explicit architecture review; no test-count gaming |
| O-003 | Approved as revised `P-007` | The corresponding service tests gate CI dispatch only; every Agent baseline is bounded, paid, live, and independently executable |

## Later Product Decisions

| ID | Blocking point | Question | Current recommendation |
| --- | --- | --- | --- |
| O-004 | Before `IH-CF` | Does forecast v1 include SARIMA immediately? | Seasonal-naive + Holt-Winters first; add SARIMA only if the qualified case shows material value within runtime budget |
| O-005 | Before `IH-RT` | Confirm recommendation v1 scope | Popularity/cold-start + collaborative Top-K; defer matrix factorization/hybrid |
| O-006 | Before any publication | Can source or derived textbook fixtures be redistributed? | Treat as `internal_only` until provenance review explicitly clears them |
| O-007 | After an unclassifiable run | Which extra trace fields are required? | Add only the minimum field needed to classify the first divergence |

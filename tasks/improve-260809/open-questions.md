# Open Questions

## Resolved B0 Review

Sir approved the B0 design on 2026-08-09 with the D-008 through D-010 corrections. These entries remain only as decision history; none is open.

| ID | Resolution | Consequence |
| --- | --- | --- |
| O-001 | Approved `P-005` | Clean-room committed fixtures and ignored private material remain separate; service and Agent assets also remain in separate executable trees |
| O-002 | Approved `P-006` | The service proof portfolio may grow beyond 50 after explicit architecture review; no test-count gaming |
| O-003 | Approved as revised `P-007` | The corresponding service tests gate CI dispatch only; every Agent baseline is bounded, paid, live, and independently executable |

## Resolved IH-CF Review

Sir resolved `O-004` on 2026-08-09: forecast v1 includes seasonal-naive, Holt-Winters, and SARIMA. The narrower evidence recommendation was rejected; its convergence, selection, and runtime findings now define SARIMA safeguards rather than a deferral gate.

| ID | Resolution | Consequence |
| --- | --- | --- |
| O-004 | Include all three forecast methods | `IH-CF` must qualify bounded temporal SARIMA selection, fail-closed convergence, comparable interval evidence, and grouped runtime limits in the first implementation |

## Resolved Recommendation and Text Design Review

Sir approved the complete `IH-RT` decision set on 2026-08-10. The choices below are retained as decision history; none remains open or blocks implementation.

| ID | Resolution | Consequence |
| --- | --- | --- | --- |
| O-005 | Explicit-rating personalized Top-K, same-truth popularity fallback, cold-user support, no cold-item/implicit/MF/hybrid | Adopted as `D-016` |
| O-008 | Explicit latest-positive holdout with time and deterministic hash-positive holdout without time | Adopted as `D-016`; no silent fallback |
| O-009 | Raw-text active analyzers with retained preparation; keep atomic `data.tokenize` | Adopted as `D-017` |
| O-010 | Bounded sanitized terms and local-only raw/vocabulary/identifier content | Adopted as `D-018` |
| O-011 | Relevance metrics only with truth; otherwise `index_diagnostic` | Adopted as `D-019` |
| O-012 | All four text service contracts, classification/topic live, retrieval service-only until truth exists | Adopted as `D-019` |

## Still-Open External or Evidence-Triggered Questions

| ID | Blocking point | Question | Current recommendation |
| --- | --- | --- | --- |
| O-006 | Before any publication | Can source or derived textbook fixtures be redistributed? | Treat as `internal_only` until provenance review explicitly clears them |
| O-007 | After an unclassifiable run | Which extra trace fields are required? | Add only the minimum field needed to classify the first divergence |
| O-013 | Before formal Agent acceptance | Which independently configured subject-disjoint Judge model/settings snapshot will own calibrated semantic verdicts? | Freeze one external Judge snapshot, calibrate exact rubric hashes, and reject same-model/unavailable Judge evidence |
| O-014 | Before the repository-wide packaged acceptance gate | Where is the locked Native OCR golden image supplied for `pdm run smoke-package`? | Keep the ML frozen-binary smoke as valid scoped evidence; do not claim the official package gate until the golden is restored |

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

## Recommendation and Text Design Review

The Dataset-profile privacy default, material-ambiguity role policy, and two-slice foundation structure were resolved as `D-011` through `D-013`. Vertical 01 is complete. The following choices are the complete product-level review boundary for proposed `IH-RT`; implementation details such as DTO names, metric formulas, seeds, and storage plumbing remain engineering-owned.

| ID | Blocking point | Question | Current recommendation |
| --- | --- | --- | --- |
| O-005 | Before approving `IH-RT` | Which recommendation problem is v1? | Explicit-rating personalized collaborative Top-K plus a same-truth popularity baseline; support cold users with popularity, reject cold items, and defer implicit feedback/matrix factorization/hybrid |
| O-008 | Before approving `IH-RT` | How is recommendation holdout chosen when time is optional? | Make the policy explicit: latest positive interaction when a valid time role exists, deterministic hash-selected positive interaction otherwise; never silently switch policies |
| O-009 | Before approving `IH-RT` | Do text models consume raw text or require a prior token Dataset? | Active analyzers consume raw text and retain the exact preparation spec; atomic `data.tokenize` remains available for descriptive frequency/inspection and reusable derived data |
| O-010 | Before approving `IH-RT` | May bounded interpretable terms enter Agent context? | Permit a small sanitized list of top terms for explanation; keep raw text, full vocabulary, document/user/item IDs, matches, and rows local |
| O-011 | Before approving `IH-RT` | What may similarity retrieval claim without relevance truth? | With bound relevance truth, report ranking metrics; otherwise report only an `index_diagnostic` state and never imply retrieval quality |
| O-012 | Before approving `IH-RT` | Which advertised text workflows belong in this pass? | Qualify classification, clustering, topics, and similarity through honest service contracts; add independent live classification and topic cases, while retrieval stays service-only until a relevance-bearing business live case exists |
| O-006 | Before any publication | Can source or derived textbook fixtures be redistributed? | Treat as `internal_only` until provenance review explicitly clears them |
| O-007 | After an unclassifiable run | Which extra trace fields are required? | Add only the minimum field needed to classify the first divergence |

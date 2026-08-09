# Impact Handshake Index

The first handshake has been consumed for implementation. Later product behavior and service-test work still requires its own reviewed handshake.

| ID | Intended scope | Status |
| --- | --- | --- |
| [`IH-B0`](IH-B0.md) — B0 Agent Harness baseline, acceptance, and diagnosis infrastructure | Independent Agent benchmark assets, single-model live safety, Judge calibration, Agent-report policy, and guidance/CI ordering; no `tests/` service cases or `src/xenix` product behavior change | consumed for implementation and offline-verified 2026-08-09; live baseline deferred |
| `IH-F` | Bounded profile/evaluation/result facts and split-aware preparation semantics | not drafted; depends on B0 evidence |
| `IH-CF` | Clustering trustworthiness and first native forecast workflow | not drafted; depends on O-004 and IH-F |
| `IH-RT` | Recommendation ranking and text quality workflows | not drafted; depends on O-005 and stable shared contracts |
| `IH-O<n>` | One exact preprocessing/Skill/Tool/orchestration/observability optimization | evidence-triggered only |

Each detailed handshake must contain:

- Address and Object: exact files, anchors, or symbols;
- State Diff: objective `From -> To`;
- Blast Radius: downstream consumers and surfaces;
- Invariants: behavior and authority that remain unchanged;
- Verification: focused and repository-wide proof;
- prerequisite Evidence IDs;
- status: `proposed`, `approved`, `consumed`, or `superseded`;
- return-to-discussion triggers.

The dashboard links to the handshake; it must not copy the detailed authorization and create a second owner.
